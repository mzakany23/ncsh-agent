"""
Streamlit UI for NC Soccer Agent

This application provides a user-friendly interface for querying soccer match data
using natural language questions powered by Claude 3.7.
"""

import os
import sys
import json
import logging
import traceback
import re
import io
import streamlit as st
from typing import Dict, List, Any, Optional
import anthropic
from datetime import datetime
import time

# Add parent directory to path to find modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    # Import the streamlit-compatible agent function
    from ui.streamlit_agent import run_agent_once
    logging.info("Successfully imported run_agent_once")
except ImportError as e:
    logging.error(f"Failed to import run_agent_once: {e}")
    logging.error(traceback.format_exc())
    logging.error(f"sys.path: {sys.path}")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("soccer-app")

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the run_agent function from the analysis package
from cli import run_agent

# Configure the page
st.set_page_config(
    page_title="NC Soccer Match Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Streamlit UI components
st.title("⚽ NC Soccer Match Analysis")
st.markdown("""
    Ask questions about soccer match data using natural language.
    This tool uses Claude 3.7 to analyze the data and provide insights.
""")

# Sidebar for configuration
st.sidebar.title("⚙️ Configuration")

# Input for Anthropic API key
api_key = st.sidebar.text_input(
    "Anthropic API Key",
    value=os.environ.get("ANTHROPIC_API_KEY", ""),
    type="password",
    help="Enter your Anthropic API key to enable Claude 3.7."
)

# Set the API key as an environment variable
if api_key:
    os.environ["ANTHROPIC_API_KEY"] = api_key

# Input for parquet file path
# Forcefully set known working path in Docker
default_paths = [
    "/app/ui/data/data.parquet",   # Based on Docker volume mount
    "/app/analysis/data/data.parquet",
    "../analysis/data/data.parquet",
    "data/data.parquet"
]

# Log all environment variables for debugging
logger.info("Environment variables:")
for key, value in os.environ.items():
    logger.info(f"{key}: {value}")

# Log current directory and its contents
current_dir = os.getcwd()
logger.info(f"Current directory: {current_dir}")
try:
    logger.info(f"Contents of current directory: {os.listdir(current_dir)}")
except Exception as e:
    logger.error(f"Error listing current directory: {e}")

# Try all possible paths and log results
default_parquet_path = os.environ.get("PARQUET_FILE", "/app/ui/data/data.parquet")
logger.info(f"Default parquet path from env: {default_parquet_path}")
valid_paths = []

for path in default_paths:
    try:
        exists = os.path.exists(path)
        logger.info(f"Checking path {path}: exists={exists}")
        if exists:
            # Try to open the file to confirm it's readable
            with open(path, 'rb') as f:
                f.read(10)  # Just read a few bytes to check
            logger.info(f"SUCCESS: Path {path} is readable")
            valid_paths.append(path)
    except Exception as e:
        logger.error(f"Error checking path {path}: {e}")

# Use the first valid path found
if valid_paths:
    default_parquet_path = valid_paths[0]
    logger.info(f"Using parquet file at: {default_parquet_path}")
else:
    logger.error("No valid parquet file paths found!")

parquet_file = st.sidebar.text_input(
    "Parquet File Path",
    value=default_parquet_path,
    help="Path to the parquet file containing match data."
)

# Initialize chat memory
class StreamlitChatMemory:
    def __init__(self):
        self.memory = []
        self.dataset_context = None

    def add_message(self, role, content):
        self.memory.append({"role": role, "content": content})

    def get_messages(self):
        return self.memory

    def get_messages_as_string(self):
        result = ""
        for msg in self.memory:
            # Format the message in a way that's cleaner for the agent to process
            role_name = "User" if msg["role"] == "user" else "Assistant"
            result += f"{role_name}: {msg['content']}\n\n"
        return result

    def set_dataset_context(self, context):
        self.dataset_context = context

    def get_dataset_context(self):
        return self.dataset_context

    def clear(self):
        self.memory = []
        self.dataset_context = None

# Initialize memory in session state if it doesn't exist
if 'memory' not in st.session_state:
    st.session_state.memory = StreamlitChatMemory()

# Initialize message history in session state if it doesn't exist
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Initialize selected dataset in session state if it doesn't exist
if 'selected_dataset' not in st.session_state:
    st.session_state.selected_dataset = None

# Function to find available datasets
def find_datasets():
    datasets = []
    # Check the ui/data directory
    ui_data_dir = os.path.join(os.path.dirname(__file__), 'data')
    if os.path.exists(ui_data_dir):
        for file in os.listdir(ui_data_dir):
            if file.endswith('.parquet'):
                datasets.append(os.path.join(ui_data_dir, file))

    # Check the analysis/data directory
    analysis_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'analysis', 'data')
    if os.path.exists(analysis_data_dir):
        for file in os.listdir(analysis_data_dir):
            if file.endswith('.parquet') and file != 'data.parquet':  # Exclude the main data file
                datasets.append(os.path.join(analysis_data_dir, file))

    # Check for datasets in the current directory
    for file in os.listdir('.'):
        if file.endswith('.parquet') and file != 'data.parquet':  # Exclude the main data file
            datasets.append(file)

    return datasets

