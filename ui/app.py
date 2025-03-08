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
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core import Settings

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
        self.memory = ChatMemoryBuffer.from_defaults(token_limit=3900)

    def add_message(self, role, content):
        # MessageRole and ChatMessage are now imported at the module level

        if role == "user":
            message_role = MessageRole.USER
        elif role == "assistant":
            message_role = MessageRole.ASSISTANT
        else:
            message_role = MessageRole.SYSTEM

        self.memory.put(ChatMessage(role=message_role, content=content))

    def get_messages(self):
        return self.memory.get()

    def get_messages_as_string(self):
        messages = self.memory.get()
        result = ""
        for msg in messages:
            # Format the message in a way that's cleaner for the agent to process
            role_name = "User" if msg.role == MessageRole.USER else "Assistant"
            result += f"{role_name}: {msg.content}\n\n"
        return result

    def clear(self):
        self.memory.reset()

# Initialize memory in session state if it doesn't exist
if 'memory' not in st.session_state:
    st.session_state.memory = StreamlitChatMemory()

# Initialize message history in session state if it doesn't exist
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Button to clear chat history
if st.sidebar.button("Clear Chat History"):
    st.session_state.messages = []
    st.session_state.memory.clear()
    st.sidebar.success("Chat history cleared!")

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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

                    # Format the context in a cleaner way for the run_agent function
                    if conversation_history and len(st.session_state.messages) > 2:  # Only add history if we have a meaningful conversation
                        # Create a clear but compact conversation history for the agent
                        context = f"\n\nOur previous conversation (most recent first):\n{conversation_history}"
                        logger.info(f"Adding conversation context: {context[:200]}...")
                    else:
                        context = ""
                        logger.info("No conversation context added")

                    enriched_question = f"{question}{context}".strip()
                    logger.info(f"Final question being processed: {enriched_question[:100]}...")

                    # Use the run_agent function from cli.py as originally designed
                    import io
                    import sys
                    import re
                    import json

                    try:
                        # Log the question being processed
                        logger.info(f"Processing question with run_agent_once: {enriched_question[:100]}...")

                        # Prepare conversation history for the agent if this is a follow-up question
                        conversation_history = None
                        if len(st.session_state.messages) > 2:  # More than just the welcome message and current question
                            conversation_history = []
                            # Add previous exchanges as conversation history
                            for msg in st.session_state.messages[1:-1]:  # Skip welcome message and current question
                                conversation_history.append({
                                    "role": msg["role"],
                                    "content": msg["content"]
                                })
                            # Add current question
                            conversation_history.append({
                                "role": "user",
                                "content": enriched_question
                            })
                            logger.info(f"Added conversation history with {len(conversation_history)} messages")

                        # Run the agent with the question (non-interactive version)
                        response = run_agent_once(
                            enriched_question,
                            parquet_file,
                            max_tokens=4000,
                            conversation_history=conversation_history
                        )

                        # Set raw_output to the response for compatibility with existing code
                        raw_output = response
                        logger.info(f"Received response with {len(raw_output)} characters")
                        logger.info(f"Response preview: {raw_output[:200].replace(chr(10), ' ')}")

                        # Check if we got any output
                        if not raw_output or len(raw_output.strip()) == 0:
                            raise ValueError("No output was returned from the analysis. Please try again.")

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
                        raw_response = re.sub(r'\[.*?\]', '', response)

                        # Summarize the raw response using Claude to make it user-friendly
                        # Get API key from environment variable
                        api_key = os.environ.get("ANTHROPIC_API_KEY")
                        if not api_key:
                            logger.error("ANTHROPIC_API_KEY environment variable is not set.")
                            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")

                        # Initialize Claude client
                        client = anthropic.Anthropic(api_key=api_key)

                        # Create a system prompt for summarization
                        system_prompt = """
                        You are a soccer match analyst who provides clear, concise summaries of soccer match analysis.
                        Your task is to take the raw output from a data analysis process and convert it into a user-friendly
                        response that focuses only on the analysis results and insights, not the process.

                        Format your response using Markdown for better readability.
                        Include all relevant statistics from the original analysis.
                        Preserve any tables or charts from the original output.
                        Organize the information logically with clear headings and sections.
                        Remove any technical details about SQL queries, tooling, or processing steps.
                        Focus only on the soccer match insights that answer the user's question.
                        """

                        # Create a user prompt with the raw response
                        user_prompt = f"""
                        The following is the raw output from a soccer match analysis tool that contains both
                        the process (SQL queries, tool calls, etc.) and the actual analysis results.
                        Please summarize this into a clean, user-friendly response that only includes
                        the relevant soccer match analysis insights.

                        Original question: {question}

                        Raw output:
                        {raw_response}
                        """

                        try:
                            # Call Claude API to summarize the response
                            logger.info("Calling Claude to summarize the response")
                            claude_summary = client.messages.create(
                                model="claude-3-7-sonnet-20250219",
                                max_tokens=4000,
                                system=system_prompt,
                                messages=[{"role": "user", "content": user_prompt}]
                            )

                            # Extract the summarized response
                            response = claude_summary.content[0].text
                            logger.info(f"Received summarized response from Claude with {len(response)} characters")
                        except Exception as e:
                            logger.error(f"Error summarizing response with Claude: {str(e)}")
                            logger.error(traceback.format_exc())
                            # Fall back to the raw response if summarization fails
                            response = raw_response

                            # Ensure it's formatted as markdown
                            if not any(md_marker in response for md_marker in ['#', '|', '*', '-', '```']):
                                response = f"```\n{response}\n```"

                        logger.info(f"Final formatted response length: {len(response)}")

                    except Exception as e:
                        logger.error(f"Error processing question: {e}")
                        raise ValueError(f"An error occurred while analyzing the data: {str(e)}")

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
    "💡 **Tip:** For best results, ask specific questions about teams, matches, or statistics. "
    "Examples: 'How did Key West FC perform?', 'Show me the top 5 teams with the most goals', or "
    "'Create a dataset for Key West FC matches'."
)
