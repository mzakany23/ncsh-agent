"""
Main entry point for the application.

This application uses Claude 3.7's thinking model to query a DuckDB database
containing parquet files. It defines tools for Claude to use via the Anthropic API's
tool calling capabilities, and uses LlamaIndex for additional functionality.

All analysis functionality is insular to the analysis module.
"""

import os
import sys
import json
import argparse
from typing import Dict, List, Any, Optional
import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

# Import tool definitions and implementations from our modules
from analysis.tools.claude_tools import (
    get_claude_tools,
    get_tool_mapping, 
    complete_task
)
from analysis.duckdb_analyzer import (
    execute_sql,
    get_schema,
    validate_sql,
    query_to_sql,
    DuckDBAnalyzer
)

# Initialize console for rich output
console = Console()

def run_agent(question: str, parquet_file: str, max_tokens: int = 4000, thinking_budget_tokens: int = 2000):
    """
    Run the agent to process a natural language question about data in the parquet file.
    
    Args:
        question: The natural language question to answer
        parquet_file: Path to the parquet file
        max_tokens: Maximum number of tokens in the response
        thinking_budget_tokens: Budget for thinking tokens
    """
    # Get API key from environment variable
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable is not set.[/red]")
        sys.exit(1)
        
    # Verify the parquet file exists
    if not os.path.exists(parquet_file):
        console.print(f"[red]Error: Parquet file {parquet_file} does not exist.[/red]")
        console.print("[yellow]Tip: Use 'make refresh-data' to download data from AWS S3.[/yellow]")
        sys.exit(1)
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Define the system prompt with tools
    system_prompt = """
    <purpose>
        You are an expert data analyst that can query DuckDB databases using SQL.
    </purpose>
    
    <instructions>
        <workflow>
            For EVERY user question, ALWAYS follow these steps in order:
            1. First, call the get_schema tool to understand the database structure
            2. Write appropriate SQL queries to answer the user's question
            3. Call the validate_sql tool to check your SQL syntax
            4. ALWAYS call the execute_sql tool to get actual match data
            5. Format an answer based on the query results
            6. Call complete_task only when you have a final data-driven answer
        </workflow>
        
        <response_requirements>
            1. ALWAYS execute SQL queries - never just describe what you could do
            2. Answer with SPECIFIC DATA from the executed SQL results
            3. Include actual numbers, scores, dates, team names, etc. from the query results
            4. Format tables or lists to make results easy to read
            5. For team performance questions, ALWAYS include:
               - Wins/losses/draws record
               - Goals scored vs. conceded
               - Relevant match dates and opponents
        </response_requirements>
        
        <advanced_query_handling>
            When processing natural language queries, be aware of these special considerations:
            
            1. Time references - Handle relative time references ("this month", "last week", etc.) by 
               translating them to absolute date ranges based on the current date. For example, "this month" 
               should use the current month and year from the system time.
               
            2. Team names and variants - Sports teams may appear with variations in names (e.g., "Key West FC" 
               and "Key West FC (1)"). When a user asks about a team, consider checking for all possible 
               variations of that team name in the data.
               
            3. Ambiguous entities - If an entity mentioned in the query could refer to multiple distinct 
               entities in the database, identify all possible matches and consider them in your analysis.
               
            4. Natural aggregations - Queries like "how did team X do" should be interpreted as requests 
               for win/loss records, scores, and other performance metrics. ALWAYS INCLUDE ACTUAL DATA.
        </advanced_query_handling>
    </instructions>
    """
    
    # Get tools for the agent from the claude_tools module
    tools = get_claude_tools()
    
    # Import date module for context
    from datetime import datetime
    
    # Get current date information
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month
    current_day = current_date.day
    
    # Prepare the initial message with date context
    initial_message = f"""I need to analyze data in a parquet file. 
    
    TODAY'S DATE: {current_date.strftime('%Y-%m-%d')}
    
    My question is: {question}
    
    The parquet file is located at: {parquet_file}
    
    IMPORTANT: When processing time-related terms like 'this month', 'last week', etc., 
    use the current date specified above as reference. Also, when searching for teams, 
    be aware that team names might have variations (e.g., 'Team Name' and 'Team Name (1)') 
    and should be considered the same entity for analysis purposes.
    """
    
    messages = [{"role": "user", "content": initial_message}]
    
    # Map tool names to their corresponding functions
    tool_functions = get_tool_mapping()
    
    max_iterations = 10
    current_iteration = 0
    
    # Begin the agent loop
    while current_iteration < max_iterations:
        current_iteration += 1
        console.rule(f"[yellow]Agent Loop {current_iteration}/{max_iterations}[/yellow]")
        
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
        except Exception as e:
            console.print(f"[red]Error in API call: {str(e)}[/red]")
            break
        
        # Log the API response with rich formatting
        console.print(
            Panel(
                Syntax(
                    json.dumps(response.model_dump(), indent=2), 
                    "json",
                    theme="monokai",
                    word_wrap=True,
                ),
                title="[bold green]API Response[/bold green]",
                border_style="green",
            )
        )
        
        # Extract and print the thinking block if present
        thinking_blocks = [
            block for block in response.content if block.type == "thinking"
        ]
        if thinking_blocks:
            console.print(
                Panel(
                    thinking_blocks[0].thinking,
                    title="[bold blue]Claude's Thinking Process[/bold blue]",
                    border_style="blue",
                )
            )
        
        # Handle text blocks
        text_blocks = [
            block for block in response.content if block.type == "text"
        ]
        for block in text_blocks:
            console.print(f"[cyan]Claude:[/cyan] {block.text}")
        
        # Process tool calls
        tool_calls = [
            block
            for block in response.content
            if block.type == "tool_use"
        ]
        
        if tool_calls:
            # Add the assistant's response to messages
            messages.append({"role": "assistant", "content": response.content})
            
            for tool in tool_calls:
                console.print(f"[blue]Tool Call:[/blue] {tool.name}({json.dumps(tool.input)})")
                func = tool_functions.get(tool.name)
                if func:
                    # Execute the appropriate tool function
                    output = func(tool.input)
                        
                    result_text = output.get("error") or output.get("result", "")
                    console.print(f"[green]Tool Result:[/green] {result_text}")
                    
                    # Format the tool result message according to Claude API requirements
                    tool_result_message = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool.id,
                                "content": result_text,
                            }
                        ],
                    }
                    messages.append(tool_result_message)
                    if tool.name == "complete_task":
                        console.print("[green]Task completed. Exiting agent loop.[/green]")
                        return
                else:
                    raise ValueError(f"Unknown tool: {tool.name}")
        else:
            # No tool calls, just continue the conversation
            messages.append({"role": "assistant", "content": response.content})
            # Add user's next message
            user_input = input("Your response (or press Enter to exit): ")
            if not user_input.strip():
                break
            messages.append({"role": "user", "content": user_input})
    
    console.print("[yellow]Reached iteration limit or user exited.[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="DuckDB Query Agent using Claude 3.7")
    parser.add_argument("-q", "--question", required=True, help="Natural language question to ask about the data")
    parser.add_argument("-f", "--file", required=True, help="Path to the parquet file")
    parser.add_argument("--max_tokens", type=int, default=4000, help="Maximum number of tokens in the response")
    parser.add_argument("--thinking_budget", type=int, default=2000, help="Budget for thinking tokens")
    
    args = parser.parse_args()
    
    run_agent(
        question=args.question,
        parquet_file=args.file,
        max_tokens=args.max_tokens,
        thinking_budget_tokens=args.thinking_budget
    )


if __name__ == "__main__":
    main()
