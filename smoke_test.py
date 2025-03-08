import os
import sys
import time
import anthropic
from rich.console import Console
from rich.panel import Panel

# This smoke test script exercises the core LLM flow (similar to what's used in Docker Compose and CLI)
# without requiring Docker. It directly calls the run_agent_with_memory function, which is a version of
# the same function used in CLI and Docker, but with support for conversation history.
#
# Usage:
#   uv run smoke_test.py                       # Run with default queries
#   uv run smoke_test.py "query1" "query2"...  # Run with custom queries
#
# The test performs:
# 1. An initial query using the first argument or a default query
# 2. Follow-up queries using subsequent arguments to test memory functionality
#
# This allows for rapid testing of the core functionality during development.

# Import the run_agent_with_memory function from our centralized agent module
from analysis.agent import run_agent_with_memory
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

def evaluate_response(response: str, tool_call_count: int):
    """Evaluate the quality and completeness of a response"""
    quality = "poor"
    completeness = "incomplete"

    # Length check
    if len(response.strip()) > 200:
        quality = "good"
    if len(response.strip()) > 500:
        quality = "excellent"

    # Check for incompleteness markers
    has_incomplete_indicators = any(indicator in response.lower() for indicator in INCOMPLETE_INDICATORS)

    # Check for completeness markers
    has_complete_indicators = any(indicator in response.lower() for indicator in COMPLETE_INDICATORS)

    # Check if a SQL query was actually executed (for data questions)
    contains_data = "data shows" in response.lower() or "results" in response.lower() or "found" in response.lower()

    if (has_complete_indicators or contains_data) and tool_call_count > 0:
        completeness = "complete"
    elif has_incomplete_indicators and not has_complete_indicators:
        completeness = "incomplete - promises analysis but doesn't deliver"
    elif tool_call_count == 0:
        completeness = "incomplete - no tools used"

    return quality, completeness

