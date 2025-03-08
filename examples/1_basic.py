"""
Basic example for the soccer agent.

This is a simple example that runs a few basic queries to verify the agent works.
"""

import os
import sys
from examples import BaseSmokeTest, console

class BasicSmokeTest(BaseSmokeTest):
    """Basic smoke test for the soccer agent."""

    def __init__(self, parquet_file: str = "analysis/data/data.parquet"):
        """Initialize the basic smoke test."""
        super().__init__(parquet_file)

    def run_default_tests(self):
        """Run a set of default test queries."""
        queries = [
            "How did Key West perform in their last 5 games?",
            "What teams had the most goals scored in January 2025?",
            "Who was Key West's toughest opponent?"
        ]

        console.print("[bold magenta]Running Basic Smoke Test with Default Queries[/bold magenta]\n")
        self.run_queries(queries)


def main():
    """Run the basic smoke test."""
    # Ensure that ANTHROPIC_API_KEY is set
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable is not set.[/red]")
        sys.exit(1)

    # Create and run the basic smoke test
    smoke_test = BasicSmokeTest()

    # If arguments were provided, use them as queries
    if len(sys.argv) > 1:
        smoke_test.run_from_args()
    else:
        # Otherwise run the default test queries
        smoke_test.run_default_tests()


if __name__ == "__main__":
    main()