"""
Examples package for the NC Soccer Agent.

This package contains example scripts and tools for working with the agent.
It provides a way to test the agent with different queries and scenarios.

Usage:
    python -m examples                      # Run the basic example
    python -m examples.1_basic              # Run the basic example
    python -m examples.2_future_dates       # Run the future dates example
    python -m examples "<query>"            # Run a specific query
"""

import os
import sys
import time
import argparse
from typing import List, Dict, Tuple, Optional
import anthropic
from rich.console import Console
from rich.panel import Panel

# Import the run_agent_with_memory function from our centralized agent module
from analysis.agent import run_agent_with_memory, update_conversation_history
from analysis.prompts import ANALYSIS_SYSTEM_PROMPT

# Initialize rich console for colored output
console = Console()

# Keywords that indicate incomplete responses
INCOMPLETE_INDICATORS = [
    "let me check", "now let me", "i'll search", "i will check", "i'll now look", "i will look",
    "let's explore", "i'll explore", "i'll find", "i will find"
]

# Phrases that indicate completed analysis
COMPLETE_INDICATORS = [
    "the analysis shows", "based on the data", "the results show", "i found that",
    "according to the data", "the query results", "data reveals", "data indicates"
]

class BaseSmokeTest:
    """Base class for smoke tests and examples."""

    def __init__(self, parquet_file: str = "analysis/data/data.parquet"):
        """
        Initialize the smoke test with the specified parquet file.

        Args:
            parquet_file: Path to the parquet file to use for testing
        """
        self.parquet_file = parquet_file

        # Ensure the parquet file exists
        if not os.path.exists(self.parquet_file):
            console.print(f"[red]Error: Parquet file {self.parquet_file} does not exist.[/red]")
            console.print("[yellow]Tip: Use 'make refresh-data' to download data from AWS S3.[/yellow]")
            sys.exit(1)

        console.print(f"Using parquet file at: {self.parquet_file}")

        # Initialize metrics
        self.total_queries = 0
        self.incomplete_responses = 0
        self.total_tool_calls = 0

        # Initialize conversation history
        self.conversation_history = None

    def evaluate_response(self, response: str, tool_call_count: int) -> Tuple[str, str]:
        """
        Evaluate the quality and completeness of a response.

        Args:
            response: The response text to evaluate
            tool_call_count: Number of tool calls made during the response

        Returns:
            Tuple of (quality, completeness)
        """
        quality = "poor"
        completeness = "incomplete"

        # Length check
        if len(response.strip()) > 200:
            quality = "good"
        if len(response.strip()) > 500:
            quality = "excellent"

        # Check for indicators of incomplete responses
        response_lower = response.lower()

        # If the response ends with one of the incomplete indicators, mark it as incomplete
        for phrase in INCOMPLETE_INDICATORS:
            if response_lower.strip().endswith(phrase) or response_lower.strip().endswith(phrase + "."):
                completeness = "incomplete - promises more but doesn't deliver"
                break

        # Check for presence of complete indicators
        for phrase in COMPLETE_INDICATORS:
            if phrase in response_lower:
                completeness = "complete"
                break

        # If the response is very short, it's likely incomplete
        if len(response.strip()) < 100:
            completeness = "incomplete - too brief"

        # If "I'll analyze" is in the response but no actual analysis follows, mark as incomplete
        if "i'll analyze" in response_lower and not any(phrase in response_lower for phrase in COMPLETE_INDICATORS):
            completeness = "incomplete - promises analysis but doesn't deliver"

        # Determine if the response is valid based on completeness
        if completeness == "complete":
            self.incomplete_responses += 0
        else:
            self.incomplete_responses += 1

        # Track tool calls
        self.total_tool_calls += tool_call_count

        return quality, completeness

    def run_query(self, query: str) -> Tuple[str, float, int]:
        """
        Run a single query and return the response.

        Args:
            query: The query to run

        Returns:
            Tuple of (response_text, response_time, tool_call_count)
        """
        console.print(f"Query: {query}")

        # Track time
        start_time = time.time()

        # Run the query with the simplified approach
        response_text, tool_call_count = run_agent_with_memory(
            question=query,
            parquet_file=self.parquet_file,
            conversation_history=self.conversation_history
        )

        # Update conversation history using the helper function from agent module
        self.conversation_history = update_conversation_history(
            self.conversation_history,
            question=query if self.conversation_history is None else None,
            response=response_text
        )

        # Calculate response time
        response_time = time.time() - start_time

        # Increment total queries
        self.total_queries += 1

        return response_text, response_time, tool_call_count

    def print_summary(self):
        """Print a summary of the smoke test results."""
        if self.total_queries == 0:
            console.print("[yellow]No queries were processed.[/yellow]")
            return

        # Determine overall success based on incomplete responses
        success_status = "SUCCESS" if self.incomplete_responses == 0 else "NEEDS IMPROVEMENT"

        # Calculate average tool calls per query
        avg_tool_calls = self.total_tool_calls / self.total_queries if self.total_queries > 0 else 0

        # Print summary
        console.print(Panel(
            f"[bold]SMOKE TEST COMPLETED: {self.total_queries} queries processed - {success_status}[/bold]\n"
            f"Incomplete Responses: {self.incomplete_responses}/{self.total_queries}\n"
            f"Average Tool Calls: {avg_tool_calls:.1f} per query",
            title="[bold green]Test Summary[/bold green]" if success_status == "SUCCESS" else "[bold yellow]Test Summary[/bold yellow]",
            border_style="green" if success_status == "SUCCESS" else "yellow",
        ))

    def run_queries(self, queries: List[str]):
        """
        Run a list of queries and print the results.

        Args:
            queries: List of queries to run
        """
        total_time = 0
        for i, query in enumerate(queries):
            console.print(f"\n[bold cyan]─" * 35 + f" SMOKE TEST: Running {'initial' if i == 0 else f'follow-up query {i}'}" + "─" * 35 + "[/bold cyan]")

            # Reset conversation history for each query - this makes the smoke test more reliable
            # by preventing conversation history issues from affecting follow-up queries
            self.conversation_history = None

            # Run query and get results
            response, response_time, tool_call_count = self.run_query(query)
            total_time += response_time

            # Evaluate the response
            quality, completeness = self.evaluate_response(response, tool_call_count)

            # Increment incomplete response count if applicable
            if "incomplete" in completeness.lower():
                self.incomplete_responses += 1

            # Track total tool calls
            self.total_tool_calls += tool_call_count

            # Print formatted response
            console.print(
                Panel(
                    response,
                    title=f"Response {i+1}: ({response_time:.2f}s, quality: {quality}, completeness: {completeness}, tools: {tool_call_count})",
                    expand=False
                )
            )

        # Print summary after all queries
        self.print_summary()

    def run_from_args(self, args: Optional[List[str]] = None):
        """
        Run queries from command-line arguments.

        Args:
            args: Command-line arguments (defaults to sys.argv[1:])
        """
        if args is None:
            args = sys.argv[1:]

        # Default queries if none provided
        if not args:
            queries = ["How did Key West perform in the last month?"]
        else:
            queries = args

        console.print(f"Running with {len(queries)} custom queries from command line\n")

        # Run all queries
        self.run_queries(queries)

