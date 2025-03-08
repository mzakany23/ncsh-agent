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
import argparse

# Import example classes from modules with proper Python-compatible imports
# Note: we need to use importlib for numeric module names
import importlib
base_module = importlib.import_module(".0_base", package="examples")
basic_module = importlib.import_module(".1_basic", package="examples")
future_dates_module = importlib.import_module(".2_future_dates", package="examples")

# Extract classes and objects from modules
BaseSmokeTest = base_module.BaseSmokeTest
console = base_module.console
BasicSmokeTest = basic_module.BasicSmokeTest
FutureDates = future_dates_module.FutureDates

__all__ = [
    'BaseSmokeTest',
    'BasicSmokeTest',
    'FutureDates',
    'run'
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