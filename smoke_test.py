import os

# This smoke test script exercises the core LLM flow (similar to what's used in Docker Compose)
# without requiring Docker. It directly calls the run_agent_once function which is the same
# function used by the Streamlit app in Docker.
#
# The test performs:
# 1. An initial query about the schema
# 2. A follow-up query using conversation history to test memory functionality
#
# This allows for rapid testing of the core functionality during development.

from ui.streamlit_agent import run_agent_once


def main():
    # Ensure that ANTHROPIC_API_KEY is set
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: Please set the ANTHROPIC_API_KEY environment variable.")
        return

    # Set the parquet file path as expected in the Docker Compose environment
    # Adjust this path as needed if running locally
    parquet_file = "/app/ui/data/data.parquet"
    if not os.path.exists(parquet_file):
        parquet_file = "analysis/data/data.parquet"
        if not os.path.exists(parquet_file):
            print(f"Error: Could not find parquet file at {parquet_file}")
            return
        else:
            print(f"Using parquet file at: {parquet_file}")

    print("\n" + "="*80)
    print("SMOKE TEST: Running initial query")
    print("="*80)

    # First query
    first_query = "What is the schema of the soccer match dataset?"
    print(f"\nQuery: {first_query}")
    try:
        response1 = run_agent_once(first_query, parquet_file)
        print("\nResponse 1:")
        print("-"*50)
        print(response1)
        print("-"*50)
    except Exception as e:
        print(f"Error during first query: {e}")
        return

    # Build conversation history from the first exchange using correct block formats
    conversation_history = [
        {"role": "user", "content": [{"type": "text", "text": first_query}]},
        {"role": "assistant", "content": [{"type": "text", "text": response1.strip() if isinstance(response1, str) and response1.strip() else "No response provided."}]}
    ]

    print("\n" + "="*80)
    print("SMOKE TEST: Running follow-up query (testing memory)")
    print("="*80)

    # Follow-up query using conversation history to test memory
    followup_query = "Based on that schema, how many columns are present and what are their data types?"
    print(f"\nFollow-up Query: {followup_query}")
    try:
        response2 = run_agent_once(followup_query, parquet_file, conversation_history=conversation_history)
        print("\nResponse 2:")
        print("-"*50)
        print(response2)
        print("-"*50)
    except Exception as e:
        print(f"Error during follow-up query: {e}")
        return

    print("\n" + "="*80)
    print("SMOKE TEST COMPLETED SUCCESSFULLY")
    print("="*80)


if __name__ == "__main__":
    main()