def main():
    # Ensure that ANTHROPIC_API_KEY is set
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[bold red]Error: Please set the ANTHROPIC_API_KEY environment variable.[/bold red]")
        return

    # Set the parquet file path as expected in the Docker Compose environment
    # Adjust this path as needed if running locally
    parquet_file = "/app/ui/data/data.parquet"
    if not os.path.exists(parquet_file):
        parquet_file = "analysis/data/data.parquet"
        if not os.path.exists(parquet_file):
            console.print(f"[bold red]Error: Could not find parquet file at {parquet_file}[/bold red]")
            return
        else:
            console.print(f"[bold green]Using parquet file at: {parquet_file}[/bold green]")

    # Get queries from command-line arguments or use defaults
    queries = []
    if len(sys.argv) > 1:
        queries = sys.argv[1:]
        console.print(f"[bold cyan]Running with {len(queries)} custom queries from command line[/bold cyan]")
    else:
        # Default queries if none provided - designed to test basic functionality
        queries = [
            "What is the schema of the soccer match dataset?",
            "Show me match statistics for the first 5 matches in the dataset.",
            "Which team had the most wins in the dataset?"
        ]
        console.print("[bold cyan]Running with default queries[/bold cyan]")

    if not queries:
        console.print("[bold red]Error: No queries provided.[/bold red]")
        return

    # Track metrics for each query
    responses = []
    response_metrics = []
    tool_calls_per_query = []

    # Run the initial query
    console.print("\n")
    console.print(Panel(
        "[bold white]SMOKE TEST: Running initial query[/bold white]",
        border_style="yellow",
        width=80
    ))

    first_query = queries[0]
    console.print(f"\n[bold magenta]Query:[/bold magenta] {first_query}")

    # Measure response time and tool calls
    start_time = time.time()
    tool_call_count = 0

    try:
        response1, tool_call_count = run_agent_with_memory(first_query, parquet_file)
        elapsed_time = time.time() - start_time

        # Store metrics
        responses.append(response1)
        quality, completeness = evaluate_response(response1, tool_call_count)
        response_metrics.append({
            "quality": quality,
            "completeness": completeness,
            "time": elapsed_time,
            "tool_calls": tool_call_count
        })
        tool_calls_per_query.append(tool_call_count)

        console.print(f"\n[bold blue]Response 1:[/bold blue] [bold green]({elapsed_time:.2f}s, quality: {quality}, completeness: {completeness}, tools: {tool_call_count})[/bold green]")
        console.print(Panel(
            response1,
            border_style="blue",
            width=80
        ))

    except Exception as e:
        console.print(f"[bold red]Error during first query: {e}[/bold red]")
        return

    # Build conversation history from the first exchange
    conversation_history = [
        {"role": "user", "content": [{"type": "text", "text": first_query}]},
        {"role": "assistant", "content": [{"type": "text", "text": response1.strip() if isinstance(response1, str) and response1.strip() else "No response provided."}]}
    ]

    # Add a short pause to let Claude "breathe" between requests
    time.sleep(1)

    # Run follow-up queries if provided
    for i, followup_query in enumerate(queries[1:], 2):
        console.print("\n")
        console.print(Panel(
            f"[bold white]SMOKE TEST: Running follow-up query #{i-1}[/bold white]",
            border_style="yellow",
            width=80
        ))

        console.print(f"\n[bold magenta]Follow-up Query:[/bold magenta] {followup_query}")

        # Reset tool call counter for this query
        tool_call_count = 0

        # Measure response time
        start_time = time.time()
        try:
            response, follow_up_tool_count = run_agent_with_memory(followup_query, parquet_file, conversation_history=conversation_history)
            elapsed_time = time.time() - start_time

            # Store metrics
            responses.append(response)
            quality, completeness = evaluate_response(response, follow_up_tool_count)
            response_metrics.append({
                "quality": quality,
                "completeness": completeness,
                "time": elapsed_time,
                "tool_calls": follow_up_tool_count
            })
            tool_calls_per_query.append(follow_up_tool_count)

            # Check for evidence that memory is working - see if the model references previous queries
            memory_words = ["previous", "earlier", "as mentioned", "we saw", "you asked", "before"]
            memory_score = "confirmed" if any(word in response.lower() for word in memory_words) else "undetected"

            console.print(f"\n[bold blue]Response {i}:[/bold blue] [bold green]({elapsed_time:.2f}s, quality: {quality}, completeness: {completeness}, tools: {follow_up_tool_count})[/bold green]")
            console.print(Panel(
                response,
                border_style="blue",
                width=80
            ))
            console.print(f"[bold yellow]Memory Retention:[/bold yellow] {memory_score}")

            # Add this exchange to the conversation history for the next query
            conversation_history.extend([
                {"role": "user", "content": [{"type": "text", "text": followup_query}]},
                {"role": "assistant", "content": [{"type": "text", "text": response.strip() if isinstance(response, str) and response.strip() else "No response provided."}]}
            ])

            # Add a short pause to let Claude "breathe" between requests
            time.sleep(1)

        except Exception as e:
            console.print(f"[bold red]Error during follow-up query #{i-1}: {e}[/bold red]")
            return

    # Calculate overall success metrics
    incomplete_responses = sum(1 for m in response_metrics if m["completeness"] == "incomplete")
    avg_tool_calls = sum(tool_calls_per_query) / len(tool_calls_per_query) if tool_calls_per_query else 0
    test_success = "SUCCESS" if incomplete_responses == 0 and avg_tool_calls > 0 else "PARTIAL SUCCESS" if incomplete_responses < len(queries) / 2 else "NEEDS IMPROVEMENT"

    console.print("\n")
    console.print(Panel(
        f"[bold white]SMOKE TEST COMPLETED: {len(queries)} queries processed - {test_success}[/bold white]\n" +
        f"[bold white]Incomplete Responses: {incomplete_responses}/{len(queries)}[/bold white]\n" +
        f"[bold white]Average Tool Calls: {avg_tool_calls:.1f} per query[/bold white]",
        border_style="green" if test_success == "SUCCESS" else "yellow" if test_success == "PARTIAL SUCCESS" else "red",
        width=80
    ))


if __name__ == "__main__":
    main()