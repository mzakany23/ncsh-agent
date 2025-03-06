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

def run_agent(question: str, parquet_file: str, max_tokens: int = 4000, thinking_budget_tokens: int = 1024):
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
    
    # Import required modules
    from datetime import datetime
    import re, calendar, time
    from analysis.duckdb_analyzer import DuckDBAnalyzer
    
    # Define a more concise system prompt with tools
    system_prompt = """
    <purpose>
        You are an expert data analyst that uses SQL for DuckDB databases. ALWAYS use table name 'input_data'.
    </purpose>
    
    <instructions>
        <operations>
            DATA ANALYSIS: SQL queries (e.g., "How did Key West FC perform?") 
            DATASET CREATION: Create team datasets (e.g., "Create dataset for Key West FC")
            DATASET COMPACTION: Compact representations (e.g., "Compact the dataset in CSV format")
        </operations>
        
        <workflow>
            DATA ANALYSIS: 
            1. Use get_schema tool
            2. Write SQL queries with 'input_data' table
            3. Validate SQL, execute it, format results
            
            DATASET CREATION:
            1. Extract team name and call build_dataset tool
            
            DATASET COMPACTION:
            1. Use compact_dataset tool with requested format
        </workflow>
        
        <requirements>
            1. ALWAYS use 'input_data' as table name
            2. Include actual data and format results well
            3. For team performance: show wins/losses/draws, goals scored/conceded
            4. Handle team name variants (e.g., "Team" and "Team (1)") 
            5. For date ranges, use date column not match_date
        </requirements>
    </instructions>
    """
    
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
    
    messages = [{"role": "user", "content": initial_message}]
    
    # Map tool names to their corresponding functions
    tool_functions = get_tool_mapping()
    
    # Get tools for the agent from the claude_tools module
    tools = get_claude_tools()
    
    # Setup retry logic
    max_retries = 3
    base_delay = 5  # seconds
    client = anthropic.Anthropic(api_key=api_key)
    
    # Begin the agent loop
    max_iterations = 10
    current_iteration = 0
    
    while current_iteration < max_iterations:
        current_iteration += 1
        console.rule(f"[yellow]Agent Loop {current_iteration}/{max_iterations}[/yellow]")
        
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
                    return  # Exit the function if all retries failed
            except Exception as e:
                console.print(f"[red]Error in API call: {str(e)}[/red]")
                return  # Exit the function on other errors
        
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


def create_team_dataset(team: str, parquet_file: str, output_file: str = None):
    """
    Create a filtered dataset for a specific team and save it as a new parquet file.
    
    Args:
        team: The team name to filter the dataset by
        parquet_file: Path to the source parquet file
        output_file: Path to save the filtered dataset as a parquet file (optional)
    """
    if not output_file:
        # Generate output filename based on team name if not provided
        output_dir = os.path.dirname(parquet_file)
        team_slug = team.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')
        output_file = os.path.join(output_dir, f"{team_slug}_dataset.parquet")
    
    # Import the build_dataset function from the module
    from analysis.duckdb_analyzer import build_dataset
    
    # Build the dataset
    console.print(f"[yellow]Building dataset for team '{team}'...[/yellow]")
    result = build_dataset(team, parquet_file, output_file)
    
    if "error" in result:
        console.print(f"[red]Error building dataset: {result['error']}[/red]")
        return
    
    console.print(f"[green]Dataset built successfully![/green]")
    console.print(f"[green]Found {result['row_count']} matches involving {team}[/green]")
    console.print(f"[green]Dataset saved to: {result['output_file']}[/green]")
    
    return result

def create_compact_dataset(parquet_file: str, output_format: str = "compact"):
    """
    Create a compact representation of match data optimized for Claude's context window.
    
    Args:
        parquet_file: Path to the parquet file containing match data
        output_format: Format style ('compact', 'table', or 'csv')
    """
    # Import the compact_dataset function from the module
    from analysis.duckdb_analyzer import compact_dataset
    
    # Create compact representation
    console.print(f"[yellow]Creating compact dataset representation in '{output_format}' format...[/yellow]")
    result = compact_dataset(parquet_file, output_format)
    
    if "error" in result:
        console.print(f"[red]Error creating compact dataset: {result['error']}[/red]")
        return
    
    console.print(f"[green]Compact dataset created successfully![/green]")
    console.print(f"[green]Processed {result['row_count']} matches[/green]")
    console.print(f"[green]Original size: {result['original_size_bytes']} bytes[/green]")
    console.print(f"[green]Compact size: {result['compact_size_bytes']} bytes[/green]")
    console.print(f"[green]Compression ratio: {result['compression_ratio']}[/green]")
    
    # Print the compact dataset
    syntax = Syntax(result['result'], "text", theme="monokai", line_numbers=True, word_wrap=True)
    console.print(
        Panel(
            syntax,
            title=f"[bold]Compact Dataset ({output_format} format)[/bold]",
            border_style="green",
        )
    )
    
    return result

def main():
    parser = argparse.ArgumentParser(description="DuckDB Query Agent using Claude 3.7")
    
    # Unified interface - everything goes through run_agent
    parser.add_argument("-q", "--question", required=True, help="Natural language question or request for the agent")
    parser.add_argument("-f", "--file", required=True, help="Path to the parquet file")
    parser.add_argument("--max_tokens", type=int, default=4000, help="Maximum number of tokens in the response")
    parser.add_argument("--thinking_budget", type=int, default=1024, help="Budget for thinking tokens")
    
    args = parser.parse_args()
    
    # All operations go through run_agent, which will let Claude determine which tool to use
    run_agent(
        question=args.question,
        parquet_file=args.file,
        max_tokens=args.max_tokens,
        thinking_budget_tokens=args.thinking_budget
    )


if __name__ == "__main__":
    main()
