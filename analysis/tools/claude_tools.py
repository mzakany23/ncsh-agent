"""
Claude Tools Module

This module defines the tools that Claude 3.7 can use via the Anthropic API's
tool calling capabilities, implemented using the LlamaIndex FunctionTool pattern.

This module imports the implementation from analysis/database.py module
to keep all analysis code insular to the analysis module.
"""

import os
import json
import traceback
from typing import Dict, List, Any, Optional
from rich.console import Console
try:
    from llama_index.core.tools import FunctionTool
except ModuleNotFoundError:
    print("llama_index module not found; using dummy FunctionTool")
    class FunctionTool:
        pass

# Import analysis functions from the database module
from analysis.database import (
    execute_sql,
    get_schema,
    validate_sql,
    query_to_sql,
    build_dataset,
    compact_dataset
)

# Import Anthropic client for summarization
import anthropic

# Initialize console for rich output
console = Console()

def complete_task(reasoning: str) -> Dict:
    """
    Tool for finalizing task and providing the final response.

    Args:
        reasoning: Final summary and answer to the user's question

    Returns:
        Dictionary with task completion status or error message
    """
    try:
        if not reasoning:
            error_message = "No reasoning provided for task completion."
            console.log(f"[tool_complete_task] Error: {error_message}")
            return {"error": error_message}

        console.log(f"[tool_complete_task] reasoning: {reasoning}")
        return {"result": "Task completed"}
    except Exception as e:
        console.log(f"[tool_complete_task] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}


def summarize_results(reasoning: str, data: str, summarization_type: str) -> Dict:
    """
    Tool for summarizing query results through a prompt.

    Args:
        reasoning: Why summarization is needed and what aspects to focus on
        data: The data to be summarized (usually query results)
        summarization_type: Type of summarization needed (brief, detailed, comparative, etc.)

    Returns:
        Dictionary with summarized results or error message
    """
    try:
        if not data:
            error_message = "No data provided for summarization."
            console.log(f"[tool_summarize_results] Error: {error_message}")
            return {"error": error_message}

        # Get API key from environment variable
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            error_message = "ANTHROPIC_API_KEY environment variable is not set."
            console.log(f"[tool_summarize_results] Error: {error_message}")
            return {"error": error_message}

        client = anthropic.Anthropic(api_key=api_key)

        # Define prompt based on summarization type
        prompts = {
            "brief": "Provide a very concise summary of the key insights from this data. Focus only on the most important points and keep it to 2-3 sentences.",
            "detailed": "Provide a comprehensive analysis of this data, including key metrics, trends, and notable outliers. Format the information in a well-structured way with headings and bullet points where appropriate.",
            "comparative": "Compare and contrast the different entities or time periods in this data. Highlight significant differences and similarities.",
            "insights": "Extract 3-5 key actionable insights from this data that would be valuable for decision-making.",
            "narrative": "Create a narrative story that explains what this data shows in an engaging, conversational way that non-technical stakeholders would understand."
        }

        # Choose appropriate prompt or use default
        prompt_text = prompts.get(summarization_type.lower(), "Summarize the following data in a clear, concise manner:")

        # Call Claude for summarization
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt_text}\n\nData to summarize:\n{data}\n\nReasoning context for summarization: {reasoning}"
                }
            ]
        )

        # Extract the summarized content
        summarized_text = response.content[0].text if response.content else "No summary generated."

        console.log(f"[tool_summarize_results] Generated summary of type '{summarization_type}'")
        return {"result": summarized_text}
    except Exception as e:
        console.log(f"[tool_summarize_results] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}

# Create LlamaIndex FunctionTools for the agent
def get_claude_tools() -> List[Dict]:
    """
    Get the tool definitions for Claude 3.7 API.

    Returns:
        List of tool definitions in the Claude API format
    """
    return [
        {
            "name": "execute_sql",
            "description": "Execute SQL queries against a DuckDB database",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Explain why this SQL query is appropriate",
                    },
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute",
                    },
                    "parquet_file": {
                        "type": "string",
                        "description": "Path to the parquet file",
                    },
                },
                "required": ["reasoning", "query", "parquet_file"],
            },
        },
        {
            "name": "build_dataset",
            "description": "Create a filtered dataset for a specific team and save it as a new parquet file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "team": {
                        "type": "string",
                        "description": "The team name to filter the dataset by (will search home_team and away_team)",
                    },
                    "parquet_file": {
                        "type": "string",
                        "description": "Path to the source parquet file",
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Path to save the filtered dataset as a parquet file",
                    },
                },
                "required": ["team", "parquet_file", "output_file"],
            },
        },
        {
            "name": "compact_dataset",
            "description": "Create a compact representation of match data optimized for Claude's context window",
            "input_schema": {
                "type": "object",
                "properties": {
                    "parquet_file": {
                        "type": "string",
                        "description": "Path to the parquet file containing match data",
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Format style ('compact', 'table', or 'csv')",
                    },
                },
                "required": ["parquet_file"],
            },
        },
        {
            "name": "get_schema",
            "description": "Get schema information from a parquet file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Why you need the schema information",
                    },
                    "parquet_file": {
                        "type": "string",
                        "description": "Path to the parquet file",
                    },
                },
                "required": ["reasoning", "parquet_file"],
            },
        },
        {
            "name": "validate_sql",
            "description": "Validate SQL queries without executing them",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Why you want to validate this query",
                    },
                    "query": {
                        "type": "string",
                        "description": "The SQL query to validate",
                    },
                },
                "required": ["reasoning", "query"],
            },
        },
        {
            "name": "query_to_sql",
            "description": "Translate natural language queries to SQL",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Detailed reasoning for the SQL translation",
                    },
                    "question": {
                        "type": "string",
                        "description": "The natural language question",
                    },
                    "schema_info": {
                        "type": "string",
                        "description": "Schema information to inform the translation",
                    },
                },
                "required": ["reasoning", "question", "schema_info"],
            },
        },
        {
            "name": "summarize_results",
            "description": "Summarize query results through a prompt for better presentation",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Why summarization is needed and what aspects to focus on",
                    },
                    "data": {
                        "type": "string",
                        "description": "The data to be summarized (usually query results)",
                    },
                    "summarization_type": {
                        "type": "string",
                        "description": "Type of summarization needed (brief, detailed, comparative, insights, narrative)",
                        "enum": ["brief", "detailed", "comparative", "insights", "narrative"]
                    },
                },
                "required": ["reasoning", "data", "summarization_type"],
            },
        },
        {
            "name": "complete_task",
            "description": "Complete the task and provide the final response",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Final summary and answer to the user's question",
                    },
                },
                "required": ["reasoning"],
            },
        },
        {
            "name": "check_date_range",
            "description": "Check if data exists for a specific date range and return the available date range in the dataset",
            "input_schema": {
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": "The team name to search for (optional)"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (optional)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (optional)"
                    },
                    "parquet_file": {
                        "type": "string",
                        "description": "Path to the Parquet file, default: 'analysis/data/data.parquet'"
                    }
                }
            }
        }
    ]

