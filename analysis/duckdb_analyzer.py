"""
DuckDB Analysis Module

This module provides comprehensive capabilities for DuckDB queries and analysis,
including database interaction, query execution, schema extraction, SQL validation,
result visualization, and statistical analysis functions.
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
    Analyzer class for DuckDB query results with comprehensive capabilities
    for data querying, validation, visualization and statistical analysis.
    """
    
    def __init__(self, parquet_file: str):
        """
        Initialize the analyzer with a parquet file.
        
        Args:
            parquet_file: Path to the parquet file to analyze
        """
        self.parquet_file = parquet_file
        self.conn = duckdb.connect(database=':memory:')
        
        # Check if file exists
        if not os.path.exists(parquet_file):
            raise FileNotFoundError(f"Parquet file {parquet_file} does not exist")
            
        self._register_data()
        
    def _register_data(self):
        """Register the parquet file as a view in DuckDB."""
        try:
            self.conn.execute(f"CREATE OR REPLACE VIEW input_data AS SELECT * FROM '{self.parquet_file}'")
        except Exception as e:
            raise ValueError(f"Error registering parquet file: {str(e)}")
    
    def get_schema(self) -> Tuple[List[Dict[str, str]], str]:
        """
        Get the schema information for the parquet file.
        
        Returns:
            Tuple containing:
            - List of dictionaries with column_name and data_type
            - JSON string representation of the schema
        """
        try:
            result = self.conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='input_data'"
            ).fetchall()
            
            schema_info = []
            for col_name, data_type in result:
                schema_info.append({"column_name": col_name, "data_type": data_type})
                
            # Return both the list and JSON string
            schema_json = json.dumps(schema_info)
            return schema_info, schema_json
        except Exception as e:
            console.log(f"[get_schema] Error: {str(e)}")
            console.log(traceback.format_exc())
            raise ValueError(f"Error getting schema: {str(e)}")
    
    def execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SQL query against the DuckDB database.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Dictionary with results, column names, and row count
        """
        try:
            if not query:
                raise ValueError("No SQL query provided")
                
            result = self.conn.execute(query).fetchall()
            column_names = [desc[0] for desc in self.conn.description]
            
            # Format the results as a list of dictionaries
            formatted_results = []
            for row in result:
                formatted_row = {}
                for i, col_name in enumerate(column_names):
                    formatted_row[col_name] = row[i]
                formatted_results.append(formatted_row)
            
            return {
                "result": json.dumps(formatted_results, default=str),
                "column_names": column_names,
                "row_count": len(result)
            }
        except Exception as e:
            console.log(f"[execute_query] Error: {str(e)}")
            console.log(traceback.format_exc())
            return {"error": str(e)}
    
    def validate_query(self, query: str) -> Dict[str, Any]:
        """
        Validate a SQL query without executing it.
        
        Args:
            query: SQL query to validate
            
        Returns:
            Dictionary with validation result or error message
        """
        try:
            if not query:
                return {"error": "No SQL query provided"}
                
            # DuckDB will parse the query without executing it
            self.conn.execute(f"PREPARE v1 AS {query}")
            return {"result": "SQL query is valid."}
        except Exception as e:
            return {"error": f"SQL validation error: {str(e)}"}
    
    def translate_query_to_sql(self, question: str, schema_info: Optional[str] = None) -> Dict[str, Any]:
        """
        This method doesn't actually translate the query - that logic happens in the LLM.
        It's a placeholder for query translation and acts as an interface for tooling.
        
        Args:
            question: The natural language question
            schema_info: Schema information in JSON format (optional)
            
        Returns:
            Dictionary indicating the query is ready for translation
        """
        try:
            if not question:
                return {"error": "No question provided"}
                
            if not schema_info and self.parquet_file:
                # If no schema provided, get it from the current file
                _, schema_info = self.get_schema()
                
            return {"result": "Query ready for translation to SQL"}
        except Exception as e:
            return {"error": str(e)}
    
    def generate_chart(self, query: str, chart_type: str = 'bar', 
                      x_column: Optional[str] = None, y_column: Optional[str] = None,
                      title: Optional[str] = None) -> str:
        """
        Generate a chart from query results.
        
        Args:
            query: SQL query to execute
            chart_type: Type of chart ('bar', 'line', 'scatter', 'pie')
            x_column: Column to use for x-axis
            y_column: Column to use for y-axis
            title: Chart title
            
        Returns:
            Base64-encoded PNG image of the chart
        """
        try:
            # Execute query and convert to DataFrame
            result = self.conn.execute(query).df()
            
            if result.empty:
                raise ValueError("Query returned no results")
            
            # If columns not specified, try to infer
            if not x_column and not y_column and len(result.columns) >= 2:
                x_column = result.columns[0]
                y_column = result.columns[1]
            elif not x_column and len(result.columns) >= 1:
                x_column = result.columns[0]
            elif not y_column and len(result.columns) >= 2:
                y_column = result.columns[1]
                
            if not x_column or not y_column:
                raise ValueError("Cannot determine chart columns automatically")
                
            # Create matplotlib figure
            plt.figure(figsize=(10, 6))
            
            if chart_type == 'bar':
                result.plot(kind='bar', x=x_column, y=y_column)
            elif chart_type == 'line':
                result.plot(kind='line', x=x_column, y=y_column)
            elif chart_type == 'scatter':
                result.plot(kind='scatter', x=x_column, y=y_column)
            elif chart_type == 'pie' and y_column:
                result.plot(kind='pie', y=y_column)
            else:
                raise ValueError(f"Unsupported chart type: {chart_type}")
                
            if title:
                plt.title(title)
                
            plt.tight_layout()
            
            # Convert plot to base64 string
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            plt.close()
            
            return image_base64
        except Exception as e:
            raise ValueError(f"Chart generation error: {str(e)}")
    
    def get_summary_statistics(self, column_name: str) -> Dict[str, Any]:
        """
        Calculate summary statistics for a specified column.
        
        Args:
            column_name: Name of the column to analyze
            
        Returns:
            Dictionary with summary statistics
        """
        try:
            query = f"""
            SELECT 
                MIN("{column_name}") as min_value,
                MAX("{column_name}") as max_value,
                AVG("{column_name}") as mean_value,
                MEDIAN("{column_name}") as median_value,
                STDDEV("{column_name}") as std_dev
            FROM input_data
            """
            
            result = self.conn.execute(query).fetchone()
            
            return {
                "min": result[0],
                "max": result[1],
                "mean": result[2],
                "median": result[3], 
                "std_dev": result[4]
            }
        except Exception as e:
            raise ValueError(f"Error calculating summary statistics: {str(e)}")
            
# Module-level functions that wrap the class methods for easy tool integration

def execute_sql(reasoning: str, query: str, parquet_file: str) -> Dict:
    """
    Execute SQL queries against DuckDB database.
    
    Args:
        reasoning: Explanation of why this SQL query is appropriate
        query: The SQL query to execute
        parquet_file: Path to the parquet file
        
    Returns:
        Dictionary with query results or error message
    """
    try:
        console.log(f"[execute_sql] reasoning: {reasoning}, query: {query}, parquet_file: {parquet_file}")
        analyzer = DuckDBAnalyzer(parquet_file)
        return analyzer.execute_query(query)
    except Exception as e:
        console.log(f"[execute_sql] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}

def get_schema(reasoning: str, parquet_file: str) -> Dict:
    """
    Get schema information from a parquet file.
    
    Args:
        reasoning: Explanation of why the schema information is needed
        parquet_file: Path to the parquet file
        
    Returns:
        Dictionary with schema information or error message
    """
    try:
        console.log(f"[get_schema] reasoning: {reasoning}, parquet_file: {parquet_file}")
        analyzer = DuckDBAnalyzer(parquet_file)
        schema_info, schema_json = analyzer.get_schema()
        return {"result": schema_json}
    except Exception as e:
        console.log(f"[get_schema] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}

def validate_sql(reasoning: str, query: str) -> Dict:
    """
    Validate SQL queries without executing them.
    
    Args:
        reasoning: Explanation of why validation is needed
        query: The SQL query to validate
        
    Returns:
        Dictionary with validation result or error message
    """
    try:
        console.log(f"[validate_sql] reasoning: {reasoning}, query: {query}")
        
        # Create a temporary connection for validation only
        conn = duckdb.connect(database=':memory:')
        
        try:
            # DuckDB will parse the query without executing it
            conn.execute(f"PREPARE v1 AS {query}")
            return {"result": "SQL query is valid."}
        except Exception as e:
            return {"error": f"SQL validation error: {str(e)}"}
    except Exception as e:
        console.log(f"[validate_sql] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}

def query_to_sql(reasoning: str, question: str, schema_info: str) -> Dict:
    """
    Interface for translating natural language queries to SQL.
    The actual translation happens in the LLM.
    
    Args:
        reasoning: Detailed reasoning for the SQL translation
        question: The natural language question
        schema_info: Schema information to inform the translation
        
    Returns:
        Dictionary with the SQL translation or error message
    """
    try:
        console.log(f"[query_to_sql] reasoning: {reasoning}, question: {question}")
        return {"result": reasoning}
    except Exception as e:
        console.log(f"[query_to_sql] Error: {str(e)}")
        console.log(traceback.format_exc())
        return {"error": str(e)}
    
    def get_unique_values(self, column_name: str, limit: int = 100) -> List[Any]:
        """
        Get unique values for a specified column.
        
        Args:
            column_name: Name of the column to analyze
            limit: Maximum number of unique values to return
            
        Returns:
            List of unique values
        """
        try:
            query = f"""
            SELECT DISTINCT "{column_name}" 
            FROM input_data 
            ORDER BY "{column_name}"
            LIMIT {limit}
            """
            
            result = self.conn.execute(query).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            raise ValueError(f"Error retrieving unique values: {str(e)}")
