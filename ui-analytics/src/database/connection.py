"""
Database connection and query utilities for the NC Soccer Analytics Dashboard.
"""

import os
import duckdb

def get_connection():
    """Initialize and return a DuckDB connection."""
    PARQUET_FILE = os.environ.get('PARQUET_FILE', 'analysis/data/data.parquet')
    conn = duckdb.connect(database=':memory:')
    conn.execute(f"CREATE OR REPLACE TABLE soccer_data AS SELECT * FROM '{PARQUET_FILE}'")
    return conn

def get_teams(conn):
    """Get all teams from the database."""
    teams_query = """
    SELECT DISTINCT home_team AS team FROM soccer_data
    UNION
    SELECT DISTINCT away_team AS team FROM soccer_data
    ORDER BY team
    """
    teams_df = conn.execute(teams_query).fetchdf()
    teams = teams_df['team'].tolist()
    teams.insert(0, "Key West (Combined)")  # Add Key West (Combined) option
    return teams

def get_date_range(conn):
    """Get the min and max dates from the database."""
    date_range_query = """
    SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM soccer_data
    """
    date_range_df = conn.execute(date_range_query).fetchdf()
    min_date = date_range_df['min_date'][0].strftime('%Y-%m-%d')
    max_date = date_range_df['max_date'][0].strftime('%Y-%m-%d')
    return min_date, max_date