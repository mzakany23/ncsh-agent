# DuckDB Query Agent with Claude 3.7

An agentic approach to query DuckDB databases using Claude 3.7's thinking model and tool calling capabilities. This project allows you to ask natural language questions about data stored in parquet files and get accurate SQL-based answers.

## Features

- **Natural Language to SQL**: Translate questions like "how did Key West do in 2025 Feb" into proper SQL queries
- **Schema Understanding**: Automatically extracts and understands parquet file schema
- **SQL Validation**: Validates generated SQL before execution to prevent errors
- **Data Visualization**: Generate charts and visualizations from query results
- **Statistical Analysis**: Calculate summary statistics on data columns

## Architecture

The project uses an agent architecture with the following components:

- **Claude 3.7 API**: Powers the reasoning and natural language understanding
- **DuckDB**: Fast in-process SQL engine for querying parquet files
- **Tools Framework**: A set of tools for Claude to interact with the database
- **Analysis Module**: Enhanced data visualization and analytics capabilities

## Setup

This project uses [uv](https://github.com/astral-sh/uv) for Python package management and virtual environments.

### Prerequisites

- Python 3.8 or higher
- uv (`pip install uv`)
- An Anthropic API key for Claude 3.7

### Development Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ncsoccer-agent
   ```

2. Set up the development environment:
   ```bash
   make setup
   ```

3. Set your Anthropic API key:
   ```bash
   export ANTHROPIC_API_KEY=your_api_key_here
   ```

## Usage

Run the query agent with a natural language question and specify the parquet file to query:

```bash
python main.py -q "How did Key West do in 2025 Feb?" -f path/to/your/data.parquet
```

Additional options:

```bash
python main.py --help
```

## Project Structure

- `main.py`: Main entry point and agent implementation
- `analysis/`: Enhanced data analysis capabilities
  - `duckdb_analyzer.py`: DuckDB-specific analysis tools
- `tools/`: Tool implementations for Claude 3.7
  - `claude_tools.py`: Claude 3.7 tool calling definitions

## Dependency Management

This project follows specific conventions for dependency management:

- **Development dependencies** are defined in `pyproject.toml` under `project.optional-dependencies.dev`
- **Production dependencies** are defined in `requirements.in` and compiled to `requirements.txt`

To add a new production dependency:
1. Add it to `requirements.in`
2. Run `make requirements` to update `requirements.txt`
3. Run `make setup` to install the dependency

## Example

```bash
python main.py -q "What were the highest temperatures in Miami during January 2025?" -f weather_data.parquet --thinking_budget 3000
```

The agent will:
1. Analyze the schema of the parquet file
2. Translate the natural language query to SQL
3. Validate and execute the generated SQL
4. Display the results in a readable format

## License

[MIT License](LICENSE)