"""
Claude Tools Module

This module defines the tools that Claude 3.7 can use via the Anthropic API's
tool calling capabilities, implemented using the LlamaIndex FunctionTool pattern.

This module imports the implementation from analysis/database.py module
to keep all analysis code insular to the analysis module.
"""

import re
import os
import json
import traceback
import anthropic
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from rich.console import Console
import time
from datetime import datetime

from analysis.database import DuckDBAnalyzer

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

# Global variables for storing results between tool calls
_last_fuzzy_match_result = None

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

def team_exists(team_name: str, parquet_file: str) -> bool:
    """
    Check if a team exists in the dataset.

    Args:
        team_name: The team name to check
        parquet_file: Path to the parquet file

    Returns:
        Boolean indicating if the team exists
    """
    try:
        from analysis.database import execute_sql

        # Build a simple query to check if the team exists
        check_sql = f"""
        SELECT COUNT(*) as count
        FROM read_parquet('{parquet_file}')
        WHERE home_team LIKE '%{team_name}%' OR away_team LIKE '%{team_name}%'
        """

        # Execute the query
        result = execute_sql("Check if team exists", check_sql, parquet_file)
        result_data = result.get("result", "")

        # Parse the result
        if "count" in result_data:
            import json
            count_data = json.loads(result_data)
            if isinstance(count_data, list) and len(count_data) > 0:
                count = count_data[0].get("count", 0)
                return count > 0

        return False
    except Exception as e:
        console.log(f"[team_exists] Error: {str(e)}")
        return False


