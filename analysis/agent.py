"""
Agent module for the soccer data analysis system.

This module contains the core agent functionality including running the agent
with and without conversation history, processing tool calls, and managing
interactions with the Claude API.
"""

import os
import json
import anthropic
from typing import Dict, List, Any, Optional, Tuple
from rich.console import Console
from datetime import datetime
import re, calendar, time

# Import tool definitions and implementations from our modules
from analysis.tools.claude_tools import (
    get_claude_tools,
    get_tool_mapping
)
from analysis.database import DuckDBAnalyzer
from analysis.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    BATCH_SYSTEM_PROMPT
)

# Initialize console for rich output
console = Console()

def run_agent(question: str, parquet_file: str, max_tokens: int = 1000) -> str:
    """
    Run the agent to process a natural language question about data in the parquet file.

    Args:
        question: The natural language question to answer
        parquet_file: Path to the parquet file
        max_tokens: Maximum number of tokens in the response

    Returns:
        The agent's response as a string
    """
    response_text, _ = run_agent_with_memory(question, parquet_file, max_tokens)
    return response_text


def update_conversation_history(conversation_history, question=None, response=None):
    """
    Helper function to update conversation history with a simplified structure.

    Args:
        conversation_history: The existing conversation history (can be None)
        question: Optional question to add as a user message
        response: Optional string response to add as an assistant message

    Returns:
        Updated conversation history
    """
    # Initialize conversation history if it's None
    if conversation_history is None:
        conversation_history = []

    # Add user question if provided
    if question is not None:
        conversation_history.append({
            "role": "user",
            "content": [{"type": "text", "text": question}]
        })

    # Add assistant response if provided
    if response is not None:
        conversation_history.append({
            "role": "assistant",
            "content": [{"type": "text", "text": response}]
        })

    return conversation_history


