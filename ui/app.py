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

            # Check if there's a dataset context and update the selected dataset
            if st.session_state.memory.get_dataset_context():
                dataset_context = st.session_state.memory.get_dataset_context()
                # Extract team name from context for potential SQL queries
                team_name = None
                context_lines = dataset_context.split('\n')
                for line in context_lines:
                    if line.startswith('# ') and 'Team Dataset' in line:
                        team_name = line.replace('# ', '').replace(' Team Dataset', '').strip()
                        break
                if team_name:
                    st.session_state.team_name = team_name
                    st.session_state.selected_dataset = team_name
                else:
                    st.session_state.team_name = None
            else:
                st.session_state.selected_dataset = None

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

# Initialize selected dataset in session state if it doesn't exist
if 'selected_dataset' not in st.session_state:
    st.session_state.selected_dataset = None

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

# Input for Anthropic API key - REMOVED
# API key will be set via environment variable as documented in README

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
    logger.info(f"Using default parquet file at: {default_parquet_path}")
else:
    logger.error("No valid parquet file paths found!")

# Store default parquet path in session state for reference
if 'default_parquet_path' not in st.session_state:
    st.session_state.default_parquet_path = default_parquet_path

# Initialize parquet_file in session state to use the default
if 'parquet_file' not in st.session_state:
    st.session_state.parquet_file = default_parquet_path

# Function to determine if a question requires statistical analysis beyond the loaded context
def requires_deep_analysis(question, dataset_context):
    """
    Determines if a question requires deep statistical analysis that would benefit from SQL queries
    rather than using the limited dataset context.

    When a dataset is loaded, we want to prioritize using that dataset first for most questions,
    and only switch to deep analysis for questions that clearly require data beyond what's in the dataset.
    """
    # Convert question to lowercase for easier matching
    question_lower = question.lower()

    # If the question is specifically asking about the loaded dataset, never use deep analysis
    dataset_reference_terms = [
        "this dataset", "the dataset", "these matches", "these games", "this data",
        "the data", "loaded dataset", "the information here", "what's shown", "what is shown",
        "from this"
    ]
    if any(term in question_lower for term in dataset_reference_terms):
        return False

    # Keywords that suggest statistical analysis across ALL matches (beyond the loaded dataset)
    global_statistical_terms = [
        "all time", "ever", "all matches", "all games", "every match", "every game",
        "career", "history", "historically", "overall", "across all",
        "league-wide", "season total", "compared to all"
    ]

    # Check if question contains global statistical terms
    has_global_term = any(term in question_lower for term in global_statistical_terms)

    # Keywords that suggest comparative analysis beyond what's in this dataset
    comparative_terms = [
        "compared to", "versus", "vs", "against all", "relative to",
        "better than", "worse than", "rank among", "ranking among", "compared with",
        "league average", "other teams", "all other", "everyone else"
    ]

    # Check if question contains comparative terms that might require broader context
    has_comparative_term = any(term in question_lower for term in comparative_terms)

    # If dataset context includes enough matches (like full season data), we don't need deep analysis for most questions
    has_comprehensive_data = False
    has_limited_sample = False
    if dataset_context:
        # Check how many matches are in the dataset
        match_count_pattern = r'Total matches: (\d+)'
        match_count_match = re.search(match_count_pattern, dataset_context)
        if match_count_match:
            match_count = int(match_count_match.group(1))
            # If the dataset has a significant number of matches, it's probably adequate for most questions
            if match_count > 20:
                has_comprehensive_data = True
            else:
                has_limited_sample = True

        # Also check if only showing a sample
        sample_indicator = "Sample Data (first 20 matches)"
        if sample_indicator in dataset_context:
            has_limited_sample = True

    # Basic statistical terms that can usually be answered from the loaded dataset if it's comprehensive
    basic_stat_terms = [
        "most", "least", "biggest", "smallest", "highest", "lowest",
        "best", "worst", "average", "mean", "total", "count"
    ]

    # If the question uses basic statistical terms but not global or comparative terms,
    # and we have comprehensive data, try to answer from the dataset
    has_basic_stat_term = any(term in question_lower for term in basic_stat_terms)

    # Only use deep analysis if:
    # 1. The question has global/comparative terms suggesting data beyond this dataset, OR
    # 2. The question has statistical terms AND the dataset is just a limited sample
    return (has_global_term or has_comparative_term or
            (has_basic_stat_term and has_limited_sample and not has_comprehensive_data))