def execute_team_comparison(team1: str, team2: str, time_period: str, parquet_file: str) -> Dict:
    """
    Tool for executing a structured comparison between two teams for a specific time period.
    This handles the complete data collection process by executing SQL queries and formatting results.

    Args:
        team1: First team name to compare
        team2: Second team name to compare
        time_period: Time period for comparison (e.g., "January 2025", "2024")
        parquet_file: Path to the parquet file

    Returns:
        Dictionary with comparison results or error message
    """
    try:
        if not team1 or not team2:
            error_message = "Both team names are required for comparison."
            console.log(f"[tool_execute_team_comparison] Error: {error_message}")
            return {"error": error_message}

        # Check if both teams exist in the dataset
        team1_exists = team_exists(team1, parquet_file)
        team2_exists = team_exists(team2, parquet_file)

        if not team1_exists and not team2_exists:
            error_message = f"Neither '{team1}' nor '{team2}' exists in the dataset."
            console.log(f"[tool_execute_team_comparison] Error: {error_message}")
            return {"error": error_message}

        if not team1_exists:
            error_message = f"Team '{team1}' does not exist in the dataset."
            console.log(f"[tool_execute_team_comparison] Error: {error_message}")
            return {"error": error_message}

        if not team2_exists:
            error_message = f"Team '{team2}' does not exist in the dataset."
            console.log(f"[tool_execute_team_comparison] Error: {error_message}")
            return {"error": error_message}

        # Parse the time period into start and end dates
        start_date = None
        end_date = None

        # Extract month and year if present
        import re
        import calendar
        from datetime import datetime

        # Match patterns like "January 2025" or just "2025"
        month_year_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", time_period, re.IGNORECASE)
        year_match = re.search(r"(\d{4})", time_period)

        if month_year_match:
            month_name = month_year_match.group(1).capitalize()
            year = int(month_year_match.group(2))
            month_num = list(calendar.month_abbr).index(month_name[:3].title())
            start_date = f"{year}-{month_num:02d}-01"
            last_day = calendar.monthrange(year, month_num)[1]
            end_date = f"{year}-{month_num:02d}-{last_day:02d}"
        elif year_match:
            year = int(year_match.group(1))
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
        else:
            # Default to current month if no date specified
            now = datetime.now()
            start_date = f"{now.year}-{now.month:02d}-01"
            last_day = calendar.monthrange(now.year, now.month)[1]
            end_date = f"{now.year}-{now.month:02d}-{last_day:02d}"

        # Build SQL queries for team performance
        # Query 1: Get overall performance metrics for both teams
        overall_sql = f"""
        WITH all_matches AS (
            -- Matches where team1 is home
            SELECT
                date,
                home_team AS team,
                away_team AS opponent,
                home_score AS team_score,
                away_score AS opponent_score,
                CASE
                    WHEN home_score > away_score THEN 'win'
                    WHEN home_score < away_score THEN 'loss'
                    ELSE 'draw'
                END AS result,
                league
            FROM read_parquet('{parquet_file}')
            WHERE (home_team LIKE '%{team1}%' OR home_team LIKE '%{team2}%')
                AND date BETWEEN '{start_date}' AND '{end_date}'

            UNION ALL

            -- Matches where team1 is away
            SELECT
                date,
                away_team AS team,
                home_team AS opponent,
                away_score AS team_score,
                home_score AS opponent_score,
                CASE
                    WHEN away_score > home_score THEN 'win'
                    WHEN away_score < home_score THEN 'loss'
                    ELSE 'draw'
                END AS result,
                league
            FROM read_parquet('{parquet_file}')
            WHERE (away_team LIKE '%{team1}%' OR away_team LIKE '%{team2}%')
                AND date BETWEEN '{start_date}' AND '{end_date}'
        )

        SELECT
            team,
            COUNT(*) AS total_matches,
            SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) AS draws,
            SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
            SUM(team_score) AS goals_for,
            SUM(opponent_score) AS goals_against,
            SUM(team_score) - SUM(opponent_score) AS goal_difference,
            ROUND(AVG(team_score), 2) AS avg_goals_scored,
            ROUND(AVG(opponent_score), 2) AS avg_goals_conceded
        FROM all_matches
        WHERE team LIKE '%{team1}%' OR team LIKE '%{team2}%'
        GROUP BY team
        ORDER BY wins DESC, goal_difference DESC
        """

        # Query 2: Get detailed match results for both teams
        matches_sql = f"""
        WITH all_matches AS (
            -- Matches where either team is home
            SELECT
                date,
                home_team,
                away_team,
                home_score,
                away_score,
                CASE
                    WHEN home_team LIKE '%{team1}%' THEN '{team1}'
                    WHEN home_team LIKE '%{team2}%' THEN '{team2}'
                    ELSE NULL
                END AS focus_team,
                league
            FROM read_parquet('{parquet_file}')
            WHERE (home_team LIKE '%{team1}%' OR home_team LIKE '%{team2}%' OR away_team LIKE '%{team1}%' OR away_team LIKE '%{team2}%')
                AND date BETWEEN '{start_date}' AND '{end_date}'
        )

        SELECT
            date,
            home_team,
            away_team,
            home_score,
            away_score,
            league
        FROM all_matches
        ORDER BY date DESC
        LIMIT 20
        """

        # Query 3: Get league standings for context
        standings_sql = f"""
        WITH all_matches AS (
            -- Matches where teams are home
            SELECT
                date,
                home_team AS team,
                away_team AS opponent,
                home_score AS team_score,
                away_score AS opponent_score,
                CASE
                    WHEN home_score > away_score THEN 'win'
                    WHEN home_score < away_score THEN 'loss'
                    ELSE 'draw'
                END AS result,
                league
            FROM read_parquet('{parquet_file}')
            WHERE date BETWEEN '{start_date}' AND '{end_date}'

            UNION ALL

            -- Matches where teams are away
            SELECT
                date,
                away_team AS team,
                home_team AS opponent,
                away_score AS team_score,
                home_score AS opponent_score,
                CASE
                    WHEN away_score > home_score THEN 'win'
                    WHEN away_score < home_score THEN 'loss'
                    ELSE 'draw'
                END AS result,
                league
            FROM read_parquet('{parquet_file}')
            WHERE date BETWEEN '{start_date}' AND '{end_date}'
        ),

        -- Calculate team statistics
        team_stats AS (
            SELECT
                team,
                COUNT(*) AS total_matches,
                SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) AS draws,
                SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN result = 'win' THEN 3 WHEN result = 'draw' THEN 1 ELSE 0 END) AS points,
                SUM(team_score) AS goals_for,
                SUM(opponent_score) AS goals_against,
                SUM(team_score) - SUM(opponent_score) AS goal_difference
            FROM all_matches
            GROUP BY team
        )

        -- Get the league standings
        SELECT
            team,
            total_matches,
            wins,
            draws,
            losses,
            points,
            goals_for,
            goals_against,
            goal_difference
        FROM team_stats
        ORDER BY points DESC, goal_difference DESC, goals_for DESC
        LIMIT 10
        """

        # Execute the queries
        from analysis.database import execute_sql

        # Execute overall performance query
        overall_result = execute_sql("Get overall performance metrics for both teams", overall_sql, parquet_file)
        overall_data = overall_result.get("result", "No overall performance data found.")

        # Execute match results query
        matches_result = execute_sql("Get recent match results for both teams", matches_sql, parquet_file)
        matches_data = matches_result.get("result", "No match data found.")

        # Execute standings query
        standings_result = execute_sql("Get league standings for context", standings_sql, parquet_file)
        standings_data = standings_result.get("result", "No standings data found.")

        # Combine all data into a structured format
        combined_data = f"""
COMPARISON DATA: {team1} vs {team2} ({time_period})

TIME PERIOD: {start_date} to {end_date}

1. OVERALL PERFORMANCE METRICS:
{overall_data}

2. RECENT MATCH RESULTS:
{matches_data}

3. LEAGUE CONTEXT (STANDINGS):
{standings_data}
"""

        # Return the combined results
        console.log(f"[tool_execute_team_comparison] Executed comparison between {team1} and {team2} for {time_period}")
        return {"result": combined_data}

    except Exception as e:
        console.log(f"[tool_execute_team_comparison] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}

def comprehensive_summary(reasoning: str, collected_data: str, query_context: str, analysis_format: str = "detailed") -> Dict:
    """
    Tool for providing a comprehensive final summary that serves as the 'reduce' step
    in the map-reduce pattern, bringing together all collected information.

    This should be used AFTER collecting data with SQL queries or other data tools.

    Args:
        reasoning: Why this summary is needed and the analytical approach taken
        collected_data: All data collected from previous tool calls (SQL query results, stats, etc.)
        query_context: The original query and any context needed to frame the answer
        analysis_format: The format style for the analysis (detailed, executive, visual, actionable)

    Returns:
        Dictionary with comprehensive summary or error message
    """
    try:
        if not collected_data:
            error_message = "No data provided for comprehensive summary."
            console.log(f"[tool_comprehensive_summary] Error: {error_message}")
            return {"error": error_message}

        # Get API key from environment variable
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            error_message = "ANTHROPIC_API_KEY environment variable is not set."
            console.log(f"[tool_comprehensive_summary] Error: {error_message}")
            return {"error": error_message}

        client = anthropic.Anthropic(api_key=api_key)

        # Define prompt based on analysis format
        format_prompts = {
            "detailed": """Provide a comprehensive analysis that:
1. Directly answers the user's original question
2. Provides detailed supporting evidence from the data
3. Offers well-structured sections with headings
4. Highlights important insights and patterns
5. Uses bullet points and numbered lists for clarity
6. Explains methodology and limitations
7. Includes relevant metrics and statistics""",

            "executive": """Create an executive summary that:
1. Starts with a direct, concise answer to the original question
2. Provides only the most crucial insights (3-5 key points)
3. Uses clear, business-focused language
4. Avoids technical details unless absolutely necessary
5. Ends with clear recommendations or implications""",

            "visual": """Create a summary optimized for visualization that:
1. Answers the original question directly
2. Describes key data points that would be ideal for charts/graphs
3. Suggests visualization types for the data (bar charts, line graphs, etc.)
4. Groups related metrics for comparative visualization
5. Highlights trends, patterns, and outliers""",

            "actionable": """Provide action-oriented analysis that:
1. Directly answers the original question
2. Transforms data insights into recommended actions
3. Prioritizes insights by potential impact
4. Presents clear next steps based on the findings
5. Includes potential risks or considerations"""
        }

        # Choose appropriate prompt or use default
        format_prompt = format_prompts.get(
            analysis_format.lower(),
            "Provide a comprehensive, well-structured analysis of the data that thoroughly answers the original question."
        )

        # Construct the system prompt for comprehensive analysis
        system_prompt = f"""You are an expert data analyst specializing in soccer data analysis.
Your task is to provide the final, comprehensive analysis that brings together all the data collected so far.
{format_prompt}

Important guidelines:
1. Always make direct comparisons between teams when doing a comparative analysis
2. Highlight strengths and weaknesses of each team based on actual performance metrics
3. Use specific numbers and statistics to support your claims
4. Organize your analysis with clear headings and structure
5. Only make claims that are supported by the data provided

Always maintain a professional, analytical tone. Be thorough but avoid unnecessary verbosity.
Make your analysis directly relevant to the original query. Use clear headings and structure.
"""

        # Call Claude for comprehensive summary
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=2000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"""Original query and context: {query_context}

Data collected from previous analyses:
{collected_data}

Additional reasoning/context: {reasoning}

Please provide a comprehensive final analysis that answers the original query, synthesizing all relevant information from the collected data.
"""
                }
            ]
        )

        # Extract the summarized content
        summary_text = response.content[0].text if response.content else "No comprehensive summary generated."

        console.log(f"[tool_comprehensive_summary] Generated comprehensive summary in '{analysis_format}' format")
        return {"result": summary_text}
    except Exception as e:
        console.log(f"[tool_comprehensive_summary] Error: {str(e)}")
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
        },
        {
            "name": "execute_team_comparison",
            "description": "Execute a structured comparison between two soccer teams for a specific time period by running SQL queries and collecting comprehensive data",
            "input_schema": {
                "type": "object",
                "properties": {
                    "team1": {
                        "type": "string",
                        "description": "First team name to compare",
                    },
                    "team2": {
                        "type": "string",
                        "description": "Second team name to compare",
                    },
                    "time_period": {
                        "type": "string",
                        "description": "Time period for comparison (e.g., 'January 2025', '2024')",
                    },
                    "parquet_file": {
                        "type": "string",
                        "description": "Path to the parquet file, default: 'analysis/data/data.parquet'",
                    }
                },
                "required": ["team1", "team2", "time_period"],
            },
        },
        {
            "name": "comprehensive_summary",
            "description": "Provide a final comprehensive summary that synthesizes all collected information to answer the original query. This is the 'reduce' step in the map-reduce pattern. NOTE: Use this AFTER collecting data with SQL queries or team comparison tools.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Reasoning about the analytical approach and synthesis process",
                    },
                    "collected_data": {
                        "type": "string",
                        "description": "All data collected from previous tool calls (e.g., SQL query results, schema info, statistics)",
                    },
                    "query_context": {
                        "type": "string",
                        "description": "The original user query and any context needed to frame the answer appropriately",
                    },
                    "analysis_format": {
                        "type": "string",
                        "description": "Format style for the comprehensive analysis",
                        "enum": ["detailed", "executive", "visual", "actionable"]
                    },
                },
                "required": ["reasoning", "collected_data", "query_context"],
            },
        },
        {
            "name": "create_analysis_pipeline",
            "description": "Create and execute a complete analysis pipeline based on the query type. This smart tool selects appropriate tools, executes them in sequence as a directed graph, and passes context between steps to produce a comprehensive analysis. This should be your first choice for complex analysis tasks.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's original query for analysis",
                    },
                    "parquet_file": {
                        "type": "string",
                        "description": "Path to the parquet file, default: 'analysis/data/data.parquet'",
                    }
                },
                "required": ["query"],
            },
        },
        {
            "name": "select_tool",
            "description": "Analyzes your query and recommends the most appropriate tool to use next. Use this tool FIRST when processing complex queries to determine the right approach.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's natural language query to analyze",
                    }
                },
                "required": ["query"],
            },
        },
        {
            "name": "fuzzy_match_teams",
            "description": "Analyzes a query to identify potential team names and time references, then performs fuzzy matching to find the actual team names in the database. Use this tool first for any query involving team names to avoid 'team not found' errors.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's natural language query containing team names",
                    },
                    "team_candidates": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Optional list of team names to match against (if not provided, will be loaded from database)",
                    },
                    "parquet_file": {
                        "type": "string",
                        "description": "Path to the parquet file",
                    }
                },
                "required": ["query"],
            },
        },
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