# Tool adapter functions that extract parameters from tool input dictionaries
def tool_execute_sql(tool_input: Dict) -> Dict:
    """Adapter for execute_sql function."""
    reasoning = tool_input.get("reasoning", "")
    query = tool_input.get("query", "")
    parquet_file = tool_input.get("parquet_file", "")
    return execute_sql(reasoning, query, parquet_file)

def tool_get_schema(tool_input: Dict) -> Dict:
    """Adapter for get_schema function."""
    reasoning = tool_input.get("reasoning", "")
    parquet_file = tool_input.get("parquet_file", "")
    return get_schema(reasoning, parquet_file)

def tool_validate_sql(tool_input: Dict) -> Dict:
    """Adapter for validate_sql function."""
    reasoning = tool_input.get("reasoning", "")
    query = tool_input.get("query", "")
    return validate_sql(reasoning, query)

def tool_query_to_sql(tool_input: Dict) -> Dict:
    """Adapter for query_to_sql function."""
    reasoning = tool_input.get("reasoning", "")
    question = tool_input.get("question", "")
    schema_info = tool_input.get("schema_info", "")
    return query_to_sql(reasoning, question, schema_info)

def tool_summarize_results(tool_input: Dict) -> Dict:
    """Adapter for summarize_results function."""
    reasoning = tool_input.get("reasoning", "")
    data = tool_input.get("data", "")
    summarization_type = tool_input.get("summarization_type", "brief")
    return summarize_results(reasoning, data, summarization_type)