# Function to create a dataset using create_llm_dataset
def create_dataset(team, format="table"):
    try:
        from analysis.tools.claude_tools import create_llm_dataset

        # Generate the dataset
        result = create_llm_dataset(
            reasoning=f"Creating a dataset for {team} to use in LLM context for chat",
            parquet_file=parquet_file,
            team=team,
            format=format
        )

        if "error" in result:
            return None, result["error"]

        # Save the formatted data to the context
        dataset_context = f"""
# {team} Team Dataset

{result.get('data', '')}

## Summary
- Total matches: {result.get('row_count', 'Unknown')}
- Dataset generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Team name: {team}
        """

        return dataset_context, None
    except Exception as e:
        logger.error(f"Error creating dataset: {e}")
        logger.error(traceback.format_exc())
        return None, str(e)

# Function to load a selected dataset file
def load_dataset_file(dataset_path):
    try:
        import pandas as pd

        # Load the parquet file
        df = pd.read_parquet(dataset_path)

        # Convert to a readable format
        team_name = os.path.basename(dataset_path).replace('_dataset.parquet', '').replace('_', ' ').title()

        # Create a nicely formatted markdown table
        if len(df) > 0:
            # Format the date column if it exists
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # Generate a markdown table with the first 20 rows
            table_rows = []
            for _, row in df.head(20).iterrows():
                table_rows.append(' | '.join([str(val) for val in row.values]))

            table_header = ' | '.join(df.columns)
            table_separator = ' | '.join(['---'] * len(df.columns))
            table = f"{table_header}\n{table_separator}\n" + '\n'.join(table_rows)

            dataset_context = f"""
# {team_name} Team Dataset

The dataset contains {len(df)} matches for {team_name}.

## Sample Data (first 20 matches)
{table}

## Summary
- Total matches: {len(df)}
- Dataset loaded from: {dataset_path}
- Dataset loaded at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """

            return dataset_context, None
        else:
            return None, "Dataset is empty"
    except Exception as e:
        logger.error(f"Error loading dataset: {e}")
        logger.error(traceback.format_exc())
        return None, str(e)

# Add dataset management to the sidebar
st.sidebar.markdown("---")
st.sidebar.title("🗃️ Dataset Management")

# Dataset creation section
st.sidebar.subheader("Create New Dataset")
team_name = st.sidebar.text_input("Team Name", value="", help="Enter a team name to create a dataset")
format_options = ["table", "compact", "simple"]
selected_format = st.sidebar.selectbox("Format", format_options, help="Select the format for the dataset")

if st.sidebar.button("Create Dataset"):
    if team_name:
        with st.sidebar.status("Creating dataset..."):
            dataset_context, error = create_dataset(team_name, selected_format)
            if error:
                st.sidebar.error(f"Error creating dataset: {error}")
            else:
                st.session_state.memory.set_dataset_context(dataset_context)
                st.session_state.selected_dataset = f"{team_name} (In-Memory)"
                st.sidebar.success(f"Dataset for {team_name} created successfully")
    else:
        st.sidebar.warning("Please enter a team name")

# Dataset selection section
st.sidebar.subheader("Select Existing Dataset")
datasets = find_datasets()
dataset_options = ["None"] + [os.path.basename(d) for d in datasets]
selected_dataset_name = st.sidebar.selectbox("Available Datasets", dataset_options, help="Select a dataset to load into context")

