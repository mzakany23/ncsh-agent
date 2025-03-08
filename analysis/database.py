"""
Database Module for Soccer Data Analysis

This module provides comprehensive database operations using DuckDB, including:
- Query execution and validation
- Schema extraction
- SQL translation from natural language
- Data visualization
- Statistical analysis
- Dataset building and manipulation

It serves as the core data layer for the analysis package.
"""

import os
import json
import traceback
import pandas as pd
import duckdb
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Optional, Tuple
import io
import base64
from rich.console import Console

# Initialize console for rich output
console = Console()

class DuckDBAnalyzer:
    """
    DuckDB analyzer for soccer data.

    This class provides methods to interact with DuckDB and execute queries
    against a Parquet file containing soccer match data.
    """

    def __init__(self, parquet_file: str):
        """
        Initialize the DuckDB analyzer.

        Args:
            parquet_file: Path to the parquet file
        """
        self.parquet_file = parquet_file
        self.conn = duckdb.connect(database=':memory:')
        self._register_data()

    def _register_data(self):
        """Register data from parquet file in DuckDB."""
        try:
            self.conn.execute(f"CREATE OR REPLACE TABLE input_data AS SELECT * FROM '{self.parquet_file}'")
        except Exception as e:
            console.print(f"[red]Failed to load data: {str(e)}[/red]")
            raise

    def get_schema(self) -> Tuple[List[Dict[str, str]], str]:
        """
        Get schema information for the dataset.

        Returns:
            A tuple containing:
            - List of dictionaries with column information
            - JSON string representation of the schema
        """
        try:
            # Get the schema as a DataFrame
            schema_df = self.conn.execute("DESCRIBE SELECT * FROM input_data").fetchdf()

            # Convert to list of dictionaries
            schema_list = []
            for _, row in schema_df.iterrows():
                col_info = {
                    "column_name": row['column_name'],
                    "data_type": row['column_type'] if 'column_type' in row else row['data_type']
                }

                # Only add column_index if it exists
                if 'column_index' in row:
                    col_info["column_index"] = row['column_index']

                schema_list.append(col_info)

            # Create a JSON string representation
            schema_json = json.dumps(schema_list)

            return schema_list, schema_json
        except Exception as e:
            console.print(f"[red]Failed to get schema: {str(e)}[/red]")
            return [], "[]"

    def query(self, query: str) -> str:
        """
        Execute a SQL query and return results as a JSON string.

        Args:
            query: SQL query to execute

        Returns:
            JSON string with query results
        """
        try:
            # Execute the query and fetch as a DataFrame
            result_df = self.conn.execute(query).fetchdf()

            # Convert to JSON
            result_json = result_df.to_json(orient='records')

            return result_json
        except Exception as e:
            error_message = str(e)
            tb_str = traceback.format_exc()
            console.print(f"[red]Error executing query: {error_message}[/red]")
            console.print(f"[red]{tb_str}[/red]")
            return json.dumps([{"error": error_message}])

    def execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SQL query and return results in various formats.

        Args:
            query: SQL query to execute

        Returns:
            Dictionary with query results in different formats
        """
        try:
            # Execute the query and fetch as a DataFrame
            result_df = self.conn.execute(query).fetchdf()

            # Basic results
            result = {
                "success": True,
                "row_count": len(result_df),
                "column_count": len(result_df.columns),
                "columns": list(result_df.columns),
                "json": result_df.to_json(orient='records'),
                "csv": result_df.to_csv(index=False),
            }

            # Add Table format if not too large
            if len(result_df) <= 1000:
                result["table"] = result_df.to_string(index=False)

            # Add HTML format if not too large
            if len(result_df) <= 1000:
                result["html"] = result_df.to_html(index=False)

            return result
        except Exception as e:
            error_message = str(e)
            tb_str = traceback.format_exc()
            console.print(f"[red]Error executing query: {error_message}[/red]")
            console.print(f"[red]{tb_str}[/red]")
            return {
                "success": False,
                "error": error_message,
                "traceback": tb_str
            }

    def validate_query(self, query: str) -> Dict[str, Any]:
        """
        Validate a SQL query without executing it.

        Args:
            query: SQL query to validate

        Returns:
            Dictionary with validation result
        """
        try:
            # Try to prepare the query, which will validate syntax
            self.conn.prepare(query)
            return {
                "success": True,
                "is_valid": True,
                "message": "Query is valid."
            }
        except Exception as e:
            error_message = str(e)
            return {
                "success": True,
                "is_valid": False,
                "message": f"Query is invalid: {error_message}"
            }

    def translate_query_to_sql(self, question: str, schema_info: Optional[str] = None) -> Dict[str, Any]:
        """
        Translate a natural language question to SQL.

        This method uses Claude to translate the question to SQL.

        Args:
            question: Natural language question
            schema_info: Optional schema information string

        Returns:
            Dictionary with translation result
        """
        # In a real implementation, this would use Claude or another LLM
        # to translate the question to SQL. For now, we return an error.
        return {
            "success": False,
            "error": "Query translation not implemented in DuckDBAnalyzer"
        }

    def generate_chart(self, query: str, chart_type: str = 'bar',
                      x_column: Optional[str] = None, y_column: Optional[str] = None,
                      title: Optional[str] = None) -> str:
        """
        Generate a chart for the results of a SQL query.

        Args:
            query: SQL query to execute
            chart_type: Type of chart to generate ('bar', 'line', 'scatter', 'pie')
            x_column: Column to use for x-axis
            y_column: Column to use for y-axis
            title: Chart title

        Returns:
            Base64-encoded PNG image data for the chart
        """
        try:
            # Execute the query
            df = self.conn.execute(query).fetchdf()

            if len(df) == 0:
                return "No data returned by query"

            # Create a figure and axis
            plt.figure(figsize=(10, 6))

            # Determine x and y columns if not provided
            if x_column is None:
                x_column = df.columns[0]
            if y_column is None and len(df.columns) > 1:
                y_column = df.columns[1]
            elif y_column is None:
                y_column = df.columns[0]

            # Generate the chart based on the type
            if chart_type == 'bar':
                df.plot(kind='bar', x=x_column, y=y_column)
            elif chart_type == 'line':
                df.plot(kind='line', x=x_column, y=y_column)
            elif chart_type == 'scatter':
                df.plot(kind='scatter', x=x_column, y=y_column)
            elif chart_type == 'pie' and y_column:
                df.plot(kind='pie', y=y_column)
            else:
                return f"Unsupported chart type: {chart_type}"

            # Set title if provided
            if title:
                plt.title(title)

            # Save to a bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)

            # Convert to base64
            image_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()

            return f"data:image/png;base64,{image_base64}"
        except Exception as e:
            error_message = str(e)
            tb_str = traceback.format_exc()
            console.print(f"[red]Error generating chart: {error_message}[/red]")
            console.print(f"[red]{tb_str}[/red]")
            return f"Error generating chart: {error_message}"

    def get_summary_statistics(self, column_name: str) -> Dict[str, Any]:
        """
        Get summary statistics for a column.

        Args:
            column_name: Name of the column to analyze

        Returns:
            Dictionary with summary statistics
        """
        try:
            # Check if column exists
            schema_list, _ = self.get_schema()
            if column_name not in [col['column_name'] for col in schema_list]:
                return {
                    "success": False,
                    "error": f"Column '{column_name}' not found in dataset"
                }

            # Get summary statistics using SQL
            query = f"""
            SELECT
                COUNT({column_name}) as count,
                COUNT(DISTINCT {column_name}) as unique_count,
                MIN({column_name}) as min_value,
                MAX({column_name}) as max_value,
                AVG({column_name}) as avg_value,
                STDDEV({column_name}) as std_dev
            FROM input_data
            WHERE {column_name} IS NOT NULL
            """

            stats_df = self.conn.execute(query).fetchdf()

            # Convert to dictionary
            stats = stats_df.to_dict('records')[0]

            # Get top 5 most frequent values
            freq_query = f"""
            SELECT {column_name} as value, COUNT(*) as frequency
            FROM input_data
            WHERE {column_name} IS NOT NULL
            GROUP BY {column_name}
            ORDER BY frequency DESC
            LIMIT 5
            """

            freq_df = self.conn.execute(freq_query).fetchdf()

            # Convert to list of dictionaries
            freq_values = freq_df.to_dict('records')

            return {
                "success": True,
                "column": column_name,
                "statistics": stats,
                "most_frequent": freq_values
            }
        except Exception as e:
            error_message = str(e)
            return {
                "success": False,
                "error": error_message
            }

    def get_unique_values(self, column_name: str, limit: int = 100) -> List[Any]:
        """
        Get unique values for a column.

        Args:
            column_name: Name of the column to analyze
            limit: Maximum number of unique values to return

        Returns:
            List of unique values
        """
        try:
            # Check if column exists
            schema_list, _ = self.get_schema()
            if column_name not in [col['column_name'] for col in schema_list]:
                return []

            # Get unique values using SQL
            query = f"""
            SELECT DISTINCT {column_name} as value
            FROM input_data
            WHERE {column_name} IS NOT NULL
            ORDER BY {column_name}
            LIMIT {limit}
            """

            result_df = self.conn.execute(query).fetchdf()

            # Convert to list
            return result_df['value'].tolist()
        except Exception as e:
            error_message = str(e)
            console.print(f"[red]Error getting unique values: {error_message}[/red]")
            return []


# Standalone functions (not part of the DuckDBAnalyzer class)

def execute_sql(reasoning: str, query: str, parquet_file: str) -> Dict:
    """
    Execute a SQL query against a DuckDB database loaded from a Parquet file.

    Args:
        reasoning: Reasoning for executing the query
        query: SQL query to execute
        parquet_file: Path to the Parquet file to load

    Returns:
        Dictionary with query results
    """
    try:
        # Initialize analyzer
        analyzer = DuckDBAnalyzer(parquet_file)

        # Execute query
        result_json = analyzer.query(query)

        return {"result": result_json}
    except Exception as e:
        error_message = str(e)
        return {"error": error_message}


def get_schema(reasoning: str, parquet_file: str) -> Dict:
    """
    Get the schema for a DuckDB database loaded from a Parquet file.

    Args:
        reasoning: Reasoning for getting the schema
        parquet_file: Path to the Parquet file to load

    Returns:
        Dictionary with schema information
    """
    try:
        # Initialize analyzer
        analyzer = DuckDBAnalyzer(parquet_file)

        # Get schema
        schema_list, schema_json = analyzer.get_schema()

        return {"result": schema_json}
    except Exception as e:
        error_message = str(e)
        return {"error": error_message}


def validate_sql(reasoning: str, query: str) -> Dict:
    """
    Validate a SQL query without executing it.

    Args:
        reasoning: Reasoning for validating the query
        query: SQL query to validate

    Returns:
        Dictionary with validation result
    """
    try:
        # Initialize analyzer with empty database
        analyzer = DuckDBAnalyzer(":memory:")

        # Validate query
        validation_result = analyzer.validate_query(query)

        if validation_result["is_valid"]:
            return {"result": "The SQL query is valid."}
        else:
            return {"error": validation_result["message"]}
    except Exception as e:
        error_message = str(e)
        return {"error": error_message}


def query_to_sql(reasoning: str, question: str, schema_info: str) -> Dict:
    """
    Convert a natural language question to SQL.

    Args:
        reasoning: Reasoning for the query translation
        question: Natural language question
        schema_info: Schema information JSON string

    Returns:
        Dictionary with SQL translation
    """
    try:
        # This would typically use Claude to translate
        # For now, return a simple message
        return {"error": "Query translation must be handled by Claude"}
    except Exception as e:
        error_message = str(e)
        return {"error": error_message}


def compact_dataset(parquet_file: str, output_format: str = "compact") -> Dict[str, Any]:
    """
    Create a compact representation of match data optimized for Claude's context window.

    Args:
        parquet_file: Path to the Parquet file containing match data
        output_format: Format style ('compact', 'table', or 'csv')

    Returns:
        Dictionary with compact dataset representation
    """
    try:
        # Initialize analyzer
        analyzer = DuckDBAnalyzer(parquet_file)

        # Define the query based on the requested format
        if output_format == "table":
            # More detailed table format
            query = """
            SELECT
                date,
                home_team,
                away_team,
                home_score,
                away_score,
                league
            FROM input_data
            ORDER BY date, league, home_team
            """
        elif output_format == "csv":
            # CSV format with essential fields
            query = """
            SELECT
                date,
                home_team,
                away_team,
                home_score,
                away_score,
                league
            FROM input_data
            ORDER BY date, league, home_team
            """
        else:
            # Super compact format
            query = """
            SELECT
                date,
                CONCAT(
                    home_team, ' ',
                    home_score, '-',
                    away_score, ' ',
                    away_team,
                    ' (', league, ')'
                ) AS match_summary
            FROM input_data
            ORDER BY date, league, home_team
            """

        # Execute the query
        result = analyzer.execute_query(query)

        if not result["success"]:
            return {"error": result["error"]}

        # Format the output based on the requested format
        if output_format == "table":
            output = result["table"]
        elif output_format == "csv":
            output = result["csv"]
        else:
            # Process the compact format
            data = json.loads(result["json"])
            lines = []
            current_date = None

            # Group matches by date
            for match in data:
                if match["date"] != current_date:
                    if current_date is not None:
                        lines.append("")  # Empty line between dates
                    lines.append(f"===== {match['date']} =====")
                    current_date = match["date"]
                lines.append(match["match_summary"])

            output = "\n".join(lines)

        # Calculate size metrics
        original_size = os.path.getsize(parquet_file)
        compact_size = len(output.encode('utf-8'))
        compression_ratio = original_size / compact_size if compact_size > 0 else 0

        return {
            "success": True,
            "row_count": result["row_count"],
            "original_size_bytes": original_size,
            "compact_size_bytes": compact_size,
            "compression_ratio": round(compression_ratio, 2),
            "result": output
        }
    except Exception as e:
        error_message = str(e)
        tb_str = traceback.format_exc()
        console.print(f"[red]Error creating compact dataset: {error_message}[/red]")
        console.print(f"[red]{tb_str}[/red]")
        return {
            "success": False,
            "error": error_message
        }


def build_dataset(team: str, parquet_file: str, output_file: str) -> Dict[str, Any]:
    """
    Create a filtered dataset for a specific team and save it as a new parquet file.

    Args:
        team: Team name to filter by
        parquet_file: Source parquet file path
        output_file: Output parquet file path

    Returns:
        Dictionary with result information
    """
    try:
        # Initialize analyzer
        analyzer = DuckDBAnalyzer(parquet_file)

        # Create a query that filters for matches involving the team
        query = f"""
        SELECT *
        FROM input_data
        WHERE
            home_team LIKE '%{team}%' OR
            away_team LIKE '%{team}%'
        ORDER BY date
        """

        # Execute the query
        result = analyzer.execute_query(query)

        if not result["success"]:
            return {"error": result["error"]}

        # If no matches found, return an error
        if result["row_count"] == 0:
            return {"error": f"No matches found for team '{team}'"}

        # Save the filtered dataset to a new parquet file
        save_query = f"""
        COPY (
            SELECT *
            FROM input_data
            WHERE
                home_team LIKE '%{team}%' OR
                away_team LIKE '%{team}%'
            ORDER BY date
        ) TO '{output_file}' (FORMAT 'parquet')
        """

        analyzer.conn.execute(save_query)

        return {
            "success": True,
            "row_count": result["row_count"],
            "team": team,
            "output_file": output_file
        }
    except Exception as e:
        error_message = str(e)
        tb_str = traceback.format_exc()
        console.print(f"[red]Error building dataset: {error_message}[/red]")
        console.print(f"[red]{tb_str}[/red]")
        return {
            "success": False,
            "error": error_message
        }