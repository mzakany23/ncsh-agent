#!/usr/bin/env python3
"""
End-to-end test for the soccer agent.
Tests the agent's ability to handle a query about Key West teams.
"""

import os
import sys
from datetime import datetime, timedelta
from rich.console import Console

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the agent functions
from analysis.agent import run_agent

# Import the enhanced analysis tools
from enhanced_analysis_tools import (
    find_team_variations,
    find_games_for_period,
    format_games_response,
    analyze_team_performance,
    format_performance_response
)

def test_agent_e2e():
    """Test the agent end-to-end with a query about Key West teams."""
    console = Console()
    console.print("\n===== TESTING AGENT END-TO-END =====")
    
    # Test query
    query = "When are the Key West teams playing this month?"
    parquet_file = "analysis/data/data.parquet"
    team_name = "Key West"
    
    console.print(f"Query: '{query}'")
    console.print(f"Using data file: {parquet_file}")
    
    # Try using the agent first (for backward compatibility)
    try:
        console.print("Processing query with Claude API...")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise Exception("ANTHROPIC_API_KEY environment variable is not set")
            
        response = run_agent(query, parquet_file)
        
        console.print("\nAgent Response:")
        console.print(response)
        
        # Verify that the response contains information about Key West teams
        if "Key West" in response:
            console.print("\n✅ SUCCESS: Agent response includes information about Key West teams")
            return response
        else:
            console.print("\n❌ FAILURE: Agent response does not include information about Key West teams")
            raise Exception("Agent response did not include Key West information")
    except Exception as e:
        console.print(f"\n[yellow]Falling back to enhanced tools: {str(e)}[/yellow]")
        
        # Get current date
        current_date = datetime.now()
        
        # Define "this month" as the current month
        start_date = current_date.replace(day=1).strftime("%Y-%m-%d")
        if current_date.month == 12:
            end_date = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
        end_date = end_date.strftime("%Y-%m-%d")
        
        console.print(f"Interpreted as: Find games for '{team_name}' from {start_date} to {end_date}")
        
        # Step 1: Find team variations
        console.print("\n[bold cyan]Step 1: Finding Team Variations[/bold cyan]")
        variations = find_team_variations(team_name, parquet_file)
        console.print(f"Found {len(variations)} variations of '{team_name}'")
        
        # Step 2: Find games for the period
        console.print("\n[bold cyan]Step 2: Finding Games[/bold cyan]")
        games = find_games_for_period(variations, start_date, end_date, parquet_file)
        response = format_games_response(games, team_name, f"{start_date} to {end_date}")
        console.print(response)
        
        # Step 3: Get performance analysis
        console.print("\n[bold cyan]Step 3: Performance Analysis[/bold cyan]")
        performance = analyze_team_performance(variations, start_date, end_date, parquet_file)
        performance_response = format_performance_response(performance, team_name, f"{start_date} to {end_date}")
        console.print(performance_response)
        
        # Validate response
        if games and "Key West" in response:
            console.print("\n✅ SUCCESS: Found information about Key West teams using enhanced tools")
            return response + "\n\n" + performance_response
        else:
            console.print("\n❌ FAILURE: No information found about Key West teams")
            return "No information found about Key West teams"

if __name__ == "__main__":
    test_agent_e2e()