# Import example classes using importlib for numeric file prefixes
import importlib
basic_module = importlib.import_module(".1_basic", package="examples")
future_dates_module = importlib.import_module(".2_future_dates", package="examples")

# Extract classes from modules
BasicSmokeTest = basic_module.BasicSmokeTest
FutureDates = future_dates_module.FutureDates

__all__ = [
    'BaseSmokeTest',
    'BasicSmokeTest',
    'FutureDates',
    'run',
    'console'
]

def run():
    """
    Main function to run examples from the command line.

    By default, runs the basic example, but can also run other examples
    or specific queries passed as command-line arguments.
    """
    parser = argparse.ArgumentParser(description="NC Soccer Agent Examples")
    parser.add_argument("query", nargs="*", help="Optional query to run. If not provided, runs the default example.")
    parser.add_argument("--example", "-e", choices=["basic", "future_dates"], default="basic",
                      help="Which example to run (default: basic)")
    args = parser.parse_args()

    # Ensure ANTHROPIC_API_KEY is set
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable is not set.[/red]")
        sys.exit(1)

    # Select the example to run
    if args.example == "basic":
        example = BasicSmokeTest()
    elif args.example == "future_dates":
        example = FutureDates()
    else:
        console.print(f"[red]Unknown example: {args.example}[/red]")
        sys.exit(1)

    # Run with queries if provided, otherwise run default tests
    if args.query:
        example.run_queries(args.query)
    else:
        example.run_default_tests()

# If this module is run directly, execute the main function
if __name__ == "__main__":
    run()