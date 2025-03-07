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
        console.print(f"Available files in /app: {os.listdir('/app')}")
        console.print(f"Available files in /app/analysis: {os.listdir('/app/analysis')}")
        console.print(f"Available files in /app/analysis/tools: {os.listdir('/app/analysis/tools')}")
        
        from analysis.tools.claude_tools import get_claude_tools as get_tools
        tools = get_tools()
        console.print(f"Successfully imported get_claude_tools from analysis.tools.claude_tools")
        return tools
    except Exception as e:
        console.print(f"[red]Error in get_claude_tools: {str(e)}[/red]")
        console.print(traceback.format_exc())
        # Fallback simple tools - these will at least allow the function to run
        from anthropic.types import Tool
        query_data_tool = Tool(
            name="query_data",
            description="Query data from the database",
            input_schema={"type": "object", "properties": {}}
        )
        execute_sql_tool = Tool(
            name="execute_sql",
            description="Execute SQL query",
            input_schema={"type": "object", "properties": {}}
        )
        complete_task_tool = Tool(
            name="complete_task",
            description="Complete the task",
            input_schema={"type": "object", "properties": {}}
        )
        return [query_data_tool, execute_sql_tool, complete_task_tool]

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
    
    # Base system prompt
    system_prompt = f"""You are a data analyst agent who helps answer questions about soccer match data.
    
You have access to tools to help analyze data stored in a parquet file at '{parquet_file}'.

When referring to specific teams, use their full, exact names as they appear in the data.
Include all relevant information in your answers, and present data in tables when appropriate.
"""
    
    # Initialize message history or use provided history
    if conversation_history:
        messages = conversation_history
    else:
        messages = [
            {"role": "user", "content": question}
        ]
    
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
                response = client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=max_tokens,
                    thinking={
                        "type": "enabled",
                        "budget_tokens": thinking_budget_tokens,
                    },
                    messages=messages,
                    system=system_prompt,
                    tools=tools,
                )
                break  # Exit retry loop on success
            except anthropic.RateLimitError as e:
                console.print(f"[yellow]Rate limit exceeded, retrying in {base_delay * (2 ** retry)} seconds... ({retry+1}/{max_retries})[/yellow]")
                if retry < max_retries - 1:
                    time.sleep(base_delay * (2 ** retry))  # Exponential backoff
                else:
                    console.print(f"[red]Failed after {max_retries} retries. Error: {str(e)}[/red]")
                    raise
        
        # Process Claude's response
        tool_calls = [block for block in response.content if getattr(block, 'type', None) == 'tool_use']
        if tool_calls:
            # Handle tool calls
            for tool in tool_calls:
                # Extract text content for logging
                text_content = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        text_content = block.text
                        break
                    
                console.print(f"[cyan]Claude:[/cyan] {text_content}")
                console.print(f"[magenta]Tool call:[/magenta] {tool.name}({tool.input})")
                
                if tool.name in tool_functions and tool_functions[tool.name] is not None:
                    # Execute the tool and get the result
                    tool_result = tool_functions[tool.name](tool.input)
                    console.print(f"[green]Tool result:[/green] {json.dumps(tool_result, indent=2)}")
                    
                    # Add tool result to message history
                    # Extract the text content properly
                    content_text = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            content_text = block.text
                            break
                        elif hasattr(block, 'thinking'):
                            # Skip thinking blocks
                            continue
                    
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
                    for retry in range(max_retries):
                        try:
                            response = client.messages.create(
                                model="claude-3-7-sonnet-20250219",
                                max_tokens=max_tokens,
                                thinking={
                                    "type": "enabled",
                                    "budget_tokens": thinking_budget_tokens,
                                },
                                messages=messages,
                                system=system_prompt,
                                tools=tools,
                            )
                            break
                        except anthropic.RateLimitError as e:
                            console.print(f"[yellow]Rate limit exceeded, retrying in {base_delay * (2 ** retry)} seconds... ({retry+1}/{max_retries})[/yellow]")
                            if retry < max_retries - 1:
                                time.sleep(base_delay * (2 ** retry))
                            else:
                                console.print(f"[red]Failed after {max_retries} retries. Error: {str(e)}[/red]")
                                raise
                elif tool.name == "complete_task":
                    console.print("[green]Task completed.[/green]")
                    # Simply add the response to messages
                    # Extract text content for the message
                    resp_text = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            resp_text = block.text
                            break
                    
                    messages.append({"role": "assistant", "content": resp_text})
                    return resp_text
                else:
                    raise ValueError(f"Unknown tool: {tool.name}")
        else:
            # No tool calls, just return the response content
            # Extract text content properly
            text_content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    text_content = block.text
                    break
                elif hasattr(block, 'thinking'):
                    # Skip thinking blocks
                    continue
                    
            messages.append({"role": "assistant", "content": text_content})
            return text_content
            
        # Return the final response content
        # Extract text content for final output
        final_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                final_text = block.text
                break
        
        console.print(f"[cyan]Claude:[/cyan] {final_text}")
        return final_text
        
    except Exception as e:
        console.print(f"[red]Error in run_agent_once: {str(e)}[/red]")
        console.print(traceback.format_exc())
        raise
