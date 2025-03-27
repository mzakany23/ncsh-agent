"""
Main dashboard callback for the NC Soccer Analytics Dashboard.
"""

from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objects as go
from ..utils.query_builder import build_team_matches_query

def register_dashboard_callbacks(app, conn):
    """Register the main dashboard callback."""

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
            Input('date-range', 'start_date'),
            Input('date-range', 'end_date'),
            Input('initial-load', 'children'),
            Input('opponent-filter-type', 'value'),
            Input('opponent-selection', 'value'),
            Input('competitiveness-threshold', 'value')
        ]
    )
    def update_dashboard(team, start_date, end_date, initial_load, opponent_filter_type, opponent_selection, competitiveness_threshold):
        """Update all dashboard components based on filters."""
        # Get matches data
        query = build_team_matches_query(team, start_date, end_date)
        matches_df = conn.execute(query).fetchdf()

        # Apply opponent filtering
        filtered_matches_df = filter_opponents(matches_df, opponent_filter_type, opponent_selection, competitiveness_threshold)

        # Calculate statistics
        stats = calculate_statistics(filtered_matches_df)

        # Create visualizations
        figures = create_visualizations(filtered_matches_df, team)

        # Prepare match results table data
        table_data = prepare_table_data(filtered_matches_df)

        return (
            stats['games_played'],
            stats['win_rate'],
            stats['loss_rate'],
            str(stats['goals_scored']),
            str(stats['goals_conceded']),
            str(stats['goal_diff']),
            figures['performance_trend'],
            table_data,
            figures['goal_stats'],
            figures['results_pie'],
            stats['opponent_analysis_text'],
            figures['opponent_comparison'],
            figures['opponent_win_rate'],
            figures['opponent_goal_diff'],
            {'display': 'block' if len(filtered_matches_df) > 0 else 'none'}
        )

def filter_opponents(df, filter_type, opponent_selection, threshold):
    """Filter matches based on opponent selection."""
    if df.empty:
        return df

    if filter_type == 'specific' and opponent_selection and len(opponent_selection) > 0:
        df['normalized_opponent'] = df['opponent_team'].str.lower().str.replace('[^a-z0-9]', '', regex=True)
        normalized_selection = [op.lower().replace(' ', '').replace('-', '').replace('_', '') for op in opponent_selection]
        mask = df['normalized_opponent'].apply(lambda x: any(norm_op in x or x in norm_op for norm_op in normalized_selection))
        df = df[mask]
    elif filter_type == 'worthy':
        df = filter_worthy_opponents(df, threshold)

    if 'normalized_opponent' in df.columns:
        df = df.drop(columns=['normalized_opponent'])

    return df

def filter_worthy_opponents(df, threshold):
    """Filter for worthy opponents based on competitiveness."""
    if df.empty:
        return df

    opponent_groups = df.groupby('opponent_team')
    worthy_opponents = []

    # First pass - find opponents with wins
    for opponent, group in opponent_groups:
        if len(group[group['result'] == 'Loss']) > 0:
            worthy_opponents.append(opponent)

    # Second pass - evaluate other opponents
    for opponent, group in opponent_groups:
        if opponent in worthy_opponents:
            continue

        if len(group) >= 1:
            loss_rate = len(group[group['result'] == 'Loss']) / len(group)
            group['goal_diff'] = abs(group['team_score'] - group['opponent_score'])
            avg_goal_diff = group['goal_diff'].mean()

            loss_factor = loss_rate * 100
            margin_factor = max(0, 100 - min(avg_goal_diff * 20, 100))
            competitiveness_score = (loss_factor * 0.7) + (margin_factor * 0.3)

            if competitiveness_score >= threshold:
                worthy_opponents.append(opponent)

    return df[df['opponent_team'].isin(worthy_opponents)] if worthy_opponents else pd.DataFrame(columns=df.columns)

def calculate_statistics(df):
    """Calculate summary statistics from match data."""
    games_played = len(df)

    if games_played > 0:
        wins = len(df[df['result'] == 'Win'])
        losses = len(df[df['result'] == 'Loss'])
        win_rate = f"{(wins / games_played) * 100:.1f}%"
        loss_rate = f"{(losses / games_played) * 100:.1f}%"
        goals_scored = df['team_score'].sum()
        goals_conceded = df['opponent_score'].sum()
        goal_diff = goals_scored - goals_conceded
    else:
        win_rate = "0.0%"
        loss_rate = "0.0%"
        goals_scored = 0
        goals_conceded = 0
        goal_diff = 0

    return {
        'games_played': games_played,
        'win_rate': win_rate,
        'loss_rate': loss_rate,
        'goals_scored': goals_scored,
        'goals_conceded': goals_conceded,
        'goal_diff': goal_diff,
        'opponent_analysis_text': f"Analysis of {len(df['opponent_team'].unique())} opponents"
    }