if selected_dataset_name != "None" and selected_dataset_name != st.session_state.selected_dataset:
    with st.sidebar.status(f"Loading dataset {selected_dataset_name}..."):
        # Find the full path of the selected dataset
        selected_dataset_path = next((d for d in datasets if os.path.basename(d) == selected_dataset_name), None)
        if selected_dataset_path:
            dataset_context, error = load_dataset_file(selected_dataset_path)
            if error:
                st.sidebar.error(f"Error loading dataset: {error}")
            else:
                st.session_state.memory.set_dataset_context(dataset_context)
                st.session_state.selected_dataset = selected_dataset_name
                st.sidebar.success(f"Dataset {selected_dataset_name} loaded successfully")

# Show the currently selected dataset
if st.session_state.selected_dataset:
    st.sidebar.info(f"Active Dataset: {st.session_state.selected_dataset}")
else:
    st.sidebar.info("No dataset selected")

# Button to clear the selected dataset
if st.sidebar.button("Clear Selected Dataset"):
    st.session_state.memory.set_dataset_context(None)
    st.session_state.selected_dataset = None
    st.sidebar.success("Dataset selection cleared")

# Button to clear chat history
if st.sidebar.button("Clear Chat History"):
    st.session_state.messages = []
    st.session_state.memory.clear()
    st.session_state.selected_dataset = None
    st.sidebar.success("Chat history cleared!")

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Display dataset context if selected (only when starting a new chat)
if st.session_state.memory.get_dataset_context() and not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(st.session_state.memory.get_dataset_context())
        # Add this initial context as the first message
        st.session_state.messages.append({"role": "assistant", "content": st.session_state.memory.get_dataset_context()})
        # Extract team name from context for potential SQL queries
        team_name = None
        context_lines = st.session_state.memory.get_dataset_context().split('\n')
        for line in context_lines:
            if line.startswith('# ') and 'Team Dataset' in line:
                team_name = line.replace('# ', '').replace(' Team Dataset', '').strip()
                break
        if team_name:
            st.session_state.team_name = team_name
        else:
            st.session_state.team_name = None

