import os
import sys
import time
import json
import traceback
import anthropic
from rich.console import Console
from typing import Dict, List, Any, Optional

# Create console for pretty output
console = Console()

def get_claude_tools():
    """Get the tools for Claude from the claude_tools module."""
    try:
        import sys
        import os
        console.print(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
        console.print(f"sys.path: {sys.path}")
        console.print(f"Current directory: {os.getcwd()}")
        if os.path.exists('/app'):
            console.print(f"Available files in /app: {os.listdir('/app')}")
        else:
            console.print("'/app' directory not found; skipping listing.")
        if os.path.exists('/app/analysis'):
            console.print(f"Available files in /app/analysis: {os.listdir('/app/analysis')}")
        else:
            console.print("'/app/analysis' directory not found; skipping listing.")
        if os.path.exists('/app/analysis/tools'):
            console.print(f"Available files in /app/analysis/tools: {os.listdir('/app/analysis/tools')}")
        else:
            console.print("'/app/analysis/tools' directory not found; skipping listing.")

        from analysis.tools.claude_tools import get_claude_tools as get_tools
        tools = get_tools()
        console.print("Successfully imported get_claude_tools from analysis.tools.claude_tools")
        return tools
    except Exception as e:
        console.print(f"[red]Error in get_claude_tools: {str(e)}[/red]")
        console.print(traceback.format_exc())
        # Fallback simple tools - these will at least allow the function to run
        return [
            {"name": "query_data", "description": "Query data from the database", "input_schema": {"type": "object", "properties": {}}},
            {"name": "execute_sql", "description": "Execute SQL query", "input_schema": {"type": "object", "properties": {}}},
            {"name": "complete_task", "description": "Complete the task", "input_schema": {"type": "object", "properties": {}}}
        ]

def get_tool_mapping():
    """Map tool names to their corresponding functions."""
    try:
        from analysis.tools.claude_tools import get_tool_mapping as get_mapping
        mapping = get_mapping()
        console.print(f"Successfully imported get_tool_mapping from analysis.tools.claude_tools")
        return mapping
    except Exception as e:
        console.print(f"[red]Error in get_tool_mapping: {str(e)}[/red]")
        console.print(traceback.format_exc())
        # Fallback empty mapping that will allow the app to start
        return {"query_data": lambda x: {"result": "Error: Tool not available"},
                "execute_sql": lambda x: {"result": "Error: Tool not available"},
                "complete_task": None}

def run_agent_once(question: str, parquet_file: str, max_tokens: int = 4000,
                  conversation_history: List[Dict[str, str]] = None):
    """
    Modified version of run_agent for Streamlit that processes a question using the
    recursive tool approach.

    Args:
        question: Natural language question about the data
        parquet_file: Path to parquet file
        max_tokens: Maximum tokens for Claude response
        conversation_history: Optional list of previous messages

    Returns:
        The assistant's response text
    """
    # Get API key from environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    # Enhanced system prompt with specific instructions to be detailed and insightful
    system_prompt = f"""You are a data analyst agent who helps answer questions about soccer match data.

You have access to tools to help analyze data stored in a parquet file at '{parquet_file}'.

When referring to specific teams, use their full, exact names as they appear in the data.

RESPONSE GUIDELINES:
1. Always provide rich, detailed analysis with clear explanations
2. Format data as tables when appropriate for readability
3. Summarize findings in a way that's easy to understand
4. Include specific statistics, trends, and insights whenever possible
5. When no data is found, explain why and suggest alternatives
6. For team names that don't match exactly, use fuzzy_match_teams tool to find the closest matches
7. For complex queries, break down your analysis into multiple steps
8. IMPORTANT: When searching for teams like "Key West", make sure to search for all variations (Key West FC, Key West I, etc.) using pattern matching with ILIKE '%key west%'

Always execute SQL queries when analyzing data to provide concrete evidence for your conclusions.
Ensure your responses are accurate, comprehensive, and provide valuable insights to the user.
"""

    # Initialize message history or use provided history
    if conversation_history:
        # If conversation_history is a string, convert it to the proper format
        if isinstance(conversation_history, str):
            messages = [
                {"role": "user", "content": [{"type": "text", "text": question}]}
            ]
        # If it's already a list of messages, use it directly
        elif isinstance(conversation_history, list):
            messages = conversation_history
        else:
            # Default case if conversation_history is in an unexpected format
            messages = [
                {"role": "user", "content": [{"type": "text", "text": question}]}
            ]
    else:
        messages = [
            {"role": "user", "content": [{"type": "text", "text": question}]}
        ]

    # Debug: Print the current conversation history
    console.print("[blue]Conversation history:[/blue]")
    for i, msg in enumerate(messages):
        role = msg.get('role', 'unknown')
        content_summary = str(msg.get('content', ''))[:100] + '...' if len(str(msg.get('content', ''))) > 100 else str(msg.get('content', ''))
        console.print(f"  {i}: {role} -> {content_summary}")

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

    try:
        # Process messages recursively until Claude provides a complete response
        while True:
            # Handle API calls with retry logic for rate limits
            for retry in range(max_retries):
                try:
                    console.print(f"[yellow]Making API call to Claude (attempt {retry+1}/{max_retries})[/yellow]")
                    response = client.messages.create(
                        model="claude-3-7-sonnet-20250219",
                        max_tokens=max_tokens,
                        messages=messages,
                        system=system_prompt,
                        tools=tools,
                    )
                    console.print("[green]API call successful[/green]")
                    break  # Exit retry loop on success
                except anthropic.RateLimitError as e:
                    console.print(f"[yellow]Rate limit exceeded, retrying in {base_delay * (2 ** retry)} seconds... ({retry+1}/{max_retries})[/yellow]")
                    if retry < max_retries - 1:
                        time.sleep(base_delay * (2 ** retry))  # Exponential backoff
                    else:
                        console.print(f"[red]Failed after {max_retries} retries. Error: {str(e)}[/red]")
                        raise
                except Exception as e:
                    console.print(f"[red]API call error: {str(e)}[/red]")
                    raise

            # Extract text from response for return
            response_text = ""
            for block in response.content:
                if hasattr(block, 'text') and block.text:
                    console.print(f"[cyan]Claude:[/cyan] {block.text}")
                    response_text += block.text

            # Update the final response text
            if response_text:
                final_response_text = response_text

            # Process any tool calls
            tool_calls = [block for block in response.content if getattr(block, 'type', None) == 'tool_use']
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

                    # Add the tool result to messages
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool.id,
                            "content": result_text
                        }]
                    })

        # Return the final response text
        return final_response_text

    except Exception as e:
        console.print(f"[red]Error in run_agent_once: {str(e)}[/red]")
        console.print(traceback.format_exc())
        raise