def create_visualizations(df, team):
    """Create all dashboard visualizations."""
    return {
        'performance_trend': create_performance_trend(df, team),
        'goal_stats': create_goal_stats_chart(df),
        'results_pie': create_results_pie_chart(df),
        'opponent_comparison': create_opponent_comparison(df),
        'opponent_win_rate': create_opponent_win_rate(df),
        'opponent_goal_diff': create_opponent_goal_diff(df)
    }

def prepare_table_data(df):
    """Prepare data for the match results table."""
    table_data = []
    for _, row in df.iterrows():
        table_data.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'home_team': row['home_team'],
            'away_team': row['away_team'],
            'score': f"{row['home_score']} - {row['away_score']}",
            'result': row['result']
        })
    return table_data

def create_performance_trend(df, team):
    """Create the performance trend chart."""
    fig = go.Figure()

    if not df.empty:
        sorted_df = df.sort_values(by='date', ascending=True)
        sorted_df['cumulative_wins'] = (sorted_df['result'] == 'Win').cumsum()
        sorted_df['cumulative_draws'] = (sorted_df['result'] == 'Draw').cumsum()
        sorted_df['cumulative_losses'] = (sorted_df['result'] == 'Loss').cumsum()

        for result, color in [('wins', '#28a745'), ('draws', '#5B6AFE'), ('losses', '#dc3545')]:
            fig.add_trace(go.Scatter(
                x=sorted_df['date'],
                y=sorted_df[f'cumulative_{result}'],
                mode='lines+markers',
                name=result.capitalize(),
                line=dict(color=color, width=3),
                marker=dict(size=8, symbol='circle', line=dict(width=2, color='white')),
                hovertemplate=f'Date: %{{x}}<br>{result.capitalize()}: %{{y}}<extra></extra>'
            ))

    fig.update_layout(
        title=f'{team} Performance Over Time',
        xaxis_title='Date',
        yaxis_title='Cumulative Count',
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='closest',
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )

    return fig

def create_goal_stats_chart(df):
    """Create the goal statistics chart."""
    if df.empty:
        return go.Figure()

    goals_scored = df['team_score'].sum()
    goals_conceded = df['opponent_score'].sum()
    goal_diff = goals_scored - goals_conceded

    fig = go.Figure(data=[
        go.Bar(
            x=['Goals Scored', 'Goals Conceded', 'Goal Difference'],
            y=[goals_scored, goals_conceded, goal_diff],
            marker_color=['#28A745', '#DC3545', '#5B6AFE']
        )
    ])

    fig.update_layout(
        title='Goal Statistics',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    return fig

def create_results_pie_chart(df):
    """Create the results distribution pie chart."""
    if df.empty:
        return go.Figure()

    results = df['result'].value_counts()

    fig = go.Figure(data=[go.Pie(
        labels=['Wins', 'Draws', 'Losses'],
        values=[
            results.get('Win', 0),
            results.get('Draw', 0),
            results.get('Loss', 0)
        ],
        marker=dict(colors=['#28A745', '#5B6AFE', '#DC3545'])
    )])

    fig.update_layout(
        title='Match Result Distribution',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    return fig

def create_opponent_comparison(df):
    """Create the opponent comparison chart."""
    if df.empty:
        return go.Figure()

    opponent_stats = df.groupby('opponent_team').agg({
        'result': lambda x: (x == 'Win').mean() * 100,
        'team_score': 'sum',
        'opponent_score': 'sum'
    }).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=opponent_stats['opponent_team'],
        y=opponent_stats['result'],
        name='Win Rate %',
        marker_color='#28A745'
    ))

    fig.update_layout(
        title='Performance Against Opponents',
        xaxis_title='Opponent',
        yaxis_title='Win Rate %',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    return fig

def create_opponent_win_rate(df):
    """Create the opponent win rate chart."""
    if df.empty:
        return go.Figure()

    opponent_stats = df.groupby('opponent_team')['result'].value_counts().unstack(fill_value=0)

    fig = go.Figure(data=[
        go.Bar(
            name=result,
            x=opponent_stats.index,
            y=opponent_stats[result],
            marker_color={'Win': '#28A745', 'Draw': '#5B6AFE', 'Loss': '#DC3545'}[result]
        ) for result in ['Win', 'Draw', 'Loss'] if result in opponent_stats.columns
    ])

    fig.update_layout(
        title='Win/Loss Distribution by Opponent',
        barmode='stack',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    return fig

def create_opponent_goal_diff(df):
    """Create the opponent goal difference chart."""
    if df.empty:
        return go.Figure()

    opponent_stats = df.groupby('opponent_team').agg({
        'team_score': 'sum',
        'opponent_score': 'sum'
    }).reset_index()

    fig = go.Figure(data=[
        go.Bar(
            name='Goals For',
            x=opponent_stats['opponent_team'],
            y=opponent_stats['team_score'],
            marker_color='#28A745'
        ),
        go.Bar(
            name='Goals Against',
            x=opponent_stats['opponent_team'],
            y=opponent_stats['opponent_score'],
            marker_color='#DC3545'
        )
    ])

    fig.update_layout(
        title='Goal Performance by Opponent',
        barmode='group',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    return fig