# Function to find available datasets
def find_datasets():
    datasets = []
    # Track datasets by filename to avoid duplicates
    seen_filenames = set()
    # Add the default dataset first
    default_dataset_name = "Main Dataset (default)"
    default_added = False

    # Check the ui/data directory first (most likely to have user-created datasets)
    ui_data_dir = os.path.join(os.path.dirname(__file__), 'data')
    if os.path.exists(ui_data_dir):
        for file in os.listdir(ui_data_dir):
            if file.endswith('.parquet'):
                filename = os.path.basename(file)
                # Skip if we've already seen this filename
                if filename in seen_filenames:
                    continue

                # Handle the main dataset specially
                if filename == 'data.parquet' and not default_added:
                    datasets.append((os.path.join(ui_data_dir, file), default_dataset_name))
                    default_added = True
                else:
                    datasets.append((os.path.join(ui_data_dir, file), filename))
                seen_filenames.add(filename)

    # Check the analysis/data directory
    analysis_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'analysis', 'data')
    if os.path.exists(analysis_data_dir):
        for file in os.listdir(analysis_data_dir):
            if file.endswith('.parquet'):
                filename = os.path.basename(file)
                # Skip if we've already seen this filename
                if filename in seen_filenames:
                    continue

                # Include the main data file but mark it as the default
                if filename == 'data.parquet' and not default_added:
                    datasets.append((os.path.join(analysis_data_dir, file), default_dataset_name))
                    default_added = True
                else:
                    datasets.append((os.path.join(analysis_data_dir, file), filename))
                seen_filenames.add(filename)

    # Check for datasets in the current directory
    for file in os.listdir('.'):
        if file.endswith('.parquet'):
            filename = os.path.basename(file)
            # Skip if we've already seen this filename
            if filename in seen_filenames:
                continue

            # Include the main data file but mark it as the default
            if filename == 'data.parquet' and not default_added:
                datasets.append((file, default_dataset_name))
                default_added = True
            else:
                datasets.append((file, filename))
            seen_filenames.add(filename)

    # Sort datasets to ensure consistent order (default first, then alphabetical)
    datasets.sort(key=lambda x: "" if x[1] == default_dataset_name else x[1])

    # If we found the default dataset, move it to the front of the list
    for i, (path, name) in enumerate(datasets):
        if name == default_dataset_name:
            datasets.pop(i)
            datasets.insert(0, (path, name))
            break

    return datasets

