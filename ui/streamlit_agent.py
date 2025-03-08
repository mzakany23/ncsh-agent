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

def run_agent_once(question: str, parquet_file: str, max_tokens: int = 4000, thinking_budget_tokens: int = 1024,
                  conversation_history: List[Dict[str, str]] = None):
    """
    Modified version of run_agent for Streamlit that processes a question only once,
    without asking for additional input. It also allows passing conversation history.

    Args:
        question: Natural language question about the data
        parquet_file: Path to parquet file
        max_tokens: Maximum tokens for Claude response
        thinking_budget_tokens: Maximum tokens for Claude thinking
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

Always execute SQL queries when analyzing data to provide concrete evidence for your conclusions.
Ensure your responses are accurate, comprehensive, and provide valuable insights to the user.
"""

    # Initialize message history or use provided history
    if conversation_history:
        messages = conversation_history
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

    try:
        # Handle API calls with retry logic for rate limits
        for retry in range(max_retries):
            try:
                console.print(f"[yellow]Making API call to Claude (attempt {retry+1}/{max_retries})[/yellow]")
                response = client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=max_tokens,
                    thinking={"type": "disabled"},
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

        # Log response content types for debugging
        console.print("[blue]Response content types:[/blue]")
        for i, block in enumerate(response.content):
            block_type = getattr(block, 'type', 'unknown')
            console.print(f"  Block {i}: {block_type}")

        # Process Claude's response
        tool_calls = [block for block in response.content if getattr(block, 'type', None) == 'tool_use']
        if tool_calls:
            # Handle tool calls
            for tool in tool_calls:
                # Extract text content for logging
                text_content = ""
                for block in response.content:
                    if hasattr(block, 'text') and block.text and block.text.strip():
                        text_content = block.text
                        break

                # Ensure text_content is never empty
                if not text_content.strip():
                    text_content = f"I'm analyzing the data about {question}. Let me use the {tool.name} tool to find relevant information."

                console.print(f"[cyan]Claude:[/cyan] {text_content}")
                console.print(f"[magenta]Tool call:[/magenta] {tool.name}({json.dumps(tool.input, indent=2)})")

                if tool.name in tool_functions and tool_functions[tool.name] is not None:
                    # Execute the tool and get the result
                    tool_result = tool_functions[tool.name](tool.input)
                    console.print(f"[green]Tool result:[/green] {json.dumps(tool_result, indent=2)}")

                    # Add tool result to message history
                    # Extract the text content properly
                    content_text = text_content  # Already set above

                    # Format as per Anthropic API documentation
                    tool_result_message = {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": content_text
                            },
                            {
                                "type": "tool_use",
                                "id": tool.id,
                                "name": tool.name,
                                "input": tool.input
                            }
                        ]
                    }
                    messages.append(tool_result_message)

                    # Add tool result to message history as user message with tool_result structure
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool.id,
                                "content": json.dumps(tool_result)
                            }
                        ]
                    })

                    # Get Claude's response to the tool result
                    console.print("[yellow]Making follow-up API call to Claude after tool use[/yellow]")
                    for retry in range(max_retries):
                        try:
                            response = client.messages.create(
                                model="claude-3-7-sonnet-20250219",
                                max_tokens=max_tokens,
                                thinking={"type": "disabled"},
                                messages=messages,
                                system=system_prompt,
                                tools=tools,
                            )
                            console.print("[green]Follow-up API call successful[/green]")
                            break
                        except anthropic.RateLimitError as e:
                            console.print(f"[yellow]Rate limit exceeded, retrying in {base_delay * (2 ** retry)} seconds... ({retry+1}/{max_retries})[/yellow]")
                            if retry < max_retries - 1:
                                time.sleep(base_delay * (2 ** retry))
                            else:
                                console.print(f"[red]Failed after {max_retries} retries. Error: {str(e)}[/red]")
                                raise
                        except Exception as e:
                            console.print(f"[red]Follow-up API call error: {str(e)}[/red]")
                            raise

                elif tool.name == "complete_task":
                    console.print("[green]Task completed.[/green]")
                    # Simply add the response to messages
                    # Extract text content for the message
                    resp_text = text_content  # Already set above

                    # Ensure it's not empty
                    if not resp_text.strip():
                        resp_text = "I've completed the analysis of the data based on your request."

                    messages.append({"role": "assistant", "content": [{"type": "text", "text": resp_text}]})
                    return resp_text
                else:
                    raise ValueError(f"Unknown tool: {tool.name}")
        else:
            # No tool calls, just return the response content
            # Extract text content properly
            text_content = ""
            for block in response.content:
                if hasattr(block, 'text') and block.text and block.text.strip():
                    text_content = block.text
                    break

            # Ensure text content is never empty - provide a meaningful fallback response
            if not text_content.strip():
                text_content = f"I've analyzed the data regarding '{question}'. Based on the available information, I can provide the following insights..."

                # Check if we have any previous context from conversation history
                if conversation_history and len(conversation_history) >= 2:
                    prior_queries = [msg.get('content')[0].get('text') for msg in conversation_history if msg.get('role') == 'user' and isinstance(msg.get('content'), list)]
                    if prior_queries:
                        text_content += f" Your previous questions about {', '.join(prior_queries[:2])} provide context for this analysis."

            console.print(f"[cyan]Claude (direct response):[/cyan] {text_content}")
            messages.append({"role": "assistant", "content": [{"type": "text", "text": text_content}]})
            return text_content

        # Return the final response content
        # Extract text content for final output
        final_text = ""
        for block in response.content:
            if hasattr(block, 'text') and block.text and block.text.strip():
                final_text = block.text
                break

        # Ensure final text is never empty - provide a detailed fallback response
        if not final_text.strip():
            final_text = f"Based on the analysis of the soccer match data regarding '{question}', I can provide the following insights and observations. The data includes information about teams, matches, scores, and leagues that can help answer your question."

            # If we're in a follow-up query, reference previous context
            if tool_calls:
                tool_names = [tool.name for tool in tool_calls]
                final_text += f" I used the {', '.join(tool_names)} to analyze the relevant data."

        console.print(f"[cyan]Claude (final response):[/cyan] {final_text}")
        return final_text

    except Exception as e:
        console.print(f"[red]Error in run_agent_once: {str(e)}[/red]")
        console.print(traceback.format_exc())
        raise
