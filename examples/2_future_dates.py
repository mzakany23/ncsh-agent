"""
Future date queries example.

This example focuses on testing how the agent handles queries about future dates,
which is a common edge case that requires special handling.
"""

import os
import sys
import importlib

# Import from base module using importlib
base_module = importlib.import_module(".0_base", package="examples")
BaseSmokeTest = base_module.BaseSmokeTest
console = base_module.console

class FutureDates(BaseSmokeTest):
    """Tests for future date queries."""

    def __init__(self, parquet_file: str = "analysis/data/data.parquet"):
        """Initialize the future dates example."""
        super().__init__(parquet_file)

    def run_default_tests(self):
        """Run a set of default future date queries."""
        queries = [
            "How did Key West do in 2025 Feb?",
            "Show me Key West's matches in December 2025",
            "What teams are playing in March 2026?",
            "Who has the most wins in the 2026 season?",
            "What is Key West's win/loss record for January 2025?"  # This might be in the dataset
        ]

        console.print("[bold magenta]Running Future Dates Queries[/bold magenta]\n")
        self.run_queries(queries)


def main():
    """Run the future dates example."""
    # Ensure that ANTHROPIC_API_KEY is set
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable is not set.[/red]")
        sys.exit(1)

    # Create and run the future dates example
    example = FutureDates()

    # If arguments were provided, use them as queries
    if len(sys.argv) > 1:
        example.run_from_args()
    else:
        # Otherwise run the default test queries
        example.run_default_tests()


if __name__ == "__main__":
    main()