from dash import callback_context
from dash.dependencies import Input, Output, State
from datetime import datetime, timedelta, date
import plotly.graph_objects as go
import pandas as pd
import sqlite3
from src.db import get_db_connection, get_team_groups, create_team_group, update_team_group, delete_team_group
from src.queries import (
    get_key_west_team_filter,
    get_debug_key_west_query,
    get_combined_matches_query,
    get_team_matches_query,
    get_team_group_filter,
    get_team_group_matches_query,
    get_opponent_query_for_key_west,
    get_opponent_query_for_team,
    get_opponent_query_for_team_group
)
from src.util import (
    normalize_team_names_in_dataframe,
    filter_matches_by_opponents,
    identify_worthy_opponents
)


def init_callbacks(app, teams, team_groups_param, conn):
    # Make team_groups properly accessible as a global variable within all callbacks
    global team_groups
    # Store the initial team_groups from the parameter to the global variable
    team_groups = team_groups_param

    @app.callback(
        [
            Output('games-played', 'children'),
            Output('win-rate', 'children'),
            Output('loss-rate-display', 'children'),
            Output('goals-scored', 'children'),
            Output('goals-conceded-display', 'children'),
            Output('goal-difference', 'children'),
            Output('performance-trend', 'figure'),
            Output('match-results-table', 'data'),
            Output('goal-stats-chart', 'figure'),
            Output('goal-stats-pie', 'figure'),
            Output('opponent-analysis-text', 'children'),
            Output('opponent-comparison-chart', 'figure'),
            Output('opponent-win-rate-chart', 'figure'),
            Output('opponent-goal-diff-chart', 'figure'),
            Output('opponent-analysis-section', 'style')
        ],
        [
            Input('team-dropdown', 'value'),
            Input('team-group-dropdown', 'value'),
            Input('team-selection-type', 'value'),
            Input('date-range', 'start_date'),
            Input('date-range', 'end_date'),
            Input('initial-load', 'children'),
            Input('opponent-filter-type', 'value'),
            Input('opponent-selection', 'value'),
            Input('opponent-team-groups', 'value'),
            Input('competitiveness-threshold', 'value')
        ]
    )
    def update_dashboard(team, team_group, selection_type, start_date, end_date, initial_load,
                         opponent_filter_type, opponent_selection, opponent_team_groups, competitiveness_threshold):
        # Set default values for inputs
        start_date = start_date or (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        end_date = end_date or datetime.now().strftime('%Y-%m-%d')

        # Handle different selection types
        if selection_type == 'individual':
            display_name = team
        else:  # 'group'
            team_group = team_group or (next(iter(team_groups.keys())) if team_groups else None)
            display_name = f"Group: {team_group}" if team_group else "No group selected"

        # Create date filter condition for SQL queries
        filter_conditions = f"date >= '{start_date}' AND date <= '{end_date}'"
        print(f"Debug: Date range selected: {start_date} to {end_date}")
        print(f"Debug: Selection type: {selection_type}, Team: {team}, Team Group: {team_group}")
        print(f"Debug: Opponent filter: {opponent_filter_type}, Opponents: {opponent_selection}, Opponent Groups: {opponent_team_groups}")

        # Run debug queries to check data
        run_debug_queries(conn, filter_conditions)

        # Get match data based on selection type
        if selection_type == 'individual':
            matches_df = get_team_match_data(conn, team, filter_conditions)
        else:  # 'group'
            matches_df = get_team_group_match_data(conn, team_group, filter_conditions)

        # Apply opponent filtering
        filtered_matches_df, display_opponent_analysis = filter_matches_by_filter_type(
            matches_df,
            opponent_filter_type,
            opponent_selection,
            opponent_team_groups,
            competitiveness_threshold
        )

        # Calculate dashboard metrics
        dashboard_metrics = calculate_dashboard_metrics(filtered_matches_df)

        # Generate visualizations - use display_name for proper titles
        visualizations = generate_visualizations(filtered_matches_df, display_name, dashboard_metrics)

        # Generate opponent analysis
        opponent_analysis = generate_opponent_analysis(
            filtered_matches_df,
            opponent_filter_type,
            opponent_selection,
            opponent_team_groups,
            competitiveness_threshold
        )

        # Combine results and return
        return (
            dashboard_metrics['games_played'],
            dashboard_metrics['win_rate_value'],
            dashboard_metrics['loss_rate_value'],
            str(dashboard_metrics['goals_scored']),
            str(dashboard_metrics['goals_conceded']),
            str(dashboard_metrics['goal_diff']),
            visualizations['performance_fig'],
            dashboard_metrics['table_data'],
            visualizations['goal_fig'],
            visualizations['pie_fig'],
            opponent_analysis['analysis_text'],
            opponent_analysis['comparison_chart'],
            opponent_analysis['win_rate_chart'],
            opponent_analysis['goal_diff_chart'],
            display_opponent_analysis
        )

    def run_debug_queries(conn, filter_conditions):
        """Run debug queries to check data quality and availability."""
        # Debug query for 2025 games
        debug_2025_query = """
        SELECT date, home_team, away_team, home_score, away_score
        FROM soccer_data
        WHERE EXTRACT(YEAR FROM date) = 2025
        ORDER BY date
        """
        debug_2025_df = conn.execute(debug_2025_query).fetchdf()
        print(f"Debug: Found {len(debug_2025_df)} games in 2025 before filtering")
        for _, row in debug_2025_df.iterrows():
            print(f"Debug: 2025 Game - {row['date']} - {row['home_team']} vs {row['away_team']}")

        # Debug query for team name variations
        debug_team_names_query = """
        SELECT DISTINCT home_team FROM soccer_data WHERE LOWER(home_team) LIKE '%k%w%' OR LOWER(home_team) LIKE '%key%'
        UNION
        SELECT DISTINCT away_team FROM soccer_data WHERE LOWER(away_team) LIKE '%k%w%' OR LOWER(away_team) LIKE '%key%'
        """
        debug_team_names_df = conn.execute(debug_team_names_query).fetchdf()
        print(f"Debug: Possible Key West team name variations:")
        for _, row in debug_team_names_df.iterrows():
            team_name = row[0]
            print(f"Debug: Possible team name: {team_name}")

    def get_team_match_data(conn, team, filter_conditions):
        """Get match data for the selected team."""
        matches_query = get_team_matches_query(team, filter_conditions)
        return conn.execute(matches_query).fetchdf()

    def get_team_group_match_data(conn, group_name, filter_conditions):
        """Get match data for the selected team group."""
        if not group_name or group_name not in team_groups:
            print(f"Debug: Team group '{group_name}' not found or empty")
            return pd.DataFrame()  # Return an empty DataFrame

        # Get the teams in the group
        teams = team_groups.get(group_name, [])
        if not teams:
            print(f"Debug: Team group '{group_name}' has no teams")
            return pd.DataFrame()  # Return an empty DataFrame

        print(f"Debug: Getting matches for team group '{group_name}' with {len(teams)} teams: {teams}")

        # Generate and execute the query
        matches_query = get_team_group_matches_query(teams, filter_conditions)

        # Debug - log the query
        print(f"Debug: Team group query first 200 chars: {matches_query[:200]}...")

        return conn.execute(matches_query).fetchdf()

    def filter_matches_by_filter_type(matches_df, filter_type, opponent_selection, opponent_team_groups, competitiveness_threshold):
        """
        Filter matches based on the selected filter type.

        Args:
            matches_df: DataFrame containing match data
            filter_type: Type of filter to apply ('specific', 'worthy', 'team_groups' or 'all')
            opponent_selection: List of selected opponent teams
            opponent_team_groups: List of selected opponent team groups
            competitiveness_threshold: Threshold for worthy opponents

        Returns:
            Tuple of (filtered_matches_df, display_opponent_analysis)
        """
        filtered_matches_df = matches_df.copy()
        display_opponent_analysis = {'display': 'block'}

        if filter_type == 'specific' and opponent_selection and len(opponent_selection) > 0:
            # Filter to include only matches against specific opponents
            if not filtered_matches_df.empty:
                filtered_matches_df = normalize_team_names_in_dataframe(filtered_matches_df)
                filtered_matches_df = filter_matches_by_opponents(filtered_matches_df, opponent_selection)
                print(f"Debug: Selected specific opponents: {opponent_selection}, found {len(filtered_matches_df)} matches")

        elif filter_type == 'team_groups' and opponent_team_groups and len(opponent_team_groups) > 0:
            # Filter to include only matches against opponents in selected team groups
            if not filtered_matches_df.empty:
                # Get all teams from the selected team groups
                all_opponent_teams = []
                for group_name in opponent_team_groups:
                    if group_name in team_groups:
                        group_teams = team_groups.get(group_name, [])
                        all_opponent_teams.extend(group_teams)

                # Remove duplicates
                all_opponent_teams = list(set(all_opponent_teams))

                if all_opponent_teams:
                    filtered_matches_df = normalize_team_names_in_dataframe(filtered_matches_df)
                    filtered_matches_df = filter_matches_by_opponents(filtered_matches_df, all_opponent_teams)
                    print(f"Debug: Filtering by {len(all_opponent_teams)} teams from {len(opponent_team_groups)} team groups")
                    print(f"Debug: Found {len(filtered_matches_df)} matches against teams in selected groups")
                else:
                    # If no teams in the selected groups, return empty DataFrame
                    filtered_matches_df = pd.DataFrame(columns=filtered_matches_df.columns)
                    print(f"Debug: No teams found in the selected team groups")

        elif filter_type == 'worthy':
            if opponent_selection and len(opponent_selection) > 0:
                # Filter to include only matches against specific worthy opponents
                if not filtered_matches_df.empty:
                    filtered_matches_df = normalize_team_names_in_dataframe(filtered_matches_df)
                    filtered_matches_df = filter_matches_by_opponents(filtered_matches_df, opponent_selection)
                    print(f"Debug: Selected worthy opponents: {opponent_selection}, found {len(filtered_matches_df)} matches")
            else:
                # Automatically identify worthy opponents
                if not filtered_matches_df.empty:
                    worthy_opponents = identify_worthy_opponents(filtered_matches_df, competitiveness_threshold)

                    if worthy_opponents:
                        filtered_matches_df = normalize_team_names_in_dataframe(filtered_matches_df)
                        filtered_matches_df = filter_matches_by_opponents(filtered_matches_df, worthy_opponents)
                        print(f"Debug: Dashboard - Found {len(worthy_opponents)} worthy opponents: {worthy_opponents}")
                    else:
                        # If no worthy opponents found, keep the filtered dataframe empty
                        filtered_matches_df = pd.DataFrame(columns=filtered_matches_df.columns)
                        print(f"Debug: Dashboard - No worthy opponents found with threshold {competitiveness_threshold}")

        # Remove the normalized_opponent column if it exists before further processing
        if 'normalized_opponent' in filtered_matches_df.columns:
            filtered_matches_df = filtered_matches_df.drop(columns=['normalized_opponent'])

        # Only hide opponent analysis if truly no data after filtering
        if len(filtered_matches_df) == 0:
            display_opponent_analysis = {'display': 'none'}

        return filtered_matches_df, display_opponent_analysis

    def calculate_dashboard_metrics(filtered_matches_df):
        """
        Calculate dashboard metrics from the filtered matches data.

        Args:
            filtered_matches_df: DataFrame containing filtered match data

        Returns:
            Dictionary of calculated metrics
        """
        games_played = len(filtered_matches_df)

        if games_played > 0:
            wins = len(filtered_matches_df[filtered_matches_df['result'] == 'Win'])
            losses = len(filtered_matches_df[filtered_matches_df['result'] == 'Loss'])
            win_rate = (wins / games_played) * 100
            loss_rate = (losses / games_played) * 100

            # Format metrics with proper formatting
            win_rate_value = f"{win_rate:.1f}%"
            loss_rate_value = f"{loss_rate:.1f}%"

            goals_scored = filtered_matches_df['team_score'].sum()
            goals_conceded = filtered_matches_df['opponent_score'].sum()
            goal_diff = goals_scored - goals_conceded
        else:
            # If no games after filtering, set default values
            win_rate_value = "0.0%"
            loss_rate_value = "0.0%"
            goals_scored = 0
            goals_conceded = 0
            goal_diff = 0

        # Prepare data for the match results table from the filtered dataset
        table_data = []
        for _, row in filtered_matches_df.iterrows():
            table_data.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'home_team': row['home_team'],
                'away_team': row['away_team'],
                'score': f"{row['home_score']} - {row['away_score']}",
                'result': row['result'],
                'opponent': row['opponent_team']
            })

        return {
            'games_played': games_played,
            'win_rate_value': win_rate_value,
            'loss_rate_value': loss_rate_value,
            'goals_scored': goals_scored,
            'goals_conceded': goals_conceded,
            'goal_diff': goal_diff,
            'table_data': table_data
        }

    def generate_visualizations(filtered_matches_df, team, dashboard_metrics):
        """
        Generate visualizations for the dashboard.

        Args:
            filtered_matches_df: DataFrame containing filtered match data
            team: Selected team name
            dashboard_metrics: Dictionary of calculated metrics

        Returns:
            Dictionary of visualization figures
        """
        # Sort data by date (newest first)
        if not filtered_matches_df.empty:
            sorted_df = filtered_matches_df.sort_values(by='date', ascending=True)  # Sort in chronological order for charts
        else:
            sorted_df = pd.DataFrame(columns=filtered_matches_df.columns)  # Empty DataFrame with same columns

        # Create performance trend chart
        performance_fig = create_performance_trend_chart(sorted_df, team)

        # Create goal statistics chart
        goal_fig = create_goal_stats_chart(filtered_matches_df,
                                          dashboard_metrics['goals_scored'],
                                          dashboard_metrics['goals_conceded'],
                                          dashboard_metrics['goal_diff'])

        # Create goal statistics pie chart
        pie_fig = create_result_distribution_pie_chart(filtered_matches_df)

        return {
            'performance_fig': performance_fig,
            'goal_fig': goal_fig,
            'pie_fig': pie_fig
        }

    def create_performance_trend_chart(sorted_df, team):
        """Create a performance trend chart showing cumulative wins, draws, and losses."""
        performance_fig = go.Figure()

        if not sorted_df.empty:
            sorted_df['cumulative_wins'] = (sorted_df['result'] == 'Win').cumsum()
            sorted_df['cumulative_draws'] = (sorted_df['result'] == 'Draw').cumsum()
            sorted_df['cumulative_losses'] = (sorted_df['result'] == 'Loss').cumsum()
            sorted_df['match_number'] = range(1, len(sorted_df) + 1)

            # Add traces with improved styling
            performance_fig.add_trace(go.Scatter(
                x=sorted_df['date'],
                y=sorted_df['cumulative_wins'],
                mode='lines+markers',
                name='Wins',
                line=dict(color='#28a745', width=3),
                marker=dict(size=8, symbol='circle', line=dict(width=2, color='white')),
                hovertemplate='Date: %{x}<br>Wins: %{y}<extra></extra>'
            ))
            performance_fig.add_trace(go.Scatter(
                x=sorted_df['date'],
                y=sorted_df['cumulative_draws'],
                mode='lines+markers',
                name='Draws',
                line=dict(color='#5B6AFE', width=3),
                marker=dict(size=8, symbol='circle', line=dict(width=2, color='white')),
                hovertemplate='Date: %{x}<br>Draws: %{y}<extra></extra>'
            ))
            performance_fig.add_trace(go.Scatter(
                x=sorted_df['date'],
                y=sorted_df['cumulative_losses'],
                mode='lines+markers',
                name='Losses',
                line=dict(color='#dc3545', width=3),
                marker=dict(size=8, symbol='circle', line=dict(width=2, color='white')),
                hovertemplate='Date: %{x}<br>Losses: %{y}<extra></extra>'
            ))
        else:
            # Create empty chart with message
            performance_fig.add_annotation(
                text="No matches found with the current filters",
                showarrow=False,
                font=dict(size=14, color="#6F42C1"),
                xref="paper", yref="paper",
                x=0.5, y=0.5
            )

        display_team = 'Key West (Combined)' if team == 'Key West (Combined)' else team

        # Apply improved chart styling with unified colors
        performance_fig.update_layout(
            title={
                'text': f'{display_team} Performance Over Time',
                'font': {'size': 20, 'color': '#6F42C1', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            xaxis_title={
                'text': 'Date',
                'font': {'size': 14, 'color': '#343A40', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            yaxis_title={
                'text': 'Cumulative Count',
                'font': {'size': 14, 'color': '#343A40', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            legend={
                'orientation': 'h',
                'yanchor': 'bottom',
                'y': 1.02,
                'xanchor': 'right',
                'x': 1,
                'font': {'size': 12, 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'},
                'bgcolor': 'rgba(255, 255, 255, 0.8)',
                'bordercolor': '#DEE2E6',
                'borderwidth': 1
            },
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='closest',
            margin=dict(l=60, r=30, t=80, b=60),
            xaxis=dict(
                showgrid=True,
                gridcolor='#E9ECEF',
                showline=True,
                linecolor='#DEE2E6',
                tickfont=dict(family='Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif', size=12, color='#343A40')
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='#E9ECEF',
                showline=True,
                linecolor='#DEE2E6',
                tickfont=dict(family='Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif', size=12, color='#343A40')
            )
        )

        return performance_fig

    def create_goal_stats_chart(filtered_matches_df, goals_scored, goals_conceded, goal_diff):
        """Create a goal statistics chart."""
        goal_stats = pd.DataFrame([
            {'Metric': 'Goals Scored', 'Value': goals_scored},
            {'Metric': 'Goals Conceded', 'Value': goals_conceded},
            {'Metric': 'Goal Difference', 'Value': goal_diff}
        ])

        # Define custom colors that match our CSS palette
        colors = ['#28A745', '#DC3545', '#5B6AFE']

        # Create a more visually appealing bar chart
        goal_fig = go.Figure()

        if not filtered_matches_df.empty:
            for i, row in goal_stats.iterrows():
                goal_fig.add_trace(go.Bar(
                    x=[row['Metric']],
                    y=[row['Value']],
                    name=row['Metric'],
                    marker_color=colors[i],
                    text=[row['Value']],
                    textposition='auto',
                    textfont={'color': 'white' if i != 2 or row['Value'] < 0 else '#343A40'},
                    hovertemplate='%{x}: %{y}<extra></extra>'
                ))
        else:
            # Create empty chart with message
            goal_fig.add_annotation(
                text="No matches found with the current filters",
                showarrow=False,
                font=dict(size=14, color="#6F42C1"),
                xref="paper", yref="paper",
                x=0.5, y=0.5
            )

        # Apply chart layout
        goal_fig.update_layout(
            title={
                'text': f'Goal Statistics',
                'font': {'size': 20, 'color': '#6F42C1', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            xaxis_title={
                'text': 'Metric',
                'font': {'size': 14, 'color': '#343A40', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            yaxis_title={
                'text': 'Count',
                'font': {'size': 14, 'color': '#343A40', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            legend_title_text='',
            showlegend=False,
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=60, r=30, t=80, b=60),
            xaxis=dict(
                showgrid=False,
                showline=True,
                linecolor='#DEE2E6',
                tickfont=dict(family='Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif', size=14, color='#343A40')
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='#E9ECEF',
                showline=True,
                linecolor='#DEE2E6',
                tickfont=dict(family='Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif', size=12, color='#343A40'),
                zerolinecolor='#DEE2E6'
            ),
            bargap=0.3
        )

        return goal_fig

    def create_result_distribution_pie_chart(filtered_matches_df):
        """Create a pie chart showing the distribution of match results."""
        pie_fig = go.Figure()

        if not filtered_matches_df.empty:
            results_count = filtered_matches_df['result'].value_counts()

            # Create a better visualization with results distribution
            pie_fig.add_trace(go.Pie(
                labels=['Wins', 'Draws', 'Losses'],
                values=[
                    results_count.get('Win', 0),
                    results_count.get('Draw', 0),
                    results_count.get('Loss', 0)
                ],
                hole=0.4,
                marker=dict(colors=['#28A745', '#5B6AFE', '#DC3545']),
                textinfo='label+percent',
                textfont=dict(family='Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif', size=14),
                hoverinfo='label+value',
                pull=[0.05, 0, 0]
            ))
        else:
            # Create empty chart with message
            pie_fig.add_annotation(
                text="No matches found with the current filters",
                showarrow=False,
                font=dict(size=14, color="#6F42C1"),
                xref="paper", yref="paper",
                x=0.5, y=0.5
            )

        # Apply chart layout
        pie_fig.update_layout(
            title={
                'text': f'Match Result Distribution',
                'font': {'size': 20, 'color': '#6F42C1', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=-0.2,
                xanchor='center',
                x=0.5,
                font=dict(family='Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif', size=12)
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=10, r=10, t=80, b=40)
        )

        return pie_fig

    def generate_opponent_analysis(filtered_matches_df, opponent_filter_type, opponent_selection, opponent_team_groups, competitiveness_threshold):
        """
        Generate opponent analysis visualizations and text.

        Args:
            filtered_matches_df: DataFrame containing filtered match data
            opponent_filter_type: Type of opponent filter applied
            opponent_selection: List of selected opponents
            opponent_team_groups: List of selected opponent team groups
            competitiveness_threshold: Threshold for worthy opponents

        Returns:
            Dictionary of opponent analysis components
        """
        # Set default empty visualization objects
        opponent_comparison_chart = go.Figure()
        opponent_win_rate_chart = go.Figure()
        opponent_goal_diff_chart = go.Figure()

        # Generate appropriate analysis text based on filter type
        if opponent_filter_type == 'all':
            opponent_analysis_text = f"Analysis of all {len(filtered_matches_df['opponent_team'].unique())} opponents"
        elif opponent_filter_type == 'worthy' and opponent_selection:
            opponent_analysis_text = f"Analysis of selected worthy adversaries: {', '.join(opponent_selection)}"
        elif opponent_filter_type == 'worthy':
            opponent_analysis_text = f"Analysis of worthy adversaries (competitiveness ≥ {competitiveness_threshold}%)"
        elif opponent_filter_type == 'specific' and opponent_selection:
            opponent_analysis_text = f"Analysis of selected opponent(s): {', '.join(opponent_selection)}"
        elif opponent_filter_type == 'team_groups' and opponent_team_groups:
            group_names = ", ".join(opponent_team_groups)
            opponent_analysis_text = f"Analysis of opponents in team group(s): {group_names}"
        else:
            opponent_analysis_text = "No opponent filter selected"

        # Generate opponent charts if we have data
        if len(filtered_matches_df) > 0:
            # Create opponent comparison charts using the filtered data
            opponent_stats_df = generate_opponent_stats_dataframe(filtered_matches_df)

            if not opponent_stats_df.empty:
                opponent_comparison_chart = create_opponent_comparison_chart(opponent_stats_df)
                opponent_win_rate_chart = create_opponent_win_rate_chart(opponent_stats_df)
                opponent_goal_diff_chart = create_opponent_goal_diff_chart(opponent_stats_df)
        else:
            # Empty figures with appropriate messages
            for chart in [opponent_comparison_chart, opponent_win_rate_chart, opponent_goal_diff_chart]:
                chart.update_layout(
                    title="No match data available",
                    xaxis=dict(showticklabels=False),
                    yaxis=dict(showticklabels=False)
                )

        return {
            'analysis_text': opponent_analysis_text,
            'comparison_chart': opponent_comparison_chart,
            'win_rate_chart': opponent_win_rate_chart,
            'goal_diff_chart': opponent_goal_diff_chart
        }

    def generate_opponent_stats_dataframe(filtered_matches_df):
        """Generate a DataFrame with opponent statistics."""
        # Group data by opponent
        opponent_groups = filtered_matches_df.groupby('opponent_team')

        # Collect opponent stats
        opponent_stats_list = []

        for opponent, group in opponent_groups:
            total_matches = len(group)
            total_wins = len(group[group['result'] == 'Win'])
            total_losses = len(group[group['result'] == 'Loss'])
            total_draws = len(group[group['result'] == 'Draw'])

            win_rate_opp = total_wins / total_matches if total_matches > 0 else 0
            loss_rate_opp = total_losses / total_matches if total_matches > 0 else 0
            draw_rate_opp = total_draws / total_matches if total_matches > 0 else 0

            total_goals_for = group['team_score'].sum()
            total_goals_against = group['opponent_score'].sum()
            goal_difference = total_goals_for - total_goals_against

            opponent_stats_list.append({
                'opponent': opponent,
                'total_matches': total_matches,
                'wins': total_wins,
                'losses': total_losses,
                'draws': total_draws,
                'win_rate': win_rate_opp,
                'loss_rate': loss_rate_opp,
                'draw_rate': draw_rate_opp,
                'goals_for': total_goals_for,
                'goals_against': total_goals_against,
                'goal_difference': goal_difference
            })

        # Create DataFrame from stats
        return pd.DataFrame(opponent_stats_list)

    def create_opponent_comparison_chart(opponent_stats_df):
        """Create a comparison chart of win rate vs. matches played by opponent."""
        # Sort by win rate for the comparison chart
        opponent_stats_df = opponent_stats_df.sort_values('win_rate', ascending=False)

        opponent_comparison_chart = go.Figure()

        opponent_comparison_chart.add_trace(go.Bar(
            x=opponent_stats_df['opponent'],
            y=opponent_stats_df['win_rate'] * 100,  # Convert to percentage value
            name='Win Rate',
            marker_color='#28A745',
            text=[f"{wr*100:.1f}%" for wr in opponent_stats_df['win_rate']],  # Format as percentage
            textposition='auto',
            hovertemplate='%{x}<br>Win Rate: %{text}<extra></extra>'
        ))

        opponent_comparison_chart.add_trace(go.Bar(
            x=opponent_stats_df['opponent'],
            y=opponent_stats_df['total_matches'],
            name='Matches Played',
            marker_color='#5B6AFE',
            text=opponent_stats_df['total_matches'],
            textposition='auto',
            yaxis='y2',
            hovertemplate='%{x}<br>Matches: %{y}<extra></extra>'
        ))

        opponent_comparison_chart.update_layout(
            title={
                'text': 'Performance Against Opponents',
                'font': {'size': 20, 'color': '#6F42C1', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            xaxis_title={
                'text': 'Opponent',
                'font': {'size': 14, 'color': '#343A40', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            yaxis=dict(
                title={
                    'text': 'Win Rate',
                    'font': {'color': '#28A745'}
                },
                tickformat='.0f',  # Changed from '.0%' to '.0f'
                range=[0, 110],    # Changed from [0, 1.1] to [0, 110]
                side='left',
                tickfont=dict(color='#28A745')
            ),
            yaxis2=dict(
                title={
                    'text': 'Matches Played',
                    'font': {'color': '#5B6AFE'}
                },
                range=[0, max(opponent_stats_df['total_matches']) * 1.2] if len(opponent_stats_df) > 0 else [0, 10],
                side='right',
                overlaying='y',
                tickfont=dict(color='#5B6AFE')
            ),
            barmode='group',
            plot_bgcolor='white',
            paper_bgcolor='white',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5
            ),
            margin=dict(l=60, r=60, t=80, b=60)
        )

        return opponent_comparison_chart

    def create_opponent_win_rate_chart(opponent_stats_df):
        """Create a win/loss breakdown chart for each opponent."""
        opponent_win_rate_chart = go.Figure()

        # Create a separate pie chart for each opponent
        for i, row in opponent_stats_df.iterrows():
            opponent_win_rate_chart.add_trace(go.Pie(
                labels=['Wins', 'Draws', 'Losses'],
                values=[row['wins'], row['draws'], row['losses']],
                name=row['opponent'],
                title=row['opponent'],
                marker_colors=['#28A745', '#5B6AFE', '#DC3545'],
                visible=(i == 0)  # Only show first opponent by default
            ))

        # Add dropdown for opponent selection
        buttons = []
        for i, row in opponent_stats_df.iterrows():
            visibility = [j == i for j in range(len(opponent_stats_df))]
            buttons.append(dict(
                method='update',
                label=row['opponent'],
                args=[{'visible': visibility},
                    {'title': {'text': f'Win/Loss Breakdown vs {row["opponent"]}',
                                'font': {'size': 20, 'color': '#6F42C1'}}}]
            ))

        opponent_win_rate_chart.update_layout(
            title={
                'text': f'Win/Loss Breakdown vs {opponent_stats_df.iloc[0]["opponent"] if len(opponent_stats_df) > 0 else ""}',
                'font': {'size': 20, 'color': '#6F42C1', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            updatemenus=[{
                'buttons': buttons,
                'direction': 'down',
                'showactive': True,
                'x': 0.5,
                'y': 1.15,
                'xanchor': 'center',
                'yanchor': 'top'
            }] if len(opponent_stats_df) > 0 else [],
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=10, r=10, t=120, b=40)
        )

        return opponent_win_rate_chart

    def create_opponent_goal_diff_chart(opponent_stats_df):
        """Create a goal statistics chart by opponent."""
        # Sort by goal difference
        opponent_stats_df = opponent_stats_df.sort_values('goal_difference', ascending=False)

        opponent_goal_diff_chart = go.Figure()

        opponent_goal_diff_chart.add_trace(go.Bar(
            x=opponent_stats_df['opponent'],
            y=opponent_stats_df['goals_for'],
            name='Goals Scored',
            marker_color='#28A745',
            text=opponent_stats_df['goals_for'],
            textposition='auto',
            hovertemplate='%{x}<br>Goals Scored: %{y}<extra></extra>'
        ))

        opponent_goal_diff_chart.add_trace(go.Bar(
            x=opponent_stats_df['opponent'],
            y=opponent_stats_df['goals_against'],
            name='Goals Conceded',
            marker_color='#DC3545',
            text=opponent_stats_df['goals_against'],
            textposition='auto',
            hovertemplate='%{x}<br>Goals Conceded: %{y}<extra></extra>'
        ))

        opponent_goal_diff_chart.update_layout(
            title={
                'text': 'Goal Performance by Opponent',
                'font': {'size': 20, 'color': '#6F42C1', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            xaxis_title={
                'text': 'Opponent',
                'font': {'size': 14, 'color': '#343A40', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            yaxis_title={
                'text': 'Goals',
                'font': {'size': 14, 'color': '#343A40', 'family': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif'}
            },
            barmode='group',
            plot_bgcolor='white',
            paper_bgcolor='white',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5
            ),
            margin=dict(l=60, r=30, t=80, b=60)
        )

        return opponent_goal_diff_chart

    # Callback to ensure data loads on initial page load
    @app.callback(
        Output('initial-load', 'children'),
        [Input('date-preset-dropdown', 'value')]
    )
    def set_initial_load(date_preset):
        # Just return something to trigger the update_dashboard callback
        return 'loaded'

    # Callback to update the date picker based on the preset selection
    @app.callback(
        [Output('date-range', 'start_date'),
        Output('date-range', 'end_date')],
        [Input('date-preset-dropdown', 'value')]
    )
    def update_date_range(preset):
        today = date.today()

        if preset == 'last_30_days':
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
        elif preset == 'last_90_days':
            start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
        elif preset == 'this_year':
            start_date = date(today.year, 1, 1).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
        elif preset == 'last_year':
            start_date = date(today.year - 1, 1, 1).strftime('%Y-%m-%d')
            end_date = date(today.year - 1, 12, 31).strftime('%Y-%m-%d')
        elif preset == 'all_time':
            # Use a very early date and future date to cover all possible data
            start_date = '2000-01-01'
            end_date = '2030-12-31'
        elif preset.startswith('year_'):
            year = int(preset.split('_')[1])
            start_date = date(year, 1, 1).strftime('%Y-%m-%d')
            end_date = date(year, 12, 31).strftime('%Y-%m-%d')
        else:
            # Default to current year
            start_date = date(today.year, 1, 1).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')

        return start_date, end_date

    # Callback to show/hide opponent filter controls
    @app.callback(
        [
            Output('opponent-selection-div', 'style'),
            Output('worthy-adversaries-controls', 'style'),
            Output('team-groups-opponent-div', 'style'),
            Output('opponent-selection-label', 'children'),
            Output('opponent-selection', 'style')
        ],
        [Input('opponent-filter-type', 'value')]
    )
    def toggle_opponent_controls(filter_type):
        if filter_type == 'specific':
            return {'display': 'block'}, {'display': 'none'}, {'display': 'none'}, "Select Opponent(s):", {'display': 'block'}
        elif filter_type == 'worthy':
            return {'display': 'block'}, {'display': 'block'}, {'display': 'none'}, "Select Opponent(s):", {'display': 'block'}
        elif filter_type == 'team_groups':
            return {'display': 'block'}, {'display': 'none'}, {'display': 'block'}, "Select Opponent(s):", {'display': 'none'}
        else:  # 'all' or any other value
            return {'display': 'none'}, {'display': 'none'}, {'display': 'none'}, "Select Opponent(s):", {'display': 'block'}

    # Callback to update opponent dropdown options based on filter type
    @app.callback(
        [Output('opponent-selection', 'options'),
        Output('opponent-selection', 'value')],  # Add this output to control the selection
        [
            Input('opponent-filter-type', 'value'),
            Input('team-dropdown', 'value'),
            Input('team-group-dropdown', 'value'),
            Input('team-selection-type', 'value'),
            Input('date-range', 'start_date'),
            Input('date-range', 'end_date'),
            Input('competitiveness-threshold', 'value')
        ]
    )
    def update_opponent_options(filter_type, team, team_group, selection_type, start_date, end_date, competitiveness_threshold):
        # Default opponents (all teams except selected team/group)
        if selection_type == 'individual':
            all_opponents = [{'label': t, 'value': t} for t in teams if t != team]
        else:  # 'group'
            if not team_group or team_group not in team_groups:
                return [], []  # No group selected or invalid group

            group_teams = team_groups.get(team_group, [])
            all_opponents = [{'label': t, 'value': t} for t in teams if t not in group_teams]

        # If filter type is 'worthy', compute worthy opponents
        if filter_type == 'worthy':
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')

            # Get data for the selected team or team group
            filter_conditions = f"date >= '{start_date}' AND date <= '{end_date}'"

            if selection_type == 'individual':
                opponent_query = get_opponent_query_for_team(team, filter_conditions)
            else:  # 'group'
                if not team_group or team_group not in team_groups:
                    return [], []  # No valid group selected

                group_teams = team_groups.get(team_group, [])
                if not group_teams:
                    return [], []  # Empty group

                opponent_query = get_opponent_query_for_team_group(group_teams, filter_conditions)

            # Execute query and get opponent data
            opponent_df = conn.execute(opponent_query).fetchdf()

            # Calculate competitiveness for each opponent
            worthy_opponents = []
            worthy_opponent_values = []  # To store just the values for selection
            opponents_with_wins = set()  # Track opponents who have defeated us

            # Group by opponent, but normalize names first to handle case variations
            # Add a normalized column for grouping
            if not opponent_df.empty:
                # Create a normalized team name column for grouping
                opponent_df['normalized_opponent'] = opponent_df['opponent'].str.lower().str.replace('[^a-z0-9]', '', regex=True)

                # Group by normalized opponent name
                opponent_groups = opponent_df.groupby('normalized_opponent')

                # Create a mapping of normalized names to original display names
                name_mapping = {}
                for _, row in opponent_df.iterrows():
                    norm_name = row['normalized_opponent']
                    if norm_name not in name_mapping:
                        name_mapping[norm_name] = row['opponent']

                # First identify opponents who have defeated us (these are automatic worthy adversaries)
                for norm_opponent, group in opponent_groups:
                    # Use the original name for display
                    display_name = name_mapping[norm_opponent]

                    # Count games where the opponent won (we lost)
                    opponent_wins = len(group[group['result'] == 'Loss'])
                    if opponent_wins > 0:
                        opponents_with_wins.add(norm_opponent)

                        # Add this opponent to worthy opponents list
                        total_matches = len(group)
                        losses = opponent_wins
                        loss_rate = losses / total_matches

                        # Add to worthy opponents with note that they've defeated us
                        worthy_opponents.append({
                            'label': f"{display_name} ({total_matches} matches, defeated us {opponent_wins} times)",
                            'value': display_name,
                            'competitiveness': 100  # Max competitiveness for teams that defeated us
                        })
                        worthy_opponent_values.append(display_name)
                        print(f"Debug: Auto-including opponent {display_name} who defeated us {opponent_wins} times")

                # Then evaluate other opponents based on competitiveness
                for norm_opponent, group in opponent_groups:
                    # Skip opponents who already defeated us (already added)
                    if norm_opponent in opponents_with_wins:
                        continue

                    if len(group) >= 1:  # Reduced minimum match threshold to 1
                        # Use the original name for display
                        display_name = name_mapping[norm_opponent]

                        # Calculate results against this opponent
                        wins = len(group[group['result'] == 'Win'])
                        losses = len(group[group['result'] == 'Loss'])
                        loss_rate = losses / len(group)

                        # Calculate average goal differential (absolute value)
                        group['goal_diff'] = abs(group['team_score'] - group['opponent_score'])
                        avg_goal_diff = group['goal_diff'].mean()

                        # Competitiveness calculation:
                        loss_factor = loss_rate * 100  # 0-100 based on loss percentage
                        margin_factor = max(0, 100 - min(avg_goal_diff * 20, 100))  # 0-100 based on goal margin
                        competitiveness_score = (loss_factor * 0.7) + (margin_factor * 0.3)

                        print(f"Debug: Evaluating opponent: {display_name}, Score: {competitiveness_score:.2f}, Threshold: {competitiveness_threshold}")

                        # Threshold now works as: higher threshold = more challenging opponents
                        if competitiveness_score >= competitiveness_threshold:
                            total_matches = len(group)
                            worthy_opponents.append({
                                'label': f"{display_name} ({total_matches} matches, {competitiveness_score:.0f}% competitive)",
                                'value': display_name,
                                'competitiveness': competitiveness_score
                            })
                            worthy_opponent_values.append(display_name)

            # Sort by competitiveness (most competitive first)
            worthy_opponents = sorted(worthy_opponents, key=lambda x: x['competitiveness'], reverse=True)

            if worthy_opponents:
                # Return all worthy opponents' options and values
                print(f"Debug: Found {len(worthy_opponents)} worthy opponents")
                return worthy_opponents, worthy_opponent_values
            else:
                return [{'label': 'No worthy opponents found with current threshold', 'value': ''}], []

        # For 'specific' option, return all opponents
        elif filter_type == 'specific':
            return all_opponents, []  # Empty selection for specific filter

        # Default: return empty when 'all' is selected (not needed to select specific opponents)
        return [], []  # Empty options and selection for 'all'

    # Add callback to hide loading spinner after initial load
    @app.callback(
        Output("loading-spinner-container", "style"),
        [Input('initial-load', 'children')]
    )
    def hide_loading_after_initial_load(initial_load):
        # Hide loading spinner container after initial load
        return {"display": "none"}

    # Callback to toggle between individual team and team group selection
    @app.callback(
        [Output('team-dropdown', 'style'),
        Output('team-group-selection-div', 'style')],
        [Input('team-selection-type', 'value')]
    )
    def toggle_team_selection_type(selection_type):
        if selection_type == 'individual':
            return {'display': 'block'}, {'display': 'none'}
        else:  # 'group'
            return {'display': 'none'}, {'display': 'block'}

    @app.callback(
        [Output('edit-teams-for-group', 'value'),
         Output('edit-group-dropdown', 'options'),
         Output('edit-group-name', 'value')],
        [Input('edit-group-dropdown', 'value'),
         Input('group-management-status', 'children')]  # Use this to trigger refresh when team groups change
    )
    def populate_edit_teams(group_name, status_change):
        """Populate the edit teams dropdown with the teams from the selected group."""
        # First update the dropdown options with all available team groups
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Get all team groups for the dropdown with debug info
            cursor.execute("SELECT id, name FROM team_groups ORDER BY name")
            all_groups = cursor.fetchall()
            print(f"Database contains {len(all_groups)} team groups: {all_groups}")

            group_names = [group[1] for group in all_groups]
            group_options = [{'label': name, 'value': name} for name in group_names]
            print(f"Refreshed edit-group-dropdown with {len(group_names)} options: {group_names}")

            # Update the global team_groups dictionary (important for consistency)
            print(f"Updated global team_groups, now contains: {list(team_groups.keys())}")
        except sqlite3.Error as e:
            print(f"Error getting team groups: {str(e)}")
            group_options = []
        finally:
            conn.close()

        # Early return if no group is selected
        if not group_name:
            return [], group_options, ""

        # Query the database directly to get the team members
        print(f"Retrieving team members for group '{group_name}'")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Get the group ID
            cursor.execute("SELECT id FROM team_groups WHERE name = ?", (group_name,))
            group_row = cursor.fetchone()

            if not group_row:
                print(f"Group '{group_name}' not found in database")
                return [], group_options, ""

            group_id = group_row[0]

            # Get all teams in the group
            cursor.execute("SELECT team_name FROM team_group_members WHERE group_id = ? ORDER BY team_name", (group_id,))
            teams = [row[0] for row in cursor.fetchall()]

            print(f"Found {len(teams)} teams for group '{group_name}': {teams}")
            return teams, group_options, group_name
        except sqlite3.Error as e:
            print(f"Error retrieving team members for group '{group_name}': {str(e)}")
            return [], group_options, ""
        finally:
            conn.close()

    # Callback to create a new team group
    @app.callback(
        [Output('group-management-status', 'children'),
        Output('new-group-name', 'value'),
        Output('teams-for-group', 'value'),
        Output('team-group-dropdown', 'options'),
        Output('team-group-dropdown', 'value')],
        [Input('create-group-button', 'n_clicks'),
        Input('update-group-button', 'n_clicks'),
        Input('delete-group-button', 'n_clicks')],
        [State('new-group-name', 'value'),
        State('teams-for-group', 'value'),
        State('edit-group-dropdown', 'value'),
        State('edit-teams-for-group', 'value'),
        State('edit-group-name', 'value'),
        State('team-group-dropdown', 'value')]
    )
    def manage_team_groups(create_clicks, update_clicks, delete_clicks,
                        new_name, new_teams, edit_name, edit_teams, edit_new_name, current_selection):
        """Handle team group management operations."""
        # Declare team_groups as global to access the module-level variable
        global team_groups

        ctx = callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

        print(f"Team group management triggered by: {triggered_id}")
        print(f"Current state - Create clicks: {create_clicks}, Update clicks: {update_clicks}, Delete clicks: {delete_clicks}")
        print(f"Edit name: {edit_name}, New name: {edit_new_name}, Edit teams count: {len(edit_teams) if edit_teams else 0}")
        print(f"Current group selection: {current_selection}")
        print(f"BEFORE OPERATION: Global team_groups contains {len(team_groups)} groups: {list(team_groups.keys())}")

        # Default return values
        status = ""
        new_name_value = ""
        new_teams_value = []
        selected_group = current_selection  # Keep current selection by default

        # We're using the global team_groups variable declared at the init_callbacks level
        # so we don't need to redeclare it here

        if triggered_id == 'create-group-button' and new_name and new_teams:
            # Create a new team group
            if create_team_group(new_name, new_teams):
                status = f"Team group '{new_name}' created successfully!"
                # Refresh team groups after successful creation
                team_groups = get_team_groups()
                print(f"AFTER CREATE: Global team_groups refreshed, now contains {len(team_groups)} groups: {list(team_groups.keys())}")
                selected_group = new_name  # Auto-select newly created group
            else:
                status = f"Failed to create team group '{new_name}'. It may already exist."
                new_name_value = new_name
                new_teams_value = new_teams

        elif triggered_id == 'update-group-button' and edit_name and edit_teams:
            # Update an existing team group
            # Use the new name if it's different from the original
            renamed = edit_new_name and edit_new_name != edit_name
            if update_team_group(edit_name, edit_teams, edit_new_name if renamed else None):
                if renamed:
                    status = f"Team group '{edit_name}' renamed to '{edit_new_name}' and updated successfully!"
                    # If current selection is the updated group, update it with the new name
                    if current_selection == edit_name:
                        selected_group = edit_new_name
                else:
                    status = f"Team group '{edit_name}' updated successfully!"

                # Refresh team groups after successful update
                team_groups = get_team_groups()
                print(f"AFTER UPDATE: Global team_groups refreshed, now contains {len(team_groups)} groups: {list(team_groups.keys())}")
            else:
                status = f"Failed to update team group '{edit_name}'."

        elif triggered_id == 'delete-group-button':
            # Validate the input for deletion
            if not edit_name:
                print("Delete operation failed: No team group selected")
                status = "Delete failed: No team group selected"
            else:
                print(f"Attempting to delete team group: {edit_name}")
                # Delete a team group
                if delete_team_group(edit_name):
                    status = f"Team group '{edit_name}' deleted successfully!"

                    # Force removal from the team_groups dictionary before refreshing
                    if edit_name in team_groups:
                        del team_groups[edit_name]

                    # Refresh team groups after deletion
                    team_groups = get_team_groups()
                    print(f"AFTER DELETE: Global team_groups refreshed, now contains {len(team_groups)} groups: {list(team_groups.keys())}")

                    # Clear the current selection if it was the deleted group
                    if current_selection == edit_name:
                        # Select another group if available, otherwise set to None
                        if team_groups:
                            selected_group = next(iter(team_groups.keys()))
                            print(f"Selected new group: {selected_group}")
                        else:
                            selected_group = None
                            print("No groups available after deletion")
                else:
                    status = f"Failed to delete team group '{edit_name}'."

        # Update dropdown options for team group dropdown
        print(f"Updating team group dropdown with team groups: {list(team_groups.keys())}")

        # Instead of relying only on the global variable, also query the database directly
        # to ensure complete consistency across all dropdowns
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM team_groups ORDER BY name")
            db_group_names = [row[0] for row in cursor.fetchall()]
            print(f"Direct database query shows {len(db_group_names)} groups: {db_group_names}")
            team_group_options = [{'label': group_name, 'value': group_name} for group_name in db_group_names]
        except sqlite3.Error as e:
            print(f"Error querying team groups for dropdown: {str(e)}")
            # Fall back to using the global variable if database query fails
            team_group_options = [{'label': group_name, 'value': group_name} for group_name in team_groups.keys()]
        finally:
            conn.close()

        # Make sure the selected group still exists
        if selected_group and selected_group not in db_group_names:
            if db_group_names:
                selected_group = db_group_names[0]
                print(f"Selected group not found, defaulting to: {selected_group}")
            else:
                selected_group = None
                print("No groups available, setting selection to None")

        print(f"Final selected group: {selected_group}")
        return status, new_name_value, new_teams_value, team_group_options, selected_group

    # Callback to update team group options for the opponent filter
    @app.callback(
        Output('opponent-team-groups', 'options'),
        [Input('group-management-status', 'children'),
         Input('team-group-dropdown', 'value'),
         Input('team-selection-type', 'value')]  # Add inputs for current selection and selection type
    )
    def update_opponent_team_groups(status_change, current_team_group, selection_type):
        """Update the team groups dropdown in the opponent filter section"""
        # Query the database directly for the most up-to-date list
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT name FROM team_groups ORDER BY name")
            all_group_names = [row[0] for row in cursor.fetchall()]

            # Filter out the currently selected team group when in Team Group mode
            if selection_type == 'group' and current_team_group:
                group_names = [name for name in all_group_names if name != current_team_group]
                print(f"Updating opponent team groups dropdown with {len(group_names)} groups (excluded {current_team_group})")
            else:
                group_names = all_group_names
                print(f"Updating opponent team groups dropdown with all {len(group_names)} groups")

            return [{'label': name, 'value': name} for name in group_names]
        except sqlite3.Error as e:
            print(f"Error querying team groups for opponent dropdown: {str(e)}")
            # Fall back to the global variable, but still filter out current selection
            if selection_type == 'group' and current_team_group:
                group_names = [name for name in team_groups.keys() if name != current_team_group]
            else:
                group_names = list(team_groups.keys())
            return [{'label': group_name, 'value': group_name} for group_name in group_names]
        finally:
            conn.close()

    # Callback to reset opponent team groups selection when team selection changes
    @app.callback(
        Output('opponent-team-groups', 'value'),
        [Input('team-group-dropdown', 'value'),
         Input('team-selection-type', 'value')],
        [State('opponent-team-groups', 'value')]
    )
    def reset_opponent_team_groups(current_team_group, selection_type, current_selection):
        """Reset the opponent team groups selection when team selection changes"""
        # Get the callback context to check what triggered this callback
        ctx = callback_context
        if not ctx.triggered:
            # If not triggered by any input, just return the current selection
            return current_selection

        # Get the ID of the input that triggered this callback
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if triggered_id in ['team-group-dropdown', 'team-selection-type']:
            # If the selection type is 'group' and current_team_group is in the current selection,
            # remove it and return the filtered selection
            if selection_type == 'group' and current_team_group and current_selection:
                if isinstance(current_selection, list) and current_team_group in current_selection:
                    new_selection = [group for group in current_selection if group != current_team_group]
                    print(f"Removed {current_team_group} from opponent team groups selection")
                    return new_selection

        # Otherwise, just return the current selection unchanged
        return current_selection