def run_agent_with_memory(question: str, parquet_file: str, max_tokens: int = 1000,
                          conversation_history=None) -> Tuple[str, int]:
    """
    A version of run_agent that supports externally passed conversation history.
    This is primarily used for testing and situations where the conversation flow
    is managed externally (like in the smoke test).

    Args:
        question: The natural language question to answer
        parquet_file: Path to the parquet file
        max_tokens: Maximum number of tokens in the response
        conversation_history: Optional conversation history for follow-up questions

    Returns:
        A tuple of (response_text, tool_call_count)
    """
    # Get API key from environment variable
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable is not set.[/red]")
        return "Error: ANTHROPIC_API_KEY environment variable is not set.", 0

    # Verify the parquet file exists
    if not os.path.exists(parquet_file):
        console.print(f"[red]Error: Parquet file {parquet_file} does not exist.[/red]")
        console.print("[yellow]Tip: Use 'make refresh-data' to download data from AWS S3.[/yellow]")
        return f"Error: Parquet file {parquet_file} does not exist.", 0

    # Use the system prompt from our centralized prompts module
    system_prompt = ANALYSIS_SYSTEM_PROMPT

    # Use provided conversation history or initialize new
    if conversation_history:
        messages = conversation_history
    else:
        # Get schema information
        analyzer = DuckDBAnalyzer(parquet_file)
        schema_list, schema_json = analyzer.get_schema()
        # Create a compact schema representation instead of using the full JSON
        compact_schema = "Columns: " + ", ".join([f"{col['column_name']} ({col['data_type']})" for col in schema_list])
        enriched_context = f"Schema: {compact_schema}"

        # Only add date filtering context if specifically asked about a month/year
        time_match = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})", question, re.IGNORECASE)
        if time_match:
            month_str = time_match.group(1)
            year_str = time_match.group(2)
            month_num = list(calendar.month_abbr).index(month_str.title())
            start_date = f"{year_str}-{month_num:02d}-01"
            last_day = calendar.monthrange(int(year_str), month_num)[1]
            end_date = f"{year_str}-{month_num:02d}-{last_day:02d}"
            # Instead of adding full filtered results, just add the date range info
            enriched_context += f" | Date range: {start_date} to {end_date}"

        # Get current date information
        current_date = datetime.now()

        # Prepare the initial message with enriched context, but more concise
        initial_message = f"""Question: {question}
        Today's date: {current_date.strftime('%Y-%m-%d')}
        Data source: {parquet_file}
        {enriched_context}
        """

        # Format as per Claude's content blocks requirements
        messages = [{"role": "user", "content": [{"type": "text", "text": initial_message}]}]

    # Map tool names to their corresponding functions
    tool_functions = get_tool_mapping()

    # Get tools for the agent from the claude_tools module
    tools = get_claude_tools()

    # Setup retry logic
    max_retries = 3
    base_delay = 5  # seconds
    client = anthropic.Anthropic(api_key=api_key)

    # Track tool calls
    total_tool_calls = 0

    # Track the final response from Claude
    final_response_text = ""

    # Process messages recursively until Claude provides a complete response
    while True:
        # Process with retry logic and exponential backoff
        for attempt in range(1, max_retries + 1):
            console.print(f"[yellow]Making API call to Claude (attempt {attempt}/{max_retries})[/yellow]")
            
            try:
                # Make the API call with Claude 3.7 Sonnet (fine-tuned for tool calling)
                response = client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=max_tokens,
                    messages=messages,
                    system=system_prompt,
                    tools=tools,
                )
                console.print("[green]API call successful[/green]")
                break  # Success, exit the retry loop
                
            except anthropic.APIStatusError as e:
                # Handle specific status errors like rate limits and overloaded
                if e.status_code in [429, 529]:  # Rate limit or overloaded
                    if attempt < max_retries:
                        # Calculate backoff time with exponential increase and some randomness
                        backoff_time = base_delay * (2 ** (attempt - 1)) * (0.5 + 0.5 * (time.time() % 1))
                        console.print(f"[yellow]API overloaded or rate limited. Retrying in {backoff_time:.1f} seconds...[/yellow]")
                        time.sleep(backoff_time)
                    else:
                        console.print(f"[red]Error in API call after {max_retries} attempts: {str(e)}[/red]")
                        return f"Error in API call: {str(e)}", total_tool_calls
                else:
                    # For other status errors, don't retry
                    console.print(f"[red]Error in API call: {str(e)}[/red]")
                    return f"Error in API call: {str(e)}", total_tool_calls
                    
            except Exception as e:
                # For general exceptions, don't retry
                console.print(f"[red]Error in API call: {str(e)}[/red]")
                return f"Error in API call: {str(e)}", total_tool_calls
        
        # If we've exhausted all retries without success or exception
        if 'response' not in locals():
            error_msg = "Failed to get a response after multiple attempts"
            console.print(f"[red]{error_msg}[/red]")
            return error_msg, total_tool_calls

        # Extract text from response for return
        response_text = ""
        for block in response.content:
            if block.type == "text":
                console.print(f"[cyan]Claude:[/cyan] {block.text}")
                response_text += block.text

        # Update the final response text
        if response_text:
            final_response_text = response_text

        # Process any tool calls
        tool_calls = [block for block in response.content if block.type == "tool_use"]
        total_tool_calls += len(tool_calls)

        # If no tool calls, we're done!
        if not tool_calls:
            break

        # Add Claude's response to the messages
        messages.append({"role": "assistant", "content": response.content})

        # Process tool calls one at a time
        for tool in tool_calls:
            console.print(f"[blue]Tool Call:[/blue] {tool.name}({json.dumps(tool.input, indent=2)})")

            func = tool_functions.get(tool.name)
            if func:
                # Execute the tool
                output = func(tool.input)
                result_text = output.get("error") or output.get("result", "")
                console.print(f"[green]Tool Result:[/green] {result_text}")

                # Add the tool result to the messages
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool.id,
                        "content": result_text
                    }]
                })

    # Return the final response text
    return final_response_text, total_tool_calls