def tool_build_dataset(tool_input: Dict) -> Dict:
    """Adapter for build_dataset function."""
    team = tool_input.get("team", "")
    parquet_file = tool_input.get("parquet_file", "")
    output_file = tool_input.get("output_file", "")
    return build_dataset(team, parquet_file, output_file)

def tool_compact_dataset(tool_input: Dict) -> Dict:
    """Adapter for compact_dataset function."""
    parquet_file = tool_input.get("parquet_file", "")
    output_format = tool_input.get("output_format", "compact")
    return compact_dataset(parquet_file, output_format)

def tool_check_date_range(tool_input: Dict) -> Dict:
    """Checks if data exists for a specific date range and returns the available date range in the dataset."""
    try:
        from analysis.database import DuckDBAnalyzer
        import json

        parquet_file = tool_input.get("parquet_file", "analysis/data/data.parquet")
        team_name = tool_input.get("team_name", None)
        start_date = tool_input.get("start_date", None)
        end_date = tool_input.get("end_date", None)

        # Initialize the DuckDB analyzer with the parquet file
        analyzer = DuckDBAnalyzer(parquet_file)

        # Get the overall date range of the dataset
        date_range_query = "SELECT MIN(date) AS earliest_date, MAX(date) AS latest_date FROM input_data;"
        date_range_result = analyzer.query(date_range_query)

        try:
            date_range_data = json.loads(date_range_result)
        except:
            date_range_data = []

        # Check if we have team-specific date range request
        if team_name and start_date and end_date:
            # Construct team query with wildcards to catch variations of the team name
            team_query = f"""
            SELECT
                date,
                home_team,
                away_team,
                home_score,
                away_score,
                league
            FROM input_data
            WHERE
                (home_team LIKE '%{team_name}%' OR away_team LIKE '%{team_name}%')
                AND date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY date;
            """

            team_result = analyzer.query(team_query)

            try:
                team_matches = json.loads(team_result)
            except:
                team_matches = []

            # Construct the response
            response = {
                "dataset_range": date_range_data[0] if date_range_data and len(date_range_data) > 0 else {"earliest_date": "unknown", "latest_date": "unknown"},
                "matches_found": len(team_matches),
                "matches": team_matches[:10] if team_matches else [],  # Limit to first 10 matches
                "has_more_matches": len(team_matches) > 10 if team_matches else False
            }

            return {"result": json.dumps(response)}
        else:
            # Just return the overall date range
            return {"result": json.dumps({"dataset_range": date_range_data[0] if date_range_data and len(date_range_data) > 0 else {"earliest_date": "unknown", "latest_date": "unknown"}})}

    except Exception as e:
        import traceback
        return {"error": f"{str(e)}\n{traceback.format_exc()}"}

# Create a mapping of tool names to their implementation functions
def get_tool_mapping() -> Dict:
    """
    Get a mapping of tool names to their implementation functions.

    Returns:
        Dictionary mapping tool names to functions
    """
    return {
        "execute_sql": tool_execute_sql,
        "get_schema": tool_get_schema,
        "validate_sql": tool_validate_sql,
        "query_to_sql": tool_query_to_sql,
        "summarize_results": tool_summarize_results,
        "complete_task": complete_task,
        "build_dataset": tool_build_dataset,
        "compact_dataset": tool_compact_dataset,
        "check_date_range": tool_check_date_range
    }