# Function to create a dataset using create_llm_dataset
def create_dataset(instructions, format="table"):
    try:
        from analysis.tools.claude_tools import create_llm_dataset
        from analysis.tools.claude_tools import fuzzy_match_teams

        # Parse the instructions to extract team name and time period
        # Use Claude to help with entity extraction
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None, "ANTHROPIC_API_KEY environment variable is not set."

        client = anthropic.Anthropic(api_key=api_key)

        # Get Claude to extract entities from the instructions
        extraction_response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=200,
            system="""
            You are an expert at extracting structured information from text instructions.
            Extract the team name and time period (if any) from the instructions.
            Respond in JSON format with keys 'team' and 'time_period'.
            For example:
            Input: "Create a 2025 Key West dataset"
            Output: {"team": "Key West", "time_period": "2025"}

            Input: "Internazionale matches in January"
            Output: {"team": "Internazionale", "time_period": "January"}

            If no time period is specified, use null for that field.
            If no team is specified, use null for that field.
            """,
            messages=[
                {"role": "user", "content": [{"type": "text", "text": instructions}]}
            ]
        )

        # Parse the extraction result
        extraction_text = extraction_response.content[0].text

        # Try to extract JSON from the response
        import re
        import json
        json_match = re.search(r'(\{.*\})', extraction_text, re.DOTALL)

        if json_match:
            try:
                extracted_data = json.loads(json_match.group(1))
                team = extracted_data.get('team')
                time_period = extracted_data.get('time_period')
            except:
                # If JSON parsing fails, use simple extraction
                team = None
                time_period = None
                if "team" in extraction_text and ":" in extraction_text:
                    team_match = re.search(r'"team"\s*:\s*"([^"]+)"', extraction_text)
                    if team_match:
                        team = team_match.group(1)
                if "time_period" in extraction_text and ":" in extraction_text:
                    time_match = re.search(r'"time_period"\s*:\s*"([^"]+)"', extraction_text)
                    if time_match:
                        time_period = time_match.group(1)
        else:
            # Fallback to treating the entire instruction as a team name
            team = instructions
            time_period = None

        if not team:
            return None, "Could not extract team name from instructions"

        # Get the default parquet file from session state
        source_parquet_file = st.session_state.default_parquet_path

        # Use fuzzy matching to get the exact team name from the database
        match_result = fuzzy_match_teams(team, parquet_file=source_parquet_file)
        if "error" in match_result:
            return None, match_result["error"]

        if match_result.get("matches"):
            # Use the highest confidence match
            team = match_result["matches"][0]["team_name"]
            logger.info(f"Fuzzy matched team name: {team}")

        # Create a descriptive dataset name for display and file naming
        dataset_name = team.replace(' ', '_').lower()
        if time_period:
            time_slug = time_period.replace(' ', '_').lower()
            # Put year first if it's a year for better sorting
            if time_period.isdigit() and len(time_period) == 4:
                dataset_name = f"{time_slug}_{dataset_name}"
            else:
                dataset_name += f"_{time_slug}"

        # Store the dataset name in session state
        st.session_state.dataset_name = f"{team}{' ' + time_period if time_period else ''}"

        # Construct SQL query with time period filter if provided
        query = None
        if time_period:
            # Map common time period descriptions to SQL expressions
            time_filters = {
                "january": "date_part('month', date) = 1",
                "february": "date_part('month', date) = 2",
                "march": "date_part('month', date) = 3",
                "april": "date_part('month', date) = 4",
                "may": "date_part('month', date) = 5",
                "june": "date_part('month', date) = 6",
                "july": "date_part('month', date) = 7",
                "august": "date_part('month', date) = 8",
                "september": "date_part('month', date) = 9",
                "october": "date_part('month', date) = 10",
                "november": "date_part('month', date) = 11",
                "december": "date_part('month', date) = 12",
                "2024": "date_part('year', date) = 2024",
                "2025": "date_part('year', date) = 2025",
            }

            # Try to match the time period to our predefined filters
            time_period_lower = time_period.lower()
            time_filter = None

            for key, filter_expr in time_filters.items():
                if key in time_period_lower:
                    time_filter = filter_expr
                    break

            # If we found a matching filter, create a query with time period constraint
            if time_filter:
                query = f"""
                SELECT
                    date,
                    league,
                    home_team,
                    away_team,
                    home_score,
                    away_score,
                    CASE
                        WHEN home_team LIKE '%{team}%' AND home_score > away_score THEN 'win'
                        WHEN away_team LIKE '%{team}%' AND away_score > home_score THEN 'win'
                        WHEN home_score = away_score AND home_score IS NOT NULL THEN 'draw'
                        WHEN home_score IS NULL OR away_score IS NULL THEN 'Not Played'
                        ELSE 'loss'
                    END as result
                FROM input_data
                WHERE (home_team LIKE '%{team}%' OR away_team LIKE '%{team}%')
                AND {time_filter}
                ORDER BY date DESC
                """
                logger.info(f"Created query with time filter: {time_filter}")

        # Define output file path
        ui_data_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(ui_data_dir, exist_ok=True)
        output_file = os.path.join(ui_data_dir, f"{dataset_name}_dataset.parquet")

        # First, use the database module to build a persistent dataset file
        from analysis.database import build_dataset

        # Create a SQL query that gets all matches for the team
        sql_query = query if query else f"""
        SELECT *
        FROM input_data
        WHERE
            home_team LIKE '%{team}%' OR
            away_team LIKE '%{team}%'
        ORDER BY date
        """

        logger.info(f"Creating dataset file at: {output_file}")

        # Execute the build_dataset function that saves the parquet file
        build_result = build_dataset(team, source_parquet_file, output_file, custom_query=sql_query)

        if "error" in build_result:
            return None, build_result["error"]

        logger.info(f"Successfully saved dataset to {output_file} with {build_result.get('row_count', 0)} rows")

        # Generate the in-memory dataset for context using create_llm_dataset
        result = create_llm_dataset(
            reasoning=f"Creating a dataset for {team}{' during ' + time_period if time_period else ''} to use in LLM context for chat",
            parquet_file=source_parquet_file,
            team=team,
            query=query,  # Pass the custom query if we have one
            format=format
        )

        if "error" in result:
            return None, result["error"]

        # Save the formatted data to the context
        time_info = f" ({time_period})" if time_period else ""
        dataset_context = f"""
# {team}{time_info} Team Dataset

{result.get('data', '')}

## Summary
- Total matches: {result.get('row_count', 'Unknown')}
- Dataset generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Team name: {team}{time_info if time_period else ''}
- Dataset file: {os.path.basename(output_file)}
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
        filename = os.path.basename(dataset_path)
        # Make a nice display name from the filename
        if filename.endswith('_dataset.parquet'):
            display_name = filename.replace('_dataset.parquet', '').replace('_', ' ').title()
            # Handle year prefixes specially (e.g., "2025_key_west" -> "Key West (2025)")
            year_match = re.match(r'(\d{4})_(.*)', display_name)
            if year_match:
                year, team = year_match.groups()
                display_name = f"{team} ({year})"
        else:
            display_name = filename.replace('.parquet', '').replace('_', ' ').title()

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
# {display_name} Team Dataset

The dataset contains {len(df)} matches for {display_name}.

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

                # Check if there's a dataset context and update the selected dataset
                if st.session_state.memory.get_dataset_context():
                    dataset_context = st.session_state.memory.get_dataset_context()
                    # Extract team name from context for potential SQL queries
                    team_name = None
                    context_lines = dataset_context.split('\n')
                    for line in context_lines:
                        if line.startswith('# ') and 'Team Dataset' in line:
                            team_name = line.replace('# ', '').replace(' Team Dataset', '').strip()
                            break
                    if team_name:
                        st.session_state.team_name = team_name
                        st.session_state.selected_dataset = team_name
                    else:
                        st.session_state.team_name = None
                else:
                    st.session_state.selected_dataset = None

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
        st.session_state.selected_dataset = None
        # Clear dataset context
        st.session_state.memory.set_dataset_context(None)
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

# Add dataset management to the sidebar
st.sidebar.markdown("---")
st.sidebar.title("🗃️ Dataset Management")

# Dataset creation section
st.sidebar.subheader("Create New Dataset")
dataset_instructions = st.sidebar.text_input("Instructions", value="", help="Enter instructions like 'Create a 2025 Key West dataset' or 'Internazionale matches in January'")
format_options = ["table", "compact", "simple"]
selected_format = st.sidebar.selectbox("Format", format_options, help="Select the format for the dataset")

if st.sidebar.button("Create Dataset"):
    if dataset_instructions:
        with st.sidebar.status("Creating dataset..."):
            # Use the default parquet file as the source for creating datasets
            dataset_context, error = create_dataset(dataset_instructions, selected_format)
            if error:
                st.sidebar.error(f"Error creating dataset: {error}")
            else:
                st.session_state.memory.set_dataset_context(dataset_context)
                dataset_name = getattr(st.session_state, 'dataset_name', 'Custom Dataset')
                st.session_state.selected_dataset = f"{dataset_name} (In-Memory)"
                # Update the active parquet file
                st.session_state.parquet_file = st.session_state.default_parquet_path
                st.sidebar.success(f"Dataset '{dataset_name}' created successfully")
    else:
        st.sidebar.warning("Please enter dataset instructions")

# Dataset selection section
st.sidebar.subheader("Select Dataset")
datasets = find_datasets()

if datasets:
    dataset_paths = [path for path, name in datasets]
    dataset_names = [name for path, name in datasets]

    # Get a clean list of display names for the dropdown
    display_names = []
    for path, name in datasets:
        # For custom datasets, clean up the filename for display
        if name != "Main Dataset (default)":
            # Strip off _dataset.parquet and make it more readable
            display_name = name.replace('_dataset.parquet', '').replace('_', ' ').title()
            # Handle year prefixes specially (e.g., "2025_key_west" -> "Key West (2025)")
            year_match = re.match(r'(\d{4})_(.*)', display_name)
            if year_match:
                year, team = year_match.groups()
                display_name = f"{team} ({year})"
            display_names.append(display_name)
        else:
            display_names.append(name)

    default_index = 0  # Default to the first item (should be Main Dataset)

    selected_dataset_index = st.sidebar.selectbox(
        "Available Datasets",
        range(len(dataset_names)),
        format_func=lambda i: display_names[i],
        index=default_index,
        help="Select a dataset to use for analysis"
    )

    # When a dataset is selected, update the parquet_file path
    selected_dataset_path = dataset_paths[selected_dataset_index]
    selected_dataset_name = dataset_names[selected_dataset_index]

    # Only update if the selection has changed
    if selected_dataset_path != st.session_state.parquet_file:
        st.session_state.parquet_file = selected_dataset_path
        # Clear dataset context if switching to main dataset
        if selected_dataset_name == "Main Dataset (default)":
            st.session_state.memory.set_dataset_context(None)
            st.session_state.selected_dataset = None
            st.sidebar.success(f"Switched to main dataset")
        else:
            # Load the dataset context for custom datasets
            with st.sidebar.status(f"Loading dataset {display_names[selected_dataset_index]}..."):
                dataset_context, error = load_dataset_file(selected_dataset_path)
                if error:
                    st.sidebar.error(f"Error loading dataset: {error}")
                else:
                    st.session_state.memory.set_dataset_context(dataset_context)
                    st.session_state.selected_dataset = display_names[selected_dataset_index]
                    st.sidebar.success(f"Dataset {display_names[selected_dataset_index]} loaded successfully")
else:
    st.sidebar.info("No datasets found. Create one using the instructions above.")

# Show the currently active dataset
if st.session_state.selected_dataset:
    st.sidebar.info(f"Active Dataset: {st.session_state.selected_dataset}")
elif selected_dataset_name == "Main Dataset (default)":
    st.sidebar.info("Using: Main Dataset (default)")

# Button to clear the selected dataset
if st.sidebar.button("Clear Selected Dataset"):
    st.session_state.memory.set_dataset_context(None)
    st.session_state.selected_dataset = None
    # Revert to default parquet file
    st.session_state.parquet_file = st.session_state.default_parquet_path
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
# Display welcome message and instructions when starting fresh
elif not st.session_state.messages:
    st.markdown("""
    ### Welcome to the Match Analysis Agent!

    **How to use this tool:**

    1. **Ask Questions:** Type your questions about soccer matches in the input box below
    2. **Select Datasets:** Use the sidebar to select or create specific datasets for focused analysis
    3. **Manage Conversations:** Save, rename, or switch between conversations using the sidebar controls

    **Features:**

    - **Team Analysis:** Ask about team performance, statistics, trends, and match outcomes
    - **Custom Datasets:** Create specialized datasets for specific teams or time periods
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
                            st.session_state.parquet_file,
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
    "- **Team Analysis:** Select the Hudson team dataset for focused team analysis\n"
    "- **Player Stats:** Ask specific questions about player performance metrics\n"
    "- **Match Insights:** For detailed match analysis, mention specific dates or opponents\n"
    "- **Custom Reports:** Create datasets with specific criteria for specialized analysis\n"
    "- **Remember:** For general questions, use the main dataset. For team-specific analysis, select or create a team dataset first."
)