# Input for user question
if question := st.chat_input("Ask a question about the match data..."):
    # Add user message to history and display it
    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.memory.add_message("user", question)

    with st.chat_message("user"):
        st.markdown(question)

    # Display assistant response with a spinner
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("Analyzing data..."):
            try:
                # Check if parquet file exists
                if not os.path.exists(parquet_file):
                    message_placeholder.error(f"Error: Parquet file {parquet_file} does not exist.")
                else:
                    # Get the conversation history as context
                    conversation_history = st.session_state.memory.get_messages_as_string()

                    # Format the context differently if we have a dataset selected
                    if st.session_state.memory.get_dataset_context():
                        # Check if the question requires deep analysis with SQL
                        if requires_deep_analysis(question, st.session_state.memory.get_dataset_context()):
                            # For questions requiring comprehensive statistics, use the full agent pipeline
                            # Get team name from session state if available
                            team_name = getattr(st.session_state, 'team_name', None)

                            if team_name:
                                # Create a more specific question that includes the team name for the agent
                                enriched_question = f"Analyze and provide comprehensive statistics about {team_name}: {question}"
                                logger.info(f"Using full agent pipeline for statistical analysis about {team_name}")
                            else:
                                enriched_question = f"Analyze and provide comprehensive statistics: {question}"
                                logger.info("Using full agent pipeline for statistical analysis")

                            use_agent = True
                            with st.status("This question requires comprehensive analysis. Running full database query..."):
                                st.write("For detailed statistical analysis, we're querying the entire dataset.")
                                time.sleep(1)  # Brief pause to show the status message
                        else:
                            # For simple questions, use the dataset context
                            enriched_question = f"{question}"
                            use_agent = False
                            logger.info("Using dataset context mode for simple question")
                    else:
                        # For the full agent mode, add the conversation history
                        if conversation_history and len(st.session_state.messages) > 2:
                            context = f"\n\nOur previous conversation (most recent first):\n{conversation_history}"
                            logger.info(f"Adding conversation context: {context[:200]}...")
                        else:
                            context = ""
                            logger.info("No conversation context added")

                        enriched_question = f"{question}{context}".strip()
                        logger.info(f"Final question being processed: {enriched_question[:100]}...")
                        use_agent = True

                    # Use the run_agent function for full agent mode, or direct Claude call for dataset context mode
                    if use_agent:
                        # Prepare conversation history for the agent if this is a follow-up question
                        conversation_history = None
                        if len(st.session_state.messages) > 2:
                            conversation_history = []
                            # Add previous exchanges as conversation history
                            for msg in st.session_state.messages[1:-1]:
                                if msg["role"] == "user":
                                    conversation_history.append({
                                        "role": "user",
                                        "content": [{"type": "text", "text": msg["content"]}]
                                    })
                                else:
                                    conversation_history.append({
                                        "role": "assistant",
                                        "content": [{"type": "text", "text": msg["content"]}]
                                    })
                            # Add current question
                            conversation_history.append({
                                "role": "user",
                                "content": [{"type": "text", "text": enriched_question}]
                            })
                            logger.info(f"Added conversation history with {len(conversation_history)} messages")

                        # Run the agent with the question
                        raw_output = run_agent_once(
                            enriched_question,
                            parquet_file,
                            max_tokens=4000,
                            conversation_history=conversation_history
                        )
                    else:
                        # Direct Claude call for dataset mode
                        # Get API key from environment variable
                        api_key = os.environ.get("ANTHROPIC_API_KEY")
                        if not api_key:
                            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")

                        # Initialize Claude client
                        client = anthropic.Anthropic(api_key=api_key)

                        # Create a system prompt for dataset context mode
                        system_prompt = """
                        You are a soccer match analyst who provides analysis based on the dataset provided.
                        The user has loaded a specific dataset about a soccer team, and you should analyze
                        that data to answer their questions.

                        Format your response using Markdown for better readability.
                        Focus only on the data provided in the dataset context.
                        Organize the information logically with clear headings and sections.
                        If you cannot answer a question from the provided dataset, explain what information is missing
                        and suggest that the user could switch to a comprehensive statistics mode for full database analysis.
                        """

                        # Prepare the conversation history
                        messages = []

                        # Add the dataset context as system prompt addition
                        dataset_context = st.session_state.memory.get_dataset_context()
                        if dataset_context:
                            system_prompt += f"\n\nHere is the dataset context to use for analysis:\n{dataset_context}"

                        # Add previous messages for context
                        for msg in st.session_state.messages:
                            if msg["role"] == "user":
                                messages.append({
                                    "role": "user",
                                    "content": [{"type": "text", "text": msg["content"]}]
                                })
                            else:
                                # Skip the initial dataset context message to avoid duplication
                                if not (msg["role"] == "assistant" and msg["content"] == dataset_context):
                                    messages.append({
                                        "role": "assistant",
                                        "content": [{"type": "text", "text": msg["content"]}]
                                    })

                        # Call Claude API with context and question
                        logger.info(f"Calling Claude directly with dataset context")
                        claude_response = client.messages.create(
                            model="claude-3-7-sonnet-20250219",
                            max_tokens=4000,
                            system=system_prompt,
                            messages=messages
                        )

                        # Extract the response text
                        raw_output = claude_response.content[0].text
                        logger.info(f"Received dataset mode response from Claude with {len(raw_output)} characters")

                    # Process the output
                    if not raw_output or len(raw_output.strip()) == 0:
                        raise ValueError("No output was returned from the analysis. Please try again.")

                    # For the agent mode, we need to extract the Claude response
                    if use_agent:
                        # Extract the Claude response using regex patterns
                        claude_patterns = [
                            r'\[cyan\]Claude:\[/cyan\]\s*(.*?)(?=\[|$)',  # Rich formatted output
                            r'Claude:\s*([^\[\n].*?)(?=\n\n|$)',         # Plain format
                            r'Claude \([^)]+\):\s*(.*?)(?=\n\n|$)'     # Format with parentheses
                        ]

                        # Try to find all Claude responses
                        all_responses = []
                        for pattern in claude_patterns:
                            matches = re.finditer(pattern, raw_output, re.DOTALL)
                            for match in matches:
                                response_text = match.group(1).strip()
                                if response_text:
                                    all_responses.append(response_text)
                                    logger.info(f"Found Claude response with pattern {pattern[:20]}...")

                        # If we found Claude responses, join them together
                        if all_responses:
                            response = '\n\n'.join(all_responses)
                            logger.info(f"Combined {len(all_responses)} Claude responses")
                        else:
                            # Try a simpler approach - just look for content between specific markers
                            # This is a fallback for when the regex patterns don't match
                            start_marker = "[cyan]Claude:[/cyan]"
                            if start_marker in raw_output:
                                parts = raw_output.split(start_marker)
                                if len(parts) > 1:
                                    response = parts[1].strip()
                                    logger.info("Used fallback extraction method")
                                else:
                                    response = raw_output
                                    logger.info("Using raw output as response")
                            else:
                                response = raw_output
                                logger.info("No Claude markers found - using raw output")

                        # Clean up the response for better formatting
                        # Remove any remaining rich formatting marks
                        response = re.sub(r'\[.*?\]', '', response)

                        # Summarize the raw response using Claude to make it user-friendly
                        try:
                            # Call Claude API to summarize the response
                            logger.info("Calling Claude to summarize the response")
                            claude_summary = client.messages.create(
                                model="claude-3-7-sonnet-20250219",
                                max_tokens=4000,
                                system="""
                                You are a soccer match analyst who provides clear, concise summaries of soccer match analysis.
                                Your task is to take the raw output from a data analysis process and convert it into a user-friendly
                                response that focuses only on the analysis results and insights, not the process.

                                Format your response using Markdown for better readability.
                                Include all relevant statistics from the original analysis.
                                Preserve any tables or charts from the original output.
                                Organize the information logically with clear headings and sections.
                                Remove any technical details about SQL queries, tooling, or processing steps.
                                Focus only on the soccer match insights that answer the user's question.
                                """,
                                messages=[{
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": f"""
                                            The following is the raw output from a soccer match analysis tool that contains both
                                            the process (SQL queries, tool calls, etc.) and the actual analysis results.
                                            Please summarize this into a clean, user-friendly response that only includes
                                            the relevant soccer match analysis insights.

                                            Original question: {question}

                                            Raw output:
                                            {response}
                                            """
                                        }
                                    ]
                                }]
                            )

                            # Extract the summarized response
                            response = claude_summary.content[0].text
                            logger.info(f"Received summarized response from Claude with {len(response)} characters")
                        except Exception as e:
                            logger.error(f"Error summarizing response with Claude: {str(e)}")
                            logger.error(traceback.format_exc())
                            # Fall back to the raw response if summarization fails
                            # Ensure it's formatted as markdown
                            if not any(md_marker in response for md_marker in ['#', '|', '*', '-', '```']):
                                response = f"```\n{response}\n```"
                    else:
                        # For dataset mode, use the raw output directly
                        response = raw_output

                    logger.info(f"Final formatted response length: {len(response)}")

                    # Update the message placeholder with the response
                    message_placeholder.markdown(response)

                    # Add assistant response to history
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.session_state.memory.add_message("assistant", response)
            except Exception as e:
                # Log detailed error for troubleshooting
                error_details = traceback.format_exc()
                logger.error(f"Error processing request: {str(e)}\n{error_details}")
                # Show a more user-friendly error message
                message_placeholder.error(f"Error processing your request: {str(e)}\n\nPlease try again or rephrase your question.")

# Footer
st.markdown("---")
st.markdown(
    "💡 **Tip:** For best results with datasets, first select or create a dataset from the sidebar. "
    "Then ask specific questions about the dataset. For general questions, no dataset needs to be selected."
)

# Function to determine if a question requires statistical analysis beyond the loaded context
def requires_deep_analysis(question, dataset_context):
    """
    Determines if a question requires deep statistical analysis that would benefit from SQL queries
    rather than using the limited dataset context.
    """
    # Convert question to lowercase for easier matching
    question_lower = question.lower()

    # Keywords that suggest statistical analysis
    statistical_terms = [
        "most", "least", "biggest", "smallest", "highest", "lowest",
        "average", "mean", "median", "maximum", "minimum", "max", "min",
        "total", "count", "percentage", "ratio", "compare", "comparison",
        "all time", "ever", "all matches", "statistics", "stats", "record",
        "ranking", "ranked", "rank", "top", "bottom", "best", "worst"
    ]

    # Check if question contains statistical terms
    has_statistical_term = any(term in question_lower for term in statistical_terms)

    # If dataset context includes all matches (unlikely), we don't need deep analysis
    context_has_all_matches = False
    if dataset_context:
        lines = dataset_context.split('\n')
        for line in lines:
            if "Sample Data" in line and "(first 20 matches)" in line:
                context_has_all_matches = False
                break

    # If the question seems to require comprehensive statistics and context doesn't have all matches
    return has_statistical_term and not context_has_all_matches
