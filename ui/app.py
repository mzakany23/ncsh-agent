"""
NC Soccer Hudson - Match Analysis Agent

Welcome to the Match Analysis Agent! This tool lets you analyze soccer match data
using natural language questions, providing insights about team performance, player
statistics, match outcomes, and trends.
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
import uuid
import glob
from urllib.parse import urlencode
import pandas as pd

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

# Define utility functions for conversation management
def get_conversations_dir():
    """Get the directory where conversations are stored."""
    ui_dir = os.path.dirname(os.path.abspath(__file__))
    conversations_dir = os.path.join(ui_dir, "conversations")
    os.makedirs(conversations_dir, exist_ok=True)
    return conversations_dir

def save_conversation(conversation_id, title, messages, dataset_context=None):
    """Save a conversation to disk."""
    conversations_dir = get_conversations_dir()

    # Create a unique filename based on the conversation ID
    filename = os.path.join(conversations_dir, f"{conversation_id}.json")

    # Format the conversation data
    conversation_data = {
        "id": conversation_id,
        "title": title,
        "messages": messages,
        "dataset_context": dataset_context,
        "last_updated": datetime.now().isoformat(),
        "created_at": datetime.now().isoformat() if not os.path.exists(filename) else None
    }

    # Save to disk
    with open(filename, "w") as f:
        json.dump(conversation_data, f, indent=2)

    logger.info(f"Saved conversation {conversation_id} to {filename}")
    return filename

def load_conversation(conversation_id):
    """Load a conversation from disk."""
    conversations_dir = get_conversations_dir()
    filename = os.path.join(conversations_dir, f"{conversation_id}.json")

    if not os.path.exists(filename):
        logger.error(f"Conversation file {filename} not found")
        return None

    try:
        with open(filename, "r") as f:
            conversation_data = json.load(f)

        # Update the last accessed time
        conversation_data["last_accessed"] = datetime.now().isoformat()
        with open(filename, "w") as f:
            json.dump(conversation_data, f, indent=2)

        logger.info(f"Loaded conversation {conversation_id} from {filename}")
        return conversation_data
    except Exception as e:
        logger.error(f"Error loading conversation {conversation_id}: {e}")
        return None

def list_conversations():
    """List all saved conversations, sorted by last updated time (newest first)."""
    conversations_dir = get_conversations_dir()
    conversation_files = glob.glob(os.path.join(conversations_dir, "*.json"))

    conversations = []
    for filename in conversation_files:
        try:
            with open(filename, "r") as f:
                conversation_data = json.load(f)

            # Extract the basic information
            conversations.append({
                "id": conversation_data.get("id", os.path.basename(filename).replace(".json", "")),
                "title": conversation_data.get("title", "Untitled Conversation"),
                "last_updated": conversation_data.get("last_updated", ""),
                "created_at": conversation_data.get("created_at", ""),
                "message_count": len(conversation_data.get("messages", [])),
                "has_dataset": conversation_data.get("dataset_context") is not None
            })
        except Exception as e:
            logger.error(f"Error reading conversation file {filename}: {e}")

    # Sort by last updated time (newest first)
    conversations.sort(key=lambda x: x["last_updated"], reverse=True)
    return conversations

def generate_conversation_title(messages, max_length=40):
    """Generate a title for a conversation based on its content."""
    if not messages:
        return "New Conversation"

    # Use the first user message as the title basis
    for msg in messages:
        if msg["role"] == "user":
            title = msg["content"]
            # Truncate and add ellipsis if too long
            if len(title) > max_length:
                title = title[:max_length] + "..."
            return title

    return "New Conversation"

# Initialize chat memory class -- MOVED EARLIER so it's defined before use
class StreamlitChatMemory:
    def __init__(self):
        self.memory = []
        self.dataset_context = None
        self.conversation_id = None
        self.conversation_title = "New Conversation"

    def add_message(self, role, content):
        self.memory.append({"role": role, "content": content})
        # Auto-save after each message if we have a conversation ID
        if self.conversation_id:
            self.save_conversation()

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
        # Don't clear conversation_id, we might want to reuse it

    def new_conversation(self):
        """Start a fresh conversation."""
        self.clear()
        self.conversation_id = str(uuid.uuid4())
        self.conversation_title = "New Conversation"
        return self.conversation_id

    def load_conversation(self, conversation_id):
        """Load a conversation from disk."""
        conversation_data = load_conversation(conversation_id)
        if conversation_data:
            self.memory = conversation_data.get("messages", [])
            self.dataset_context = conversation_data.get("dataset_context")
            self.conversation_id = conversation_id
            self.conversation_title = conversation_data.get("title", "Untitled Conversation")
            return True
        return False

    def save_conversation(self):
        """Save the current conversation to disk."""
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())

        # Generate a title if needed
        if self.conversation_title == "New Conversation" and self.memory:
            self.conversation_title = generate_conversation_title(self.memory)

        return save_conversation(
            self.conversation_id,
            self.conversation_title,
            self.memory,
            self.dataset_context
        )

# Initialize session state for tracking URL query params
if "query_params" not in st.session_state:
    st.session_state.query_params = {}

# Initialize parquet file path in session state
if "parquet_file" not in st.session_state:
    st.session_state.parquet_file = os.environ.get("PARQUET_FILE", "/app/ui/data/data.parquet")

# Function to get the current URL query parameters
def get_query_params():
    # Get query parameters from URL
    query_params = st.query_params.to_dict()
    return query_params

# Function to update URL with current conversation
def set_conversation_in_url(conversation_id):
    # Update the URL with the current conversation ID
    if conversation_id:
        st.query_params["conversation"] = conversation_id
    else:
        # Clear the conversation parameter if None
        st.query_params.clear()

# Function to load a conversation based on query parameters
def load_conversation_from_url():
    query_params = get_query_params()
    conversation_id = query_params.get("conversation")

    if conversation_id:
        logger.info(f"Loading conversation from URL query parameter: {conversation_id}")
        if st.session_state.memory.load_conversation(conversation_id):
            # Update the messages for display
            st.session_state.messages = st.session_state.memory.get_messages()
            logger.info(f"Successfully loaded conversation from URL: {st.session_state.memory.conversation_title}")
            return True
        else:
            logger.error(f"Failed to load conversation from URL with ID: {conversation_id}")
            # If conversation doesn't exist, clear the URL parameter
            st.query_params.clear()
            return False
    return False

# Initialize page configuration
st.set_page_config(
    page_title="NC Soccer Match Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize memory in session state if it doesn't exist
if 'memory' not in st.session_state:
    st.session_state.memory = StreamlitChatMemory()
    # We'll wait to assign a conversation ID until we check URL params

# Initialize message history in session state if it doesn't exist
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Initialize conversation list in session state
if 'conversations' not in st.session_state:
    st.session_state.conversations = list_conversations()

# Check URL parameters for conversation ID and load if present
if not st.session_state.memory.conversation_id:
    # First try to load from URL
    url_loading_success = load_conversation_from_url()

    # If no conversation in URL or loading failed, load most recent conversation
    if not url_loading_success:
        conversations = list_conversations()
        if conversations:
            # Load the most recent conversation
            most_recent_id = conversations[0]["id"]
            logger.info(f"Loading most recent conversation: {most_recent_id}")
            if st.session_state.memory.load_conversation(most_recent_id):
                st.session_state.messages = st.session_state.memory.get_messages()
                # Update URL with the conversation ID
                set_conversation_in_url(most_recent_id)
            else:
                # If loading fails, create a new conversation
                st.session_state.memory.new_conversation()
                set_conversation_in_url(st.session_state.memory.conversation_id)
        else:
            # No previous conversations, create a new one
            st.session_state.memory.new_conversation()
            set_conversation_in_url(st.session_state.memory.conversation_id)

# Streamlit UI components
st.title("⚽ NC Soccer Hudson - Match Analysis Agent")

# Sidebar for configuration
st.sidebar.title("⚙️ Configuration")

# Input for parquet file path
parquet_file = st.sidebar.text_input(
    "Parquet File Path",
    st.session_state.parquet_file,   # Use the session state value
    help="Path to the parquet file containing the soccer data. Default is the Docker container path."
)

# Update session state with the new value if changed
if parquet_file != st.session_state.parquet_file:
    st.session_state.parquet_file = parquet_file

# Add a note about the data source
st.sidebar.markdown("""
### Data Source
The application uses a parquet file containing soccer match data. The data is automatically refreshed from S3 when the container starts.
""")

# Load the parquet file
try:
    df = pd.read_parquet(st.session_state.parquet_file)
    st.sidebar.success(f"Successfully loaded data from {st.session_state.parquet_file}")
except Exception as e:
    st.sidebar.error(f"Error loading parquet file: {str(e)}")
    st.stop()

# Add conversation management to the sidebar
st.sidebar.markdown("---")
st.sidebar.title("💬 Conversation Management")

# Get the current list of conversations
conversations = list_conversations()

# Display current conversation info
if st.session_state.memory.conversation_id:
    # Show message count
    msg_count = len(st.session_state.memory.get_messages())
    st.sidebar.markdown(f"**Current Conversation**: {st.session_state.memory.conversation_title}")
    st.sidebar.markdown(f"Messages: {msg_count}")

# Add selectbox for all conversations
if conversations:
    # Format the conversation options for the selectbox
    conversation_options = []
    for conv in conversations:
        # Format the date for display
        try:
            last_updated = datetime.fromisoformat(conv["last_updated"]).strftime("%m/%d/%Y %I:%M %p")
        except:
            last_updated = "Unknown date"

        # Add message count to display
        msg_count = conv.get("message_count", 0)
        msg_text = f"{msg_count} message{'s' if msg_count != 1 else ''}"

        # Create a display string with title, date and message count
        display_text = f"{conv['title']} ({last_updated}) - {msg_text}"
        conversation_options.append({"id": conv["id"], "display": display_text})

    # Find the current conversation in the list for default selection
    current_index = 0
    for i, conv in enumerate(conversation_options):
        if conv["id"] == st.session_state.memory.conversation_id:
            current_index = i
            break

    # Create the selectbox for conversations
    selected_conversation_index = st.sidebar.selectbox(
        "Select Conversation",
        range(len(conversation_options)),
        format_func=lambda i: conversation_options[i]["display"],
        index=current_index
    )

    selected_conversation_id = conversation_options[selected_conversation_index]["id"]

    # Only show the load button if a different conversation is selected
    if selected_conversation_id != st.session_state.memory.conversation_id:
        if st.sidebar.button("Switch to Selected Conversation"):
            # Load the selected conversation
            if st.session_state.memory.load_conversation(selected_conversation_id):
                # Update the messages for display
                st.session_state.messages = st.session_state.memory.get_messages()
                # Update URL with new conversation ID
                set_conversation_in_url(selected_conversation_id)
                st.sidebar.success(f"Switched to: {st.session_state.memory.conversation_title}")
                # Rerun to refresh the UI
                st.rerun()
            else:
                st.sidebar.error("Failed to load conversation.")

# Create two columns for conversation actions
col1, col2 = st.sidebar.columns(2)

with col1:
    if st.button("New Conversation", use_container_width=True):
        # Create a new conversation
        new_id = st.session_state.memory.new_conversation()
        st.session_state.messages = []
        # Update URL with new conversation ID
        set_conversation_in_url(new_id)
        st.session_state.conversations = list_conversations()
        st.sidebar.success("New conversation started!")
        # Rerun to refresh the UI
        st.rerun()

with col2:
    if st.session_state.memory.conversation_id and st.button("Delete Current", use_container_width=True):
        if st.sidebar.checkbox("Confirm deletion"):
            # Delete the conversation file
            conversations_dir = get_conversations_dir()
            filename = os.path.join(conversations_dir, f"{st.session_state.memory.conversation_id}.json")
            try:
                current_id = st.session_state.memory.conversation_id
                os.remove(filename)
                # Find another conversation to load or create new
                other_conversations = [c for c in conversations if c["id"] != current_id]
                if other_conversations:
                    # Load another conversation
                    next_id = other_conversations[0]["id"]
                    st.session_state.memory.load_conversation(next_id)
                    st.session_state.messages = st.session_state.memory.get_messages()
                    set_conversation_in_url(next_id)
                else:
                    # Create a new conversation
                    new_id = st.session_state.memory.new_conversation()
                    st.session_state.messages = []
                    set_conversation_in_url(new_id)

                st.sidebar.success("Conversation deleted")
                # Refresh the conversation list
                st.session_state.conversations = list_conversations()
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error deleting conversation: {e}")

# Button to rename the current conversation
if st.session_state.memory.conversation_id and len(st.session_state.messages) > 0:
    new_title = st.sidebar.text_input("Rename Conversation", value=st.session_state.memory.conversation_title)
    if new_title != st.session_state.memory.conversation_title:
        if st.sidebar.button("Save New Title"):
            st.session_state.memory.conversation_title = new_title
            st.session_state.memory.save_conversation()
            st.sidebar.success("Conversation renamed!")
            # Update conversation list
            st.session_state.conversations = list_conversations()
            st.rerun()

# Button to save the current conversation manually
if st.session_state.memory.conversation_id and len(st.session_state.messages) > 0:
    if st.sidebar.button("Save Conversation"):
        st.session_state.memory.save_conversation()
        st.session_state.conversations = list_conversations()
        st.sidebar.success("Conversation saved!")

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Display welcome message and instructions when starting fresh
if not st.session_state.messages:
    st.markdown("""
    ### Welcome to the Match Analysis Agent!

    **How to use this tool:**

    1. **Ask Questions:** Type your questions about soccer matches in the input box below
    2. **Manage Conversations:** Save, rename, or switch between conversations using the sidebar controls

    **Features:**

    - **Team Analysis:** Ask about team performance, statistics, trends, and match outcomes
    - **Conversation History:** Your analysis discussions are saved and can be revisited

    **Example Questions:**
    - "How did Hudson perform in their last 5 matches?"
    - "Who scored the most goals this season?"
    - "What was the pass completion rate for the midfielders?"
    - "Compare home vs. away performance for Hudson"

    Start by asking a question below!
    """)

# Input for user question
if question := st.chat_input("Ask a question about the match data..."):
    # Add user message to history and display it
    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.memory.add_message("user", question)

    # If this is the first message, generate a title for the conversation
    if len(st.session_state.messages) == 1:
        st.session_state.memory.conversation_title = generate_conversation_title([{"role": "user", "content": question}])
        st.session_state.memory.save_conversation()
        # Update the conversation list
        st.session_state.conversations = list_conversations()

        # Update URL with the conversation ID (in case this is a new conversation)
        set_conversation_in_url(st.session_state.memory.conversation_id)

    with st.chat_message("user"):
        st.markdown(question)

    # Display assistant response with a spinner
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("Analyzing data..."):
            try:
                # Check if parquet file exists
                if not os.path.exists(st.session_state.parquet_file):
                    message_placeholder.error(f"Error: Parquet file {st.session_state.parquet_file} does not exist.")
                else:
                    # Get the conversation history as context
                    conversation_history = st.session_state.memory.get_messages_as_string()

                    # For the full agent mode, add the conversation history
                    if conversation_history and len(st.session_state.messages) > 2:
                        context = f"\n\nOur previous conversation (most recent first):\n{conversation_history}"
                        logger.info(f"Adding conversation context: {context[:200]}...")
                    else:
                        context = ""
                        logger.info("No conversation context added")

                    enriched_question = f"{question}{context}".strip()
                    logger.info(f"Final question being processed: {enriched_question[:100]}...")

                    # Use the run_agent function for analysis
                    # Format conversation history as a list of message objects for Claude API
                    formatted_conversation = []
                    if len(st.session_state.messages) > 1:
                        for msg in st.session_state.messages[:-1]:  # Exclude the current message
                            formatted_conversation.append({
                                "role": msg["role"],
                                "content": [{"type": "text", "text": msg["content"]}]
                            })

                    raw_output = run_agent_once(
                        enriched_question,
                        st.session_state.parquet_file,
                        max_tokens=4000,
                        conversation_history=formatted_conversation if formatted_conversation else None
                    )

                    # Process the output
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
                    response = re.sub(r'\[.*?\]', '', response)

                    # Summarize the raw response using Claude to make it user-friendly
                    try:
                        # Initialize the Anthropic client
                        api_key = os.environ.get("ANTHROPIC_API_KEY")
                        if not api_key:
                            logger.error("ANTHROPIC_API_KEY environment variable is not set")
                            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

                        client = anthropic.Anthropic(api_key=api_key)

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
                                "content": response
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

                    logger.info(f"Final formatted response length: {len(response)}")

                    # Update the message placeholder with the response
                    message_placeholder.markdown(response)

                    # Add assistant response to history
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.session_state.memory.add_message("assistant", response)

                    # Save the conversation
                    st.session_state.memory.save_conversation()
                    # Update conversation list and URL
                    st.session_state.conversations = list_conversations()
                    set_conversation_in_url(st.session_state.memory.conversation_id)

            except Exception as e:
                # Log detailed error for troubleshooting
                error_details = traceback.format_exc()
                logger.error(f"Error processing request: {str(e)}\n{error_details}")
                # Show a more user-friendly error message
                message_placeholder.error(f"Error processing your request: {str(e)}\n\nPlease try again or rephrase your question.")

# Footer
st.markdown("---")
st.markdown(
    "💡 **Tips for NC Soccer Hudson Match Analysis:** \n"
    "- **Team Analysis:** Ask specific questions about team performance and statistics\n"
    "- **Player Stats:** Ask about player performance metrics and achievements\n"
    "- **Match Insights:** For detailed match analysis, mention specific dates or opponents\n"
    "- **Remember:** Your conversations are saved and can be revisited later"
)
