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

def run_agent(question: str, parquet_file: str, max_tokens: int = 4000, thinking_budget_tokens: int = 1024) -> str:
    """
    Run the agent to process a natural language question about data in the parquet file.

    Args:
        question: The natural language question to answer
        parquet_file: Path to the parquet file
        max_tokens: Maximum number of tokens in the response
        thinking_budget_tokens: Budget for thinking tokens

    Returns:
        The agent's response as a string
    """
    response_text, _ = run_agent_with_memory(question, parquet_file, max_tokens, thinking_budget_tokens)
    return response_text


def run_agent_with_memory(question: str, parquet_file: str, max_tokens: int = 4000,
                          thinking_budget_tokens: int = 1024,
                          conversation_history=None) -> Tuple[str, int]:
    """
    A version of run_agent that supports externally passed conversation history.
    This is primarily used for testing and situations where the conversation flow
    is managed externally (like in the smoke test).

    Args:
        question: The natural language question to answer
        parquet_file: Path to the parquet file
        max_tokens: Maximum number of tokens in the response
        thinking_budget_tokens: Budget for thinking tokens
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

    # Process a single iteration
    console.print(f"[yellow]Making API call to Claude (attempt 1/{max_retries})[/yellow]")

    try:
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=max_tokens,
            thinking={"type": "enabled", "budget_tokens": thinking_budget_tokens},
            messages=messages,
            system=system_prompt,
            tools=tools,
        )
        console.print("[green]API call successful[/green]")
    except Exception as e:
        console.print(f"[red]Error in API call: {str(e)}[/red]")
        return f"Error in API call: {str(e)}", 0

    # Extract text from response for return
    response_text = ""
    for block in response.content:
        if block.type == "text":
            console.print(f"[cyan]Claude:[/cyan] {block.text}")
            response_text += block.text
        elif block.type == "thinking":
            console.print(f"[blue]Claude (thinking):[/blue] {block.thinking}")

    # Process any tool calls
    tool_calls = [block for block in response.content if block.type == "tool_use"]
    total_tool_calls = len(tool_calls)

    if tool_calls:
        # Process each tool call
        for tool in tool_calls:
            console.print(f"[blue]Tool Call:[/blue] {tool.name}({json.dumps(tool.input, indent=2)})")

            func = tool_functions.get(tool.name)
            if func:
                # Execute the tool
                output = func(tool.input)
                result_text = output.get("error") or output.get("result", "")
                console.print(f"[green]Tool Result:[/green] {result_text}")

                # Add the tool call and result to messages
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool.id,
                        "content": result_text
                    }]
                })

                # Get Claude's response to the tool result
                try:
                    console.print(f"[yellow]Making follow-up API call to Claude[/yellow]")
                    follow_up_response = client.messages.create(
                        model="claude-3-7-sonnet-20250219",
                        max_tokens=max_tokens,
                        thinking={"type": "enabled", "budget_tokens": thinking_budget_tokens},
                        messages=messages,
                        system=system_prompt,
                        tools=tools,
                    )
                    console.print("[green]Follow-up API call successful[/green]")

                    # Extract text from the follow-up response
                    follow_up_text = ""
                    for block in follow_up_response.content:
                        if block.type == "text":
                            console.print(f"[cyan]Claude (follow-up):[/cyan] {block.text}")
                            follow_up_text += block.text
                        elif block.type == "thinking":
                            console.print(f"[blue]Claude (thinking):[/blue] {block.thinking}")

                    # Update the response text with the follow-up text if any
                    if follow_up_text:
                        response_text = follow_up_text

                    # Check for more tool calls in the follow-up response
                    follow_up_tool_calls = [block for block in follow_up_response.content if block.type == "tool_use"]
                    if follow_up_tool_calls:
                        # Recursively handle more tool calls (simplified - just count them)
                        total_tool_calls += len(follow_up_tool_calls)

                except Exception as e:
                    console.print(f"[red]Error in follow-up API call: {str(e)}[/red]")

    return response_text, total_tool_calls