"""
Main entry point for the application.

This application uses Claude 3.7's thinking model to query a DuckDB database
containing parquet files. It defines tools for Claude to use via the Anthropic API's
tool calling capabilities, and uses LlamaIndex for additional functionality.

All analysis functionality is insular to the analysis module.
"""

import os
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

# Import only what we need from our modules
from analysis.agent import run_agent
from analysis.datasets import create_team_dataset, create_compact_dataset

# Initialize console for rich output
console = Console()

def main():
    parser = argparse.ArgumentParser(description="DuckDB Query Agent using Claude 3.7")

    # Define commands/subparsers
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Query command
    query_parser = subparsers.add_parser("query", help="Run a natural language query against the database")
    query_parser.add_argument("question", help="The natural language question to answer")
    query_parser.add_argument("--parquet", "-p", help="Path to parquet file", default="analysis/data/data.parquet")
    query_parser.add_argument("--max-tokens", "-m", help="Maximum tokens in response", type=int, default=4000)
    query_parser.add_argument("--thinking-budget", "-t", help="Budget for thinking tokens", type=int, default=1024)

    # Dataset creation command
    team_parser = subparsers.add_parser("team", help="Create a filtered dataset for a specific team")
    team_parser.add_argument("team_name", help="Name of the team to create dataset for")
    team_parser.add_argument("--parquet", "-p", help="Path to parquet file", default="analysis/data/data.parquet")
    team_parser.add_argument("--output", "-o", help="Output file path (optional)")

    # Compact dataset command
    compact_parser = subparsers.add_parser("compact", help="Create a compact representation of match data")
    compact_parser.add_argument("--parquet", "-p", help="Path to parquet file", default="analysis/data/data.parquet")
    compact_parser.add_argument("--format", "-f", help="Output format (compact, table, csv)", default="compact", choices=["compact", "table", "csv"])

    args = parser.parse_args()

    # Handle no arguments case - show help
    if not args.command:
        parser.print_help()
        return

    # Execute the appropriate command
    if args.command == "query":
        run_agent(args.question, args.parquet, args.max_tokens, args.thinking_budget)
    elif args.command == "team":
        create_team_dataset(args.team_name, args.parquet, args.output)
    elif args.command == "compact":
        create_compact_dataset(args.parquet, args.format)

if __name__ == "__main__":
    main()
