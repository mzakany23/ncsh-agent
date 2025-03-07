# NC Soccer Match Analysis UI

This directory contains a Streamlit-based user interface for analyzing soccer match data using natural language queries. The UI interacts with the Claude 3.7 agent to provide insights about soccer matches.

## Features

- Natural language querying of soccer match data
- Interactive chat interface with conversation memory
- Visualizations of match statistics and query results
- Configuration options for API keys and data sources

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Anthropic API key for Claude 3.7
- Parquet file containing soccer match data

### Running the UI

1. Set up your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

2. Set the path to your parquet file (optional, defaults to data/matches.parquet):

```bash
export PARQUET_FILE=path/to/your/matches.parquet
```

3. Start the application using Docker Compose:

```bash
cd ui
docker-compose up --build
```

4. Open your browser and navigate to http://localhost:8501

### Usage

1. Enter your Anthropic API key in the sidebar (if not set as an environment variable)
2. Verify or update the path to your parquet file
3. Type your question in the chat input box at the bottom of the screen
4. View the response from the Claude 3.7 agent
5. Continue the conversation with follow-up questions

## Example Questions

- "How did Key West FC perform in their last 5 matches?"
- "Show me the top 5 teams with the most wins"
- "Which team scored the most goals in August 2023?"
- "Create a dataset for all matches involving Orlando City"
- "Compare the performance of Team A and Team B"

## Troubleshooting

- If you encounter connection issues with Claude, verify your API key
- If data loading fails, check that the parquet file path is correct
- Use the "Clear Chat History" button in the sidebar to reset the conversation if needed