def tool_execute_team_comparison(tool_input: Dict) -> Dict:
    """Adapter for execute_team_comparison function."""
    team1 = tool_input.get("team1", "")
    team2 = tool_input.get("team2", "")
    time_period = tool_input.get("time_period", "")
    parquet_file = tool_input.get("parquet_file", "analysis/data/data.parquet")
    return execute_team_comparison(team1, team2, time_period, parquet_file)

def tool_comprehensive_summary(tool_input: Dict) -> Dict:
    """Adapter for comprehensive_summary function."""
    reasoning = tool_input.get("reasoning", "")
    collected_data = tool_input.get("collected_data", "")
    query_context = tool_input.get("query_context", "")
    analysis_format = tool_input.get("analysis_format", "detailed")
    return comprehensive_summary(reasoning, collected_data, query_context, analysis_format)

def tool_select_tool(tool_input: Dict) -> Dict:
    """Tool implementation for select_tool"""
    query = tool_input.get("query", "")
    return select_tool(query)

def fuzzy_match_teams(query: str, team_candidates: List[str] = None, parquet_file: str = "analysis/data/data.parquet") -> Dict:
    """
    Performs fuzzy matching to find the most likely team names in the database that match
    what was mentioned in the query. Also resolves time references like "last year".

    Args:
        query: The user's query containing potential team names and time references
        team_candidates: Optional list of potential team names to match against (if None, loads from database)
        parquet_file: Path to the parquet file

    Returns:
        Dictionary with matched teams and resolved time periods
    """
    try:
        console.log(f"[fuzzy_match_teams] Analyzing query: {query}")

        # If no team candidates provided, get all teams from the database
        if team_candidates is None:
            # Use DuckDBAnalyzer to query all unique team names
            analyzer = DuckDBAnalyzer(parquet_file)
            # Execute the SQL directly with DuckDB
            sql = """
            SELECT DISTINCT home_team AS team_name FROM input_data
            UNION
            SELECT DISTINCT away_team AS team_name FROM input_data
            ORDER BY team_name
            """
            # Get the result as a JSON string
            results_json = analyzer.query(sql)
            # Parse the JSON string to get the team names
            results = json.loads(results_json)
            team_candidates = [row["team_name"] for row in results]
            console.log(f"[fuzzy_match_teams] Found {len(team_candidates)} unique teams in database")

        # Extract potential team names from the query using Claude's reasoning
        # We'll use anthropic's API to have Claude analyze the query for potential team names
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"error": "ANTHROPIC_API_KEY environment variable is not set."}

        client = anthropic.Anthropic(api_key=api_key)

        # Create a system prompt specifically for entity extraction
        system_prompt = """
        You are an expert at extracting and understanding sports team names and time references from text.
        Your task is to:
        1. Identify potential team names mentioned in the query
        2. Resolve time references (e.g., "last year", "this season", etc.)
        3. Structure your response in JSON format

        Do not make assumptions. Only extract what is explicitly mentioned.
        """

        # Ask Claude to extract team names and time references
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=500,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"""
                    Please analyze this query for soccer team names and time references:

                    "{query}"

                    Extract:
                    1. Any potential team names mentioned
                    2. Any time references (month, year, season, etc.)

                    Format your response as JSON with this structure:
                    {{
                        "potential_teams": ["Team1", "Team2", ...],
                        "time_references": ["January 2025", "last season", ...],
                        "reasoning": "Brief explanation of your extraction process"
                    }}

                    Return ONLY the JSON, nothing else.
                    """
                }
            ]
        )

        # Extract the JSON response
        extraction_text = response.content[0].text

        # Parse the JSON, handling potential JSON formatting issues
        try:
            extracted_data = json.loads(extraction_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON using regex
            import re
            json_match = re.search(r'\{.*\}', extraction_text, re.DOTALL)
            if json_match:
                try:
                    extracted_data = json.loads(json_match.group(0))
                except:
                    extracted_data = {
                        "potential_teams": [],
                        "time_references": [],
                        "reasoning": "Failed to parse JSON response"
                    }
            else:
                extracted_data = {
                    "potential_teams": [],
                    "time_references": [],
                    "reasoning": "Failed to parse JSON response"
                }

        potential_teams = extracted_data.get("potential_teams", [])
        time_references = extracted_data.get("time_references", [])

        console.log(f"[fuzzy_match_teams] Extracted potential teams: {potential_teams}")
        console.log(f"[fuzzy_match_teams] Extracted time references: {time_references}")

        # For each potential team, find the closest match in the database
        matched_teams = {}
        for team in potential_teams:
            # Perform fuzzy matching
            best_match = None
            best_score = 0

            for candidate in team_candidates:
                # Calculate Levenshtein distance ratio for fuzzy matching
                from difflib import SequenceMatcher
                score = SequenceMatcher(None, team.lower(), candidate.lower()).ratio()

                # Also check if team is a substring of candidate or vice versa
                if team.lower() in candidate.lower() or candidate.lower() in team.lower():
                    score += 0.2  # Boost score for substring matches

                if score > best_score:
                    best_score = score
                    best_match = candidate

            # Consider it a match if score is above threshold
            if best_score > 0.6:
                matched_teams[team] = {
                    "matched_name": best_match,
                    "confidence": best_score,
                    "exact_match": team == best_match
                }
            else:
                matched_teams[team] = {
                    "matched_name": None,
                    "confidence": 0,
                    "suggestions": sorted(
                        [(SequenceMatcher(None, team.lower(), c.lower()).ratio(), c)
                         for c in team_candidates if SequenceMatcher(None, team.lower(), c.lower()).ratio() > 0.4],
                        key=lambda x: x[0], reverse=True
                    )[:5]
                }

        # Resolve time references using Claude's help
        resolved_time = {}
        if time_references:
            time_resolution_response = client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=500,
                system="""You are an expert at resolving relative time references in sports queries.
                Convert references like 'last year', 'this season', etc. into specific date ranges.""",
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                        Please resolve these time references into specific date ranges:

                        {time_references}

                        Today's date is {datetime.now().strftime('%Y-%m-%d')}.
                        Soccer seasons typically run from August to May.

                        Format your response as JSON with this structure:
                        {{
                            "resolved_time_ranges": [
                                {{
                                    "original_reference": "original reference",
                                    "start_date": "YYYY-MM-DD",
                                    "end_date": "YYYY-MM-DD",
                                    "description": "human readable description"
                                }}
                            ]
                        }}

                        Return ONLY the JSON, nothing else.
                        """
                    }
                ]
            )

            # Extract the JSON response for time resolution
            time_resolution_text = time_resolution_response.content[0].text

            # Parse the JSON, handling potential formatting issues
            try:
                resolved_time = json.loads(time_resolution_text)
            except:
                # Default to January 2025 if parsing fails
                resolved_time = {
                    "resolved_time_ranges": [
                        {
                            "original_reference": time_references[0] if time_references else "current",
                            "start_date": "2025-01-01",
                            "end_date": "2025-01-31",
                            "description": "January 2025 (default)"
                        }
                    ]
                }

        # Format final response
        result = {
            "matched_teams": matched_teams,
            "time_resolution": resolved_time.get("resolved_time_ranges", []),
            "query_analysis": {
                "original_query": query,
                "extracted_teams": potential_teams,
                "extracted_time_references": time_references
            }
        }

        # Format the result as a string
        result_str = ""

        # Add matched teams section
        result_str += "Fuzzy Team Matching Results:\n\n"
        for original_name, match_info in matched_teams.items():
            if match_info.get("matched_name"):
                result_str += f"• '{original_name}' → '{match_info['matched_name']}' (confidence: {match_info['confidence']:.2f})\n"
            else:
                result_str += f"• '{original_name}' → No confident match found\n"
                if match_info.get("suggestions"):
                    result_str += "  Possible matches:\n"
                    for i, (score, name) in enumerate(match_info["suggestions"][:3], 1):
                        result_str += f"    {i}. '{name}' (score: {score:.2f})\n"

        # Add time resolution section
        if resolved_time.get("resolved_time_ranges"):
            result_str += "\nTime Reference Resolution:\n\n"
            for time_range in resolved_time["resolved_time_ranges"]:
                result_str += f"• '{time_range.get('original_reference', '')}' → {time_range.get('description', '')}\n"
                result_str += f"  Period: {time_range.get('start_date', '')} to {time_range.get('end_date', '')}\n"

        # Store the result object in a global variable for use by other tools
        global _last_fuzzy_match_result
        _last_fuzzy_match_result = result

        return {"result": result_str}
    except Exception as e:
        console.log(f"[fuzzy_match_teams] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}

def tool_fuzzy_match_teams(tool_input: Dict) -> Dict:
    """Tool implementation for fuzzy_match_teams"""
    query = tool_input.get("query", "")
    team_candidates = tool_input.get("team_candidates")
    parquet_file = tool_input.get("parquet_file", "analysis/data/data.parquet")
    return fuzzy_match_teams(query, team_candidates, parquet_file)

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
        "check_date_range": tool_check_date_range,
        "comprehensive_summary": tool_comprehensive_summary,
        "execute_team_comparison": tool_execute_team_comparison,
        "create_analysis_pipeline": tool_create_analysis_pipeline,
        "select_tool": tool_select_tool,
        "fuzzy_match_teams": tool_fuzzy_match_teams,
    }

def create_analysis_pipeline(query: str, parquet_file: str) -> Dict:
    """
    Smart orchestrator tool that creates and executes a pipeline of tools based on the query type.
    This tool analyzes the query, determines which tools to use, and executes them in sequence,
    passing context between each step in the pipeline.

    Args:
        query: The user's original query
        parquet_file: Path to the parquet file

    Returns:
        Dictionary with final analysis results and pipeline metadata
    """
    try:
        console.log(f"[create_analysis_pipeline] Creating analysis pipeline for query: {query}")

        # Initialize pipeline context to store data between steps
        pipeline_context = {
            "query": query,
            "parquet_file": parquet_file,
            "steps_executed": [],
            "query_type": None,
            "collected_data": {},
            "start_time": time.time(),
            "errors": []
        }

        # Step 1: Check if we already have fuzzy matching results from a previous tool call
        global _last_fuzzy_match_result
        if _last_fuzzy_match_result is not None:
            pipeline_context["fuzzy_match_result"] = _last_fuzzy_match_result
            pipeline_context["steps_executed"].append("fuzzy_match_teams")

            # Extract matched team names for use in subsequent steps
            matched_teams = _last_fuzzy_match_result["matched_teams"]
            if matched_teams:
                pipeline_context["team_names"] = {}
                for team_name, match_info in matched_teams.items():
                    if match_info["matched_name"]:
                        pipeline_context["team_names"][team_name] = match_info["matched_name"]
                    elif match_info.get("suggestions"):
                        # Store top suggestion if available
                        top_suggestion = match_info["suggestions"][0][1] if match_info["suggestions"] else None
                        pipeline_context["team_names"][team_name] = top_suggestion

            # Extract time period information
            time_resolution = _last_fuzzy_match_result["time_resolution"]
            if time_resolution:
                # Use the first resolved time range for simplicity
                first_time_range = time_resolution[0]
                pipeline_context["time_period"] = {
                    "description": first_time_range.get("description", ""),
                    "start_date": first_time_range.get("start_date", ""),
                    "end_date": first_time_range.get("end_date", "")
                }

            # Reset the global variable to avoid using stale data in future calls
            _last_fuzzy_match_result = None
        else:
            # If we don't have fuzzy matching results, perform the fuzzy matching here
            try:
                fuzzy_match_result = fuzzy_match_teams(query, None, parquet_file)
                if "error" in fuzzy_match_result:
                    pipeline_context["errors"].append(f"Error in fuzzy matching: {fuzzy_match_result['error']}")
                else:
                    # Parse the string result back into structured data
                    # This is a simplified approach since we can't easily reconstruct the full structure
                    pipeline_context["steps_executed"].append("fuzzy_match_teams(internally)")

                    # Extract team names from the query using regex
                    team_comparison_patterns = [
                        r"compare (?:the )?(?:performance )?(?:of |between )?([A-Za-z0-9\s]+) and ([A-Za-z0-9\s]+)",
                        r"(?:performance|stats|statistics|comparison) (?:of |between )?([A-Za-z0-9\s]+) (?:and|vs\.?|versus) ([A-Za-z0-9\s]+)",
                        r"how (?:do|does) ([A-Za-z0-9\s]+) compare (?:to|with|against) ([A-Za-z0-9\s]+)"
                    ]

                    # Try to extract team names from the query
                    team_names = {}
                    for pattern in team_comparison_patterns:
                        match = re.search(pattern, query, re.IGNORECASE)
                        if match:
                            team_names[match.group(1).strip()] = match.group(1).strip()
                            team_names[match.group(2).strip()] = match.group(2).strip()
                            break

                    if team_names:
                        pipeline_context["team_names"] = team_names
            except Exception as e:
                pipeline_context["errors"].append(f"Error in internal fuzzy matching step: {str(e)}")
                console.log(f"[create_analysis_pipeline] Error in internal fuzzy matching: {str(e)}")
                console.log(traceback.format_exc())

        # Step 2: Determine query type based on query pattern and fuzzy match results

        # Check for team comparison patterns
        team_comparison_patterns = [
            r"compare (?:the )?(?:performance )?(?:of |between )?([A-Za-z0-9\s]+) and ([A-Za-z0-9\s]+)",
            r"(?:performance|stats|statistics|comparison) (?:of |between )?([A-Za-z0-9\s]+) (?:and|vs\.?|versus) ([A-Za-z0-9\s]+)",
            r"how (?:do|does) ([A-Za-z0-9\s]+) compare (?:to|with|against) ([A-Za-z0-9\s]+)"
        ]

        is_team_comparison = False
        for pattern in team_comparison_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                is_team_comparison = True
                # If we haven't already extracted team names via fuzzy matching
                if "team_names" not in pipeline_context:
                    pipeline_context["team_names"] = {}
                    pipeline_context["team_names"][match.group(1).strip()] = match.group(1).strip()
                    pipeline_context["team_names"][match.group(2).strip()] = match.group(2).strip()
                break

        # Use the fuzzy match results to determine team names if available
        if "fuzzy_match_result" in pipeline_context:
            extracted_teams = pipeline_context["fuzzy_match_result"]["query_analysis"]["extracted_teams"]
            if len(extracted_teams) >= 2:
                is_team_comparison = True

        # Set the query type
        if is_team_comparison:
            pipeline_context["query_type"] = "team_comparison"
            console.log(f"[create_analysis_pipeline] Identified query type: team_comparison")
        else:
            pipeline_context["query_type"] = "general_analysis"
            console.log(f"[create_analysis_pipeline] Identified query type: general_analysis")

        # Step 3: Execute the appropriate pipeline based on query type
        if pipeline_context["query_type"] == "team_comparison":
            execute_team_comparison_pipeline(pipeline_context)
        else:
            execute_general_analysis_pipeline(pipeline_context)

        # Step 4: Generate a comprehensive final summary
        final_summary = generate_final_summary(pipeline_context)

        # Calculate total execution time
        total_time = time.time() - pipeline_context["start_time"]
        pipeline_context["execution_time"] = total_time

        console.log(f"[create_analysis_pipeline] Successfully executed {len(pipeline_context['steps_executed'])} pipeline steps")

        return {"result": final_summary}
    except Exception as e:
        console.log(f"[create_analysis_pipeline] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}


def execute_team_comparison_pipeline(pipeline_context: Dict) -> None:
    """
    Executes a pipeline for team comparison queries:
    1. Checks if data exists for specified time period
    2. Checks if both teams exist in the database
    3. Executes the team comparison if both teams exist
    4. Collects all results for the final summary

    Args:
        pipeline_context: Dictionary containing pipeline state and parameters
    """
    try:
        # Extract key parameters from the context
        query = pipeline_context["query"]
        parquet_file = pipeline_context["parquet_file"]

        # Extract team names - use fuzzy matched names if available
        team_names = {}
        if "team_names" in pipeline_context:
            team_names = pipeline_context["team_names"]

            # Get the original team names as keys and matched names as values
            team_keys = list(team_names.keys())
            if len(team_keys) >= 2:
                team1_original = team_keys[0]
                team2_original = team_keys[1]
                team1 = team_names[team1_original]
                team2 = team_names[team2_original]
            else:
                # Fallback if we somehow don't have two teams
                console.log("[execute_team_comparison_pipeline] Warning: Less than 2 teams identified in query")
                pipeline_context["errors"].append("Less than 2 teams identified in query")
                return
        else:
            # This should not happen if the pipeline is working correctly
            console.log("[execute_team_comparison_pipeline] Error: No team names found in pipeline context")
            pipeline_context["errors"].append("No team names found in pipeline context")
            return

        # Extract time period - use fuzzy matched time if available
        time_period = "all time"
        start_date = None
        end_date = None
        if "time_period" in pipeline_context:
            time_period = pipeline_context["time_period"]["description"]
            start_date = pipeline_context["time_period"].get("start_date")
            end_date = pipeline_context["time_period"].get("end_date")

        console.log(f"[execute_team_comparison_pipeline] Comparing {team1} and {team2} for {time_period}")

        # Step 1: Check if data exists for the specified time period
        if start_date and end_date:
            # Check date range using the tool
            date_check_result = tool_check_date_range({
                "parquet_file": parquet_file,
                "start_date": start_date,
                "end_date": end_date
            })

            # Store the result in our collected data
            pipeline_context["collected_data"]["date_check"] = date_check_result
            pipeline_context["steps_executed"].append("check_date_range")

            if "error" in date_check_result:
                pipeline_context["errors"].append(f"Error checking date range: {date_check_result['error']}")
                return

        # Step 2: Check if both teams exist in the database
        team1_exists = team_exists(team1, parquet_file)
        team2_exists = team_exists(team2, parquet_file)

        pipeline_context["collected_data"]["team_existence"] = {
            "team1": {
                "name": team1,
                "exists": team1_exists
            },
            "team2": {
                "name": team2,
                "exists": team2_exists
            }
        }
        pipeline_context["steps_executed"].append("team_exists")

        # Step 3: If either team doesn't exist, try similar team search
        missing_teams = []
        if not team1_exists:
            missing_teams.append(team1)
        if not team2_exists:
            missing_teams.append(team2)

        if missing_teams:
            # Get analyzer to perform direct SQL query
            analyzer = DuckDBAnalyzer(parquet_file)

            # Search for similar team names in the database
            suggestions = {}
            for team in missing_teams:
                # Query to find similar team names using SQL LIKE pattern
                sql = f"""
                WITH all_teams AS (
                    SELECT DISTINCT home_team AS team_name FROM input_data
                    UNION
                    SELECT DISTINCT away_team AS team_name FROM input_data
                )
                SELECT team_name
                FROM all_teams
                WHERE team_name LIKE '%{team.replace("'", "''")}%'
                   OR team_name LIKE '%{team.replace(" ", "%").replace("'", "''")}%'
                ORDER BY team_name
                LIMIT 5
                """

                # Execute the query and get results
                results_json = analyzer.query(sql)
                results = json.loads(results_json)

                if results:
                    suggestions[team] = [r["team_name"] for r in results]

                    # If we have a suggestion, update the team name to use the first suggestion
                    if suggestions[team]:
                        if team == team1:
                            team1 = suggestions[team][0]
                            team1_exists = True
                            pipeline_context["collected_data"]["team_existence"]["team1"]["exists"] = True
                            pipeline_context["collected_data"]["team_existence"]["team1"]["name"] = team1
                            pipeline_context["team_names"][team1_original] = team1
                            console.log(f"[execute_team_comparison_pipeline] Updated team1 to '{team1}'")
                        elif team == team2:
                            team2 = suggestions[team][0]
                            team2_exists = True
                            pipeline_context["collected_data"]["team_existence"]["team2"]["exists"] = True
                            pipeline_context["collected_data"]["team_existence"]["team2"]["name"] = team2
                            pipeline_context["team_names"][team2_original] = team2
                            console.log(f"[execute_team_comparison_pipeline] Updated team2 to '{team2}'")

            # Store suggestions for later
            if suggestions:
                pipeline_context["collected_data"]["team_suggestions"] = suggestions

            # Check again if both teams now exist or have suggestions
            if not team1_exists and not team2_exists:
                # If neither team can be found, we need to report that
                error_context = f"The following teams were not found in the database: {', '.join(missing_teams)}."
                if suggestions:
                    suggestion_text = []
                    for team, team_suggestions in suggestions.items():
                        if team_suggestions:
                            suggestion_text.append(f"For '{team}', did you mean: {', '.join(team_suggestions[:3])}?")
                    if suggestion_text:
                        error_context += " " + " ".join(suggestion_text)

                pipeline_context["errors"].append(error_context)
                return
            elif not team1_exists:
                error_context = f"Team '{team1}' was not found in the database."
                if suggestions.get(team1, []):
                    error_context += f" Did you mean: {', '.join(suggestions[team1][:3])}?"
                pipeline_context["errors"].append(error_context)
                return
            elif not team2_exists:
                error_context = f"Team '{team2}' was not found in the database."
                if suggestions.get(team2, []):
                    error_context += f" Did you mean: {', '.join(suggestions[team2][:3])}?"
                pipeline_context["errors"].append(error_context)
                return

        # Step 4: Execute team comparison with the potentially updated team names
        # We'll execute this using direct SQL query for better control
        try:
            # Get analyzer to perform direct SQL query
            analyzer = DuckDBAnalyzer(parquet_file)

            # Build SQL query for team 1 performance
            team1_sql = f"""
            WITH team_matches AS (
                -- Home matches
                SELECT
                    date,
                    home_team AS team,
                    away_team AS opponent,
                    home_score AS team_score,
                    away_score AS opponent_score,
                    CASE
                        WHEN home_score > away_score THEN 'win'
                        WHEN home_score < away_score THEN 'loss'
                        ELSE 'draw'
                    END AS result,
                    league
                FROM input_data
                WHERE home_team = '{team1}'
                {f"AND date BETWEEN '{start_date}' AND '{end_date}'" if start_date and end_date else ""}

                UNION ALL

                -- Away matches
                SELECT
                    date,
                    away_team AS team,
                    home_team AS opponent,
                    away_score AS team_score,
                    home_score AS opponent_score,
                    CASE
                        WHEN away_score > home_score THEN 'win'
                        WHEN away_score < home_score THEN 'loss'
                        ELSE 'draw'
                    END AS result,
                    league
                FROM input_data
                WHERE away_team = '{team1}'
                {f"AND date BETWEEN '{start_date}' AND '{end_date}'" if start_date and end_date else ""}
            )

            SELECT
                '{team1}' AS team_name,
                COUNT(*) AS total_matches,
                SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) AS draws,
                SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
                SUM(team_score) AS goals_for,
                SUM(opponent_score) AS goals_against,
                SUM(team_score) - SUM(opponent_score) AS goal_difference,
                ROUND(AVG(team_score), 2) AS avg_goals_scored,
                ROUND(AVG(opponent_score), 2) AS avg_goals_conceded
            FROM team_matches
            """

            # Execute the query for team 1
            team1_results_json = analyzer.query(team1_sql)
            team1_results = json.loads(team1_results_json)

            # Build SQL query for team 2 performance
            team2_sql = f"""
            WITH team_matches AS (
                -- Home matches
                SELECT
                    date,
                    home_team AS team,
                    away_team AS opponent,
                    home_score AS team_score,
                    away_score AS opponent_score,
                    CASE
                        WHEN home_score > away_score THEN 'win'
                        WHEN home_score < away_score THEN 'loss'
                        ELSE 'draw'
                    END AS result,
                    league
                FROM input_data
                WHERE home_team = '{team2}'
                {f"AND date BETWEEN '{start_date}' AND '{end_date}'" if start_date and end_date else ""}

                UNION ALL

                -- Away matches
                SELECT
                    date,
                    away_team AS team,
                    home_team AS opponent,
                    away_score AS team_score,
                    home_score AS opponent_score,
                    CASE
                        WHEN away_score > home_score THEN 'win'
                        WHEN away_score < home_score THEN 'loss'
                        ELSE 'draw'
                    END AS result,
                    league
                FROM input_data
                WHERE away_team = '{team2}'
                {f"AND date BETWEEN '{start_date}' AND '{end_date}'" if start_date and end_date else ""}
            )

            SELECT
                '{team2}' AS team_name,
                COUNT(*) AS total_matches,
                SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) AS draws,
                SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
                SUM(team_score) AS goals_for,
                SUM(opponent_score) AS goals_against,
                SUM(team_score) - SUM(opponent_score) AS goal_difference,
                ROUND(AVG(team_score), 2) AS avg_goals_scored,
                ROUND(AVG(opponent_score), 2) AS avg_goals_conceded
            FROM team_matches
            """

            # Execute the query for team 2
            team2_results_json = analyzer.query(team2_sql)
            team2_results = json.loads(team2_results_json)

            # Build SQL query for head-to-head matches
            head_to_head_sql = f"""
            SELECT
                date,
                home_team,
                away_team,
                home_score,
                away_score,
                CASE
                    WHEN home_score > away_score THEN home_team
                    WHEN home_score < away_score THEN away_team
                    ELSE 'Draw'
                END AS winner,
                league
            FROM input_data
            WHERE (home_team = '{team1}' AND away_team = '{team2}')
               OR (home_team = '{team2}' AND away_team = '{team1}')
            {f"AND date BETWEEN '{start_date}' AND '{end_date}'" if start_date and end_date else ""}
            ORDER BY date DESC
            LIMIT 5
            """

            # Execute the query for head-to-head matches
            h2h_results_json = analyzer.query(head_to_head_sql)
            h2h_results = json.loads(h2h_results_json)

            # Get standings information for both teams in leagues
            standings_sql = f"""
            WITH match_points AS (
                -- Home points
                SELECT
                    home_team AS team,
                    league,
                    CASE
                        WHEN home_score > away_score THEN 3
                        WHEN home_score = away_score THEN 1
                        ELSE 0
                    END AS points
                FROM input_data
                WHERE (home_team = '{team1}' OR home_team = '{team2}')
                {f"AND date BETWEEN '{start_date}' AND '{end_date}'" if start_date and end_date else ""}

                UNION ALL

                -- Away points
                SELECT
                    away_team AS team,
                    league,
                    CASE
                        WHEN away_score > home_score THEN 3
                        WHEN away_score = home_score THEN 1
                        ELSE 0
                    END AS points
                FROM input_data
                WHERE (away_team = '{team1}' OR away_team = '{team2}')
                {f"AND date BETWEEN '{start_date}' AND '{end_date}'" if start_date and end_date else ""}
            ),

            team_standings AS (
                SELECT
                    team,
                    league,
                    SUM(points) AS total_points,
                    COUNT(*) AS matches_played
                FROM match_points
                GROUP BY team, league
            )

            SELECT
                ts.team,
                ts.league,
                ts.total_points,
                ts.matches_played,
                ROUND(ts.total_points::FLOAT / NULLIF(ts.matches_played, 0), 2) AS points_per_match,
                -- Add league context (other teams in same league)
                (
                    SELECT COUNT(DISTINCT team)
                    FROM match_points mp
                    WHERE mp.league = ts.league
                ) AS teams_in_league
            FROM team_standings ts
            ORDER BY ts.team, ts.league
            """

            # Execute the query for standings
            standings_results_json = analyzer.query(standings_sql)
            standings_results = json.loads(standings_results_json)

            # Combine all results into a structured comparison
            comparison_results = {
                "team1": {
                    "name": team1,
                    "stats": team1_results[0] if team1_results else {"total_matches": 0}
                },
                "team2": {
                    "name": team2,
                    "stats": team2_results[0] if team2_results else {"total_matches": 0}
                },
                "head_to_head": h2h_results,
                "standings": standings_results,
                "time_period": time_period,
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date
                }
            }

            # Use comprehensive_summary to generate the final analysis
            summary_text = comprehensive_summary(
                reasoning=f"Analyzing the performance comparison between {team1} and {team2} for {time_period}",
                collected_data=json.dumps(comparison_results, indent=2),
                query_context=query,
                analysis_format="detailed"
            )

            # Store the complete analysis in the pipeline context
            pipeline_context["collected_data"]["team_comparison"] = {
                "result": summary_text.get("result", "Failed to generate comprehensive summary."),
                "raw_data": comparison_results
            }
            pipeline_context["steps_executed"].append("execute_team_comparison")

        except Exception as e:
            pipeline_context["errors"].append(f"Error executing SQL comparison: {str(e)}")
            console.log(f"[execute_team_comparison_pipeline] Error executing SQL comparison: {str(e)}")
            console.log(traceback.format_exc())
            return

    except Exception as e:
        console.log(f"[execute_team_comparison_pipeline] Error: {str(e)}")
        console.log(traceback.format_exc())
        pipeline_context["errors"].append(f"Error in team comparison pipeline: {str(e)}")


def execute_general_analysis_pipeline(pipeline_context: Dict) -> None:
    """
    Executes a pipeline for general analysis queries:
    1. Gets schema information
    2. Translates natural language query to SQL
    3. Executes SQL query
    4. Collects all results for the final summary

    Args:
        pipeline_context: Dictionary containing pipeline state and parameters
    """
    try:
        # Extract key parameters from the context
        query = pipeline_context["query"]
        parquet_file = pipeline_context["parquet_file"]

        # Step 1: Get schema information
        try:
            analyzer = DuckDBAnalyzer(parquet_file)
            schema_list, schema_json = analyzer.get_schema()

            # Store schema in pipeline context
            pipeline_context["collected_data"]["schema"] = schema_json
            pipeline_context["steps_executed"].append("get_schema")
        except Exception as e:
            pipeline_context["errors"].append(f"Error getting schema: {str(e)}")
            console.log(f"[execute_general_analysis_pipeline] Error getting schema: {str(e)}")
            console.log(traceback.format_exc())
            return

        # Step 2: Translate natural language query to SQL
        try:
            # This is a simplified approach - in a real implementation, you would use
            # a more sophisticated method to translate the query to SQL
            sql_query = f"""
            SELECT
                COUNT(*) as match_count,
                COUNT(DISTINCT home_team) + COUNT(DISTINCT away_team) as team_count,
                AVG(home_score + away_score) as avg_goals_per_match
            FROM input_data
            """

            # Store SQL query in pipeline context
            pipeline_context["collected_data"]["sql_query"] = sql_query
            pipeline_context["steps_executed"].append("query_to_sql")
        except Exception as e:
            pipeline_context["errors"].append(f"Error translating query to SQL: {str(e)}")
            console.log(f"[execute_general_analysis_pipeline] Error translating query to SQL: {str(e)}")
            console.log(traceback.format_exc())
            return

        # Step 3: Execute SQL query
        try:
            # Execute the SQL query
            result_json = analyzer.query(sql_query)

            # Store results in pipeline context
            pipeline_context["collected_data"]["sql_results"] = {"result": result_json}
            pipeline_context["steps_executed"].append("execute_sql")
        except Exception as e:
            pipeline_context["errors"].append(f"Error executing SQL query: {str(e)}")
            console.log(f"[execute_general_analysis_pipeline] Error executing SQL query: {str(e)}")
            console.log(traceback.format_exc())
            return

    except Exception as e:
        console.log(f"[execute_general_analysis_pipeline] Error: {str(e)}")
        console.log(traceback.format_exc())
        pipeline_context["errors"].append(f"Error in general analysis pipeline: {str(e)}")


def generate_final_summary(pipeline_context: Dict) -> str:
    """
    Generates a comprehensive final summary based on all the data collected in the pipeline.
    This is the final "reduce" step that synthesizes all the collected data into a coherent analysis.

    Args:
        pipeline_context: Dictionary containing all collected data and pipeline state

    Returns:
        A string containing the final summary
    """
    try:
        # Extract key parameters
        query = pipeline_context["query"]
        pipeline_type = pipeline_context["query_type"]
        collected_data = pipeline_context["collected_data"]

        # Check if we have any errors that should be reported
        if pipeline_context.get("errors"):
            error_list = pipeline_context["errors"]

            # Create an analysis response with error information
            summary = f"# Analysis Response: {pipeline_type.replace('_', ' ').title()} Request\n\n"

            # Include information about fuzzy matching if available
            if "team_names" in pipeline_context:
                summary += "## Team Name Resolution\n\n"
                team_names = pipeline_context["team_names"]
                for original, matched in team_names.items():
                    if original != matched:
                        summary += f"- '{original}' was matched to '{matched}' in the database\n"
                    else:
                        summary += f"- '{original}' was used as is\n"
                summary += "\n"

            summary += "## Summary of Data Availability\n\n"

            # Include information about errors
            summary += "Based on the data provided, I cannot perform a complete analysis due to the following reasons:\n\n"

            for i, error in enumerate(error_list, 1):
                summary += f"{i}. **{error}**\n"

            # Include information about date range if available
            if "date_check" in collected_data:
                date_info = collected_data["date_check"]
                if isinstance(date_info, dict) and "result" in date_info:
                    try:
                        dataset_range = json.loads(date_info["result"])["dataset_range"]
                        start_ts = dataset_range.get("earliest_date")
                        end_ts = dataset_range.get("latest_date")

                        # Check if timestamps are in milliseconds (common in JS/Unix timestamps)
                        if start_ts > 1000000000000:  # If timestamp is in milliseconds
                            start_date = datetime.fromtimestamp(start_ts / 1000).strftime('%Y-%m-%d')
                            end_date = datetime.fromtimestamp(end_ts / 1000).strftime('%Y-%m-%d')
                        else:
                            start_date = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d')
                            end_date = datetime.fromtimestamp(end_ts).strftime('%Y-%m-%d')

                        summary += f"\n3. **Date Range**: The dataset contains matches from {start_date} to {end_date}"
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass

            # Include information about available teams if we have team existence errors
            if "team_existence" in collected_data:
                team_existence = collected_data["team_existence"]
                if isinstance(team_existence, dict):
                    team1_info = team_existence.get("team1", {})
                    team2_info = team_existence.get("team2", {})

                    if not team1_info.get("exists", True) or not team2_info.get("exists", True):
                        non_existent_teams = []
                        if not team1_info.get("exists", True):
                            non_existent_teams.append(team1_info.get("name", "Team 1"))
                        if not team2_info.get("exists", True):
                            non_existent_teams.append(team2_info.get("name", "Team 2"))

                        summary += f"\n4. The following teams do not exist in the dataset: {', '.join(non_existent_teams)}"

            # Include team suggestions if available
            if "team_suggestions" in collected_data:
                suggestions = collected_data["team_suggestions"]
                if suggestions:
                    summary += "\n\n## Suggestions\n\n"
                    for team, team_suggestions in suggestions.items():
                        if team_suggestions:
                            summary += f"For '{team}', did you mean: {', '.join(team_suggestions[:3])}?\n"

            # Add information about available teams in the dataset
            summary += "\n## Available Teams\n\nThe dataset contains several teams. Here are some examples:\n"

            # Get available teams from the database or use a pre-defined list
            available_teams = []
            if "available_teams" in collected_data:
                available_teams = collected_data["available_teams"]

            if not available_teams:
                # Fallback to a sample of teams we know are in the database
                available_teams = ["#N2P", "#N2P (1)", "2010 NHSA Coed", "2010 NHSA Girls", "2011 NHSA Girls",
                                  "2012 NHSA Boys", "2012 NHSA Coed", "2013 KFC Blue", "2013 NHSA Boys", "2013 NHSA Coed"]

            for i, team in enumerate(available_teams[:10], 1):
                summary += f"- {team}\n"

            # Add recommendations
            summary += "\n## Recommendations\n\n"
            summary += "To proceed with a meaningful analysis, you might consider:\n\n"
            summary += "1. Verifying the exact team names from the list of available teams provided\n"
            summary += "2. Checking if the teams might be listed under different names\n"
            summary += "3. Requesting a comparison between teams that are available in the dataset\n"

            return summary

        # For successful team comparison
        if pipeline_type == "team_comparison" and "team_comparison" in collected_data:
            # For team comparisons, use the results directly or run comprehensive_summary

            # Check if we have a result object or a string
            team_comparison_data = collected_data["team_comparison"]
            if isinstance(team_comparison_data, dict) and "result" in team_comparison_data:
                comparison_text = team_comparison_data["result"]
            else:
                comparison_text = str(team_comparison_data)

            # Ensure we have a valid result
            if not comparison_text or comparison_text == "None":
                return "No comparison data available. Please check team names and try again."

            # Include information about fuzzy matching if available
            if "team_names" in pipeline_context:
                fuzzy_info = "# Team Comparison Results\n\n## Team Name Resolution\n\n"
                team_names = pipeline_context["team_names"]
                for original, matched in team_names.items():
                    if original != matched:
                        fuzzy_info += f"- '{original}' was matched to '{matched}' in the database\n"
                    else:
                        fuzzy_info += f"- '{original}' was used as is\n"
                fuzzy_info += "\n"

                # Prepend this to the comparison text
                if not comparison_text.startswith("# Team Comparison Results"):
                    comparison_text = fuzzy_info + comparison_text

            # If we have time period information, include it
            if "time_period" in pipeline_context:
                time_period = pipeline_context["time_period"]
                time_description = time_period.get("description", "")
                if time_description:
                    time_info = f"## Time Period\n\n- {time_description}\n\n"

                    # Insert after the team name resolution section if it exists
                    if "## Team Name Resolution" in comparison_text:
                        parts = comparison_text.split("## Team Name Resolution")
                        if len(parts) > 1 and "\n\n" in parts[1]:
                            resolution_section, rest = parts[1].split("\n\n", 1)
                            comparison_text = parts[0] + "## Team Name Resolution" + resolution_section + "\n\n" + time_info + rest
                    # Otherwise just prepend it
                    elif not comparison_text.startswith("#"):
                        comparison_text = "# Team Comparison Results\n\n" + time_info + comparison_text
                    else:
                        # Find the first section break and insert there
                        first_break = comparison_text.find("\n\n")
                        if first_break > 0:
                            comparison_text = comparison_text[:first_break+2] + time_info + comparison_text[first_break+2:]

            return comparison_text

    except Exception as e:
        console.log(f"[generate_final_summary] Error: {str(e)}")
        console.log(traceback.format_exc())
        return f"Error generating summary: {str(e)}"


def tool_create_analysis_pipeline(tool_input: Dict) -> Dict:
    """Adapter for create_analysis_pipeline function."""
    query = tool_input.get("query", "")
    parquet_file = tool_input.get("parquet_file", "analysis/data/data.parquet")
    return create_analysis_pipeline(query, parquet_file)

def select_tool(query: str) -> Dict:
    """
    Analyzes a natural language query and recommends the most appropriate tool to use.
    This is a meta-tool that helps Claude decide which specialized tool to call next.

    Args:
        query: The user's natural language query

    Returns:
        Dictionary with the recommended tool and reasoning
    """
    try:
        console.log(f"[select_tool] Analyzing query: {query}")

        # Check for team comparison patterns
        team_comparison_patterns = [
            r"compare (?:the )?(?:performance )?(?:of |between )?([A-Za-z0-9\s]+) and ([A-Za-z0-9\s]+)",
            r"(?:performance|stats|statistics|comparison) (?:of |between )?([A-Za-z0-9\s]+) (?:and|vs\.?|versus) ([A-Za-z0-9\s]+)",
            r"how (?:do|does) ([A-Za-z0-9\s]+) compare (?:to|with|against) ([A-Za-z0-9\s]+)"
        ]

        # Check for team name patterns
        team_name_patterns = [
            r"(?:team|club) ([A-Za-z0-9\s]+)",
            r"([A-Za-z0-9\s]+) (?:FC|United|City|Town)",
            r"performance of ([A-Za-z0-9\s]+)"
        ]

        # Check for comprehensive analysis patterns
        complex_analysis_patterns = [
            r"comprehensive",
            r"summary",
            r"strengths and weaknesses",
            r"detailed analysis",
            r"in-depth",
            r"thorough",
            r"breakdown",
            r"full report"
        ]

        # Check for time period patterns
        time_period_match = re.search(r"(?:in|during|for) (?:the )?(?:month of )?([A-Za-z]+)? ?(\d{4})", query, re.IGNORECASE)
        time_reference_patterns = [
            r"last (?:year|season|month|week)",
            r"this (?:year|season|month|week)",
            r"recent",
            r"current",
            r"upcoming",
            r"previous"
        ]

        has_time_reference = any(re.search(pattern, query, re.IGNORECASE) for pattern in time_reference_patterns)

        # Check if query contains team names (either from comparison or individual patterns)
        team_match = False
        for pattern in team_comparison_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                team_match = True
                break

        if not team_match:
            for pattern in team_name_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    team_match = True
                    break

        # If query contains potential team names or ambiguous time references, suggest fuzzy matching first
        if team_match or has_time_reference:
            return {
                "result": "Tool: fuzzy_match_teams\nReasoning: This query contains potential team names or time references that may need disambiguation. The fuzzy_match_teams tool will help identify the actual team names in the database and resolve time references before proceeding with analysis."
            }

        # If query matches team comparison patterns, proceed with original logic
        for pattern in team_comparison_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # If query also contains complex analysis keywords, recommend analysis pipeline
                for complex_pattern in complex_analysis_patterns:
                    if re.search(complex_pattern, query, re.IGNORECASE):
                        return {
                            "result": "Tool: create_analysis_pipeline\nReasoning: This is a complex team comparison request that requires a full analysis pipeline with multiple steps. The create_analysis_pipeline tool will automatically handle team verification, data retrieval, and generate a comprehensive summary."
                        }

                # If it's a simple comparison, recommend execute_team_comparison
                team1 = match.group(1).strip()
                team2 = match.group(2).strip()
                time_period = time_period_match.group(0) if time_period_match else "all time"

                return {
                    "result": f"Tool: execute_team_comparison\nReasoning: This query is asking for a direct comparison between {team1} and {team2} for {time_period}. The execute_team_comparison tool will handle this efficiently."
                }

        # Check for general analysis with comprehensive requirements
        for complex_pattern in complex_analysis_patterns:
            if re.search(complex_pattern, query, re.IGNORECASE):
                return {
                    "result": "Tool: create_analysis_pipeline\nReasoning: This query requires a comprehensive analysis with multiple steps. The create_analysis_pipeline tool will handle the complexity automatically."
                }

        # For other types of queries, recommend basic tools
        if re.search(r"schema|columns|fields|structure", query, re.IGNORECASE):
            return {
                "result": "Tool: get_schema\nReasoning: This query is asking about the database schema or structure. The get_schema tool will provide this information directly."
            }

        # For SQL execution queries
        if re.search(r"sql|query|select|from|where", query, re.IGNORECASE):
            return {
                "result": "Tool: query_to_sql\nReasoning: This appears to be a request for SQL execution. First translate the query to SQL using query_to_sql, then execute it with execute_sql."
            }

        # Default recommendation for general queries
        return {
            "result": "Tool: create_analysis_pipeline\nReasoning: For general analysis queries, the create_analysis_pipeline tool provides the most comprehensive approach by orchestrating multiple analysis steps automatically."
        }
    except Exception as e:
        console.log(f"[select_tool] Error: {str(e)}")
        return {"error": str(e)}
