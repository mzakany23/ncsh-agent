"""
NC Soccer Hudson - Analytics Dashboard

This dashboard provides visualizations and statistics for soccer match data,
allowing users to filter by date range and team to explore performance metrics.
"""

import os
import sys
import dash
from dash import dcc, html, dash_table, callback_context
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import duckdb
from datetime import datetime, timedelta, date
import numpy as np

# Add parent directory to path to find modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get the path to the parquet file from environment variables
PARQUET_FILE = os.environ.get('PARQUET_FILE', 'analysis/data/data.parquet')

# Initialize the DuckDB connection and load data
conn = duckdb.connect(database=':memory:')
conn.execute(f"CREATE OR REPLACE TABLE soccer_data AS SELECT * FROM '{PARQUET_FILE}'")

# Get all teams for the dropdown
teams_query = """
SELECT DISTINCT home_team AS team FROM soccer_data
UNION
SELECT DISTINCT away_team AS team FROM soccer_data
ORDER BY team
"""
teams_df = conn.execute(teams_query).fetchdf()
teams = teams_df['team'].tolist()

# Add Key West (Combined) option at the beginning of the list
teams.insert(0, "Key West (Combined)")

# Get date range for the date picker
date_range_query = """
SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM soccer_data
"""
date_range_df = conn.execute(date_range_query).fetchdf()
min_date = date_range_df['min_date'][0].strftime('%Y-%m-%d')
max_date = date_range_df['max_date'][0].strftime('%Y-%m-%d')

# Function to get date range presets
def get_date_range_options():
    today = date.today()

    # Get all available years from the dataset
    years_query = """
    SELECT DISTINCT EXTRACT(YEAR FROM date) AS year
    FROM soccer_data
    ORDER BY year DESC
    """
    years_df = conn.execute(years_query).fetchdf()
    years = years_df['year'].tolist()

    # Create date range options
    options = [
        {"label": "Last 30 Days", "value": "last_30_days"},
        {"label": "Last 90 Days", "value": "last_90_days"},
        {"label": "This Year", "value": "this_year"},
        {"label": "Last Year", "value": "last_year"},
        {"label": "All Time", "value": "all_time"},
    ]

    # Add year options
    for year in years:
        options.append({"label": f"Year {int(year)}", "value": f"year_{int(year)}"})

    return options

# Custom CSS for the app
custom_css = '''
:root {
    /* Primary Color Palette */
    --primary: #6F42C1;         /* Main brand purple */
    --primary-light: #9A7AD1;   /* Lighter purple for hover states */
    --primary-dark: #5A32A3;    /* Darker purple for active states */

    /* Secondary Colors */
    --secondary: #5B6AFE;       /* Complementary blue for accents */
    --accent: #00C2CB;          /* Teal accent for highlights */

    /* Neutral Colors */
    --neutral-dark: #343A40;    /* Dark gray for text */
    --neutral-medium: #6C757D;  /* Medium gray for secondary text */
    --neutral-light: #E9ECEF;   /* Light gray for backgrounds */
    --white: #FFFFFF;           /* White for cards and contrast */

    /* Semantic Colors */
    --success: #28A745;         /* Green for positive metrics */
    --warning: #5B6AFE;         /* Blue for neutral metrics */
    --danger: #DC3545;          /* Red for negative metrics */

    /* UI Colors */
    --card-bg: var(--white);
    --body-bg: #F8F9FA;
    --border-color: #DEE2E6;
    --shadow-color: rgba(0, 0, 0, 0.05);
}

body {
    font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background-color: var(--body-bg);
    color: var(--neutral-dark);
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-weight: 600;
    color: var(--primary);
}

p {
    color: var(--neutral-dark);
    line-height: 1.5;
}

.text-muted {
    color: var(--neutral-medium) !important;
}

/* Card Styles */
.card {
    border-radius: 8px;
    box-shadow: 0 4px 8px var(--shadow-color);
    border: none;
    margin-bottom: 20px;
    background-color: var(--card-bg);
    overflow: hidden;
}

.card-header {
    background-color: var(--primary);
    color: var(--white);
    border-bottom: none;
    font-weight: 500;
    padding: 12px 15px;
}

.card-header h4 {
    color: var(--white);
    margin: 0;
}

.card-body {
    padding: 20px;
}

/* Summary Cards */
.summary-card {
    text-align: center;
}

.summary-card .card-header {
    background-color: var(--secondary);
}

.summary-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: var(--primary);
    margin: 10px 0;
}

/* Section headers */
.section-header {
    color: var(--secondary);
    font-weight: 600;
    margin-top: 30px;
    margin-bottom: 15px;
    padding-bottom: 5px;
    border-bottom: 2px solid var(--secondary);
}

/* Table Styles */
.dash-table-container {
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 4px var(--shadow-color);
}

.dash-header {
    background-color: var(--secondary) !important;
    color: var(--white) !important;
    font-weight: 600 !important;
}

/* Results styling */
.result-win {
    background-color: rgba(40, 167, 69, 0.1) !important;
    border-left: 3px solid var(--success) !important;
}

.result-draw {
    background-color: rgba(91, 106, 254, 0.1) !important;
    border-left: 3px solid var(--warning) !important;
}

.result-loss {
    background-color: rgba(220, 53, 69, 0.1) !important;
    border-left: 3px solid var(--danger) !important;
}

/* Filter panel styling */
.filter-panel {
    background-color: var(--card-bg);
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 4px 8px var(--shadow-color);
}

/* Dropdown styling */
.Select-control {
    border-radius: 6px !important;
    border: 1px solid var(--border-color) !important;
}

.Select-control:hover {
    border-color: var(--primary-light) !important;
}

.is-focused:not(.is-open) > .Select-control {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 0.2rem rgba(111, 66, 193, 0.25) !important;
}

.Select-menu-outer {
    border-radius: 0 0 6px 6px !important;
    border: 1px solid var(--border-color) !important;
    box-shadow: 0 2px 4px var(--shadow-color) !important;
}

/* Date picker styling */
.DateInput_input {
    border-radius: 4px !important;
    font-size: 0.9rem !important;
    color: var(--neutral-dark) !important;
}

.DateRangePickerInput {
    border-radius: 6px !important;
    border: 1px solid var(--border-color) !important;
}

.CalendarDay__selected,
.CalendarDay__selected:hover {
    background: var(--primary) !important;
    border: 1px double var(--primary) !important;
}

.CalendarDay__selected_span {
    background: var(--primary-light) !important;
    border: 1px double var(--primary-light) !important;
    color: var(--white) !important;
}

/* Responsive Design */
@media (max-width: 768px) {
    .summary-card {
        margin-bottom: 15px;
    }

    .section-header {
        margin-top: 20px;
        margin-bottom: 10px;
    }

    .summary-value {
        font-size: 1.8rem;
    }
}
'''

# Initialize the Dash app with Bootstrap
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.FONT_AWESOME
    ]
)
server = app.server  # Needed for gunicorn deployment

# Add the custom CSS to the app's assets
if not os.path.exists(os.path.join(os.path.dirname(__file__), 'assets')):
    os.makedirs(os.path.join(os.path.dirname(__file__), 'assets'))

with open(os.path.join(os.path.dirname(__file__), 'assets', 'custom.css'), 'w') as f:
    f.write(custom_css)

# Define the app layout with a standard two-column design
app.layout = dbc.Container([
    # Top Header Row
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("NC Soccer Analytics Dashboard", className="text-center my-4"),
                html.Hr()
            ], className="p-3", style={'background-color': 'white', 'border-radius': '8px', 'box-shadow': '0 2px 4px rgba(0,0,0,0.05)'})
        ], width=12)
    ], className="mb-4"),

    # Main content in two columns
    dbc.Row([
        # Left sidebar with filters
        dbc.Col([
            html.Div([
                html.H4("Filters", className="mb-4", style={'color': '#5B6AFE'}),

                html.Label("Team:", className="fw-bold mb-2"),
                dcc.Dropdown(
                    id='team-dropdown',
                    options=[{'label': team, 'value': team} for team in teams],
                    value='Key West (Combined)',  # Default to Key West (Combined)
                    searchable=True,
                    className="mb-4"
                ),

                html.Label("Quick Date Selection:", className="fw-bold mb-2"),
                dcc.Dropdown(
                    id='date-preset-dropdown',
                    options=get_date_range_options(),
                    value='this_year',
                    clearable=False,
                    className="mb-4"
                ),

                html.Label("Custom Date Range:", className="fw-bold mb-2"),
                dcc.DatePickerRange(
                    id='date-range',
                    min_date_allowed=min_date,
                    max_date_allowed=max_date,
                    start_date=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
                    end_date=datetime.now().strftime('%Y-%m-%d'),
                    display_format='YYYY-MM-DD',
                    className="mb-4"
                ),

                html.Hr(className="my-4"),

                html.Div([
                    html.P([
                        html.I(className="fas fa-info-circle me-2"),
                        "Select filters above to analyze team performance data."
                    ], className="small text-muted mb-0")
                ])
            ], className="filter-panel")
        ], lg=3, md=4, sm=12, className="mb-4"),

        # Right main content area
        dbc.Col([
            # Introduction and context
            dbc.Card([
                dbc.CardHeader(html.H4("About This Dashboard", className="m-0")),
                dbc.CardBody([
                    html.P([
                        "This dashboard provides an analysis of soccer match data for the selected team and time period. ",
                        "Use the filters to select a specific team and date range to explore their performance."
                    ]),
                    html.P([
                        "The Key West (Combined) option shows aggregate statistics for all Key West teams, while individual team ",
                        "selections allow you to focus on specific squads."
                    ])
                ])
            ], className="mb-4"),

            # Summary statistics cards in a row at the top of the story
            html.H4("Performance Summary", className="section-header"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Games Played"),
                        dbc.CardBody([
                            html.Div(html.H3(id="games-played", children="0", className="summary-value")),
                            html.Div("Total matches", className="text-muted small")
                        ])
                    ], className="summary-card")
                ], lg=3, md=6, sm=12),

                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Win Rate"),
                        dbc.CardBody([
                            html.Div(html.H3(id="win-rate", children="0%", className="summary-value")),
                            html.Div("Percentage of wins", className="text-muted small")
                        ])
                    ], className="summary-card")
                ], lg=3, md=6, sm=12),

                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Goals Scored"),
                        dbc.CardBody([
                            html.Div(html.H3(id="goals-scored", children="0", className="summary-value")),
                            html.Div("Total goals scored", className="text-muted small")
                        ])
                    ], className="summary-card")
                ], lg=3, md=6, sm=12),

                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Goal Difference"),
                        dbc.CardBody([
                            html.Div(html.H3(id="goal-difference", children="0", className="summary-value")),
                            html.Div("Goals scored - conceded", className="text-muted small")
                        ])
                    ], className="summary-card")
                ], lg=3, md=6, sm=12)
            ], className="mb-4"),

            # Performance trend chart
            html.H4("Performance Over Time", className="section-header"),
            dbc.Card([
                dbc.CardBody([
                    html.P("This chart shows the cumulative wins, draws, and losses over the selected time period."),
                    dcc.Graph(id="performance-trend")
                ])
            ], className="mb-4"),

            # Goal statistics - with bar chart
            html.H4("Goal Analysis", className="section-header"),
            dbc.Card([
                dbc.CardBody([
                    html.P("Breakdown of goals scored, conceded, and the resulting goal difference."),
                    dcc.Graph(id="goal-stats-chart")
                ])
            ], className="mb-4"),

            # Detailed match results
            html.H4("Match Details", className="section-header"),
            dbc.Card([
                dbc.CardBody([
                    html.P("Complete record of individual matches during the selected period."),
                    dash_table.DataTable(
                        id='match-results-table',
                        columns=[
                            {"name": "Date", "id": "date"},
                            {"name": "Home Team", "id": "home_team"},
                            {"name": "Away Team", "id": "away_team"},
                            {"name": "Score", "id": "score"},
                            {"name": "Result", "id": "result"}
                        ],
                        page_size=10,
                        style_table={'overflowX': 'auto'},
                        style_cell={
                            'textAlign': 'left',
                            'padding': '10px',
                            'fontFamily': 'Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif',
                            'color': '#343A40'
                        },
                        style_header={
                            'backgroundColor': '#5B6AFE',
                            'color': 'white',
                            'fontWeight': 'bold',
                            'textAlign': 'left',
                            'border': 'none'
                        },
                        style_data={
                            'border': 'none',
                            'borderBottom': '1px solid #DEE2E6'
                        },
                        style_data_conditional=[
                            {
                                'if': {'filter_query': '{result} contains "Win"'},
                                'backgroundColor': 'rgba(40, 167, 69, 0.1)',
                                'borderLeft': '3px solid #28A745'
                            },
                            {
                                'if': {'filter_query': '{result} contains "Draw"'},
                                'backgroundColor': 'rgba(91, 106, 254, 0.1)',
                                'borderLeft': '3px solid #5B6AFE'
                            },
                            {
                                'if': {'filter_query': '{result} contains "Loss"'},
                                'backgroundColor': 'rgba(220, 53, 69, 0.1)',
                                'borderLeft': '3px solid #DC3545'
                            },
                            {
                                'if': {'column_id': 'result', 'filter_query': '{result} contains "Win"'},
                                'color': '#28A745',
                                'fontWeight': 'bold'
                            },
                            {
                                'if': {'column_id': 'result', 'filter_query': '{result} contains "Draw"'},
                                'color': '#5B6AFE',
                                'fontWeight': 'bold'
                            },
                            {
                                'if': {'column_id': 'result', 'filter_query': '{result} contains "Loss"'},
                                'color': '#DC3545',
                                'fontWeight': 'bold'
                            }
                        ]
                    )
                ])
            ], className="mb-4"),

            # Footer
            dbc.Row([
                dbc.Col([
                    html.Hr(),
                    html.Div([
                        html.Span("NC Soccer Hudson Analytics Dashboard", className="text-muted me-2"),
                        html.Span("•", className="text-muted mx-2"),
                        html.Span("Designed with ", className="text-muted"),
                        html.I(className="fas fa-heart text-danger mx-1"),
                        html.Span(" by NC Soccer Team", className="text-muted")
                    ], className="text-center py-3")
                ], width=12)
            ], className="mt-4")
        ], lg=9, md=8, sm=12)
    ]),

    # Hidden div for storing initial load state
    html.Div(id='initial-load', style={'display': 'none'})
], fluid=True)

# Callback to update all components based on filters automatically
@app.callback(
    [
        Output('games-played', 'children'),
        Output('win-rate', 'children'),
        Output('goals-scored', 'children'),
        Output('goal-difference', 'children'),
        Output('performance-trend', 'figure'),
        Output('match-results-table', 'data'),
        Output('goal-stats-chart', 'figure')
    ],
    [
        Input('team-dropdown', 'value'),
        Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('initial-load', 'children')
    ]
)
def update_dashboard(team, start_date, end_date, initial_load):
    # Use default date range if not provided
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not team:
        team = 'Key West (Combined)'

    # Common filter conditions
    filter_conditions = f"date >= '{start_date}' AND date <= '{end_date}'"

    # Handle Key West (Combined) option - use LIKE for all Key West teams
    if team == 'Key West (Combined)':
        team_filter = "(home_team LIKE '%Key West%' OR home_team LIKE '%Keywest%' OR away_team LIKE '%Key West%' OR away_team LIKE '%Keywest%')"

        # Query to get team match data (both home and away) for all Key West teams
        matches_query = f"""
        SELECT date, home_team, away_team, home_score, away_score,
               CASE
                   WHEN home_team LIKE '%Key West%' OR home_team LIKE '%Keywest%' THEN home_score
                   WHEN away_team LIKE '%Key West%' OR away_team LIKE '%Keywest%' THEN away_score
                   ELSE 0
               END AS team_score,
               CASE
                   WHEN home_team LIKE '%Key West%' OR home_team LIKE '%Keywest%' THEN away_score
                   WHEN away_team LIKE '%Key West%' OR away_team LIKE '%Keywest%' THEN home_score
                   ELSE 0
               END AS opponent_score,
               CASE
                   WHEN (home_team LIKE '%Key West%' OR home_team LIKE '%Keywest%') AND home_score > away_score THEN 'Win'
                   WHEN (away_team LIKE '%Key West%' OR away_team LIKE '%Keywest%') AND away_score > home_score THEN 'Win'
                   WHEN home_score = away_score THEN 'Draw'
                   ELSE 'Loss'
               END AS result
        FROM soccer_data
        WHERE ({filter_conditions}) AND {team_filter}
        ORDER BY date
        """
    else:
        # Query to get team match data (both home and away) for a single team
        matches_query = f"""
        SELECT date, home_team, away_team, home_score, away_score,
               CASE
                   WHEN home_team = '{team}' THEN home_score
                   WHEN away_team = '{team}' THEN away_score
                   ELSE 0
               END AS team_score,
               CASE
                   WHEN home_team = '{team}' THEN away_score
                   WHEN away_team = '{team}' THEN home_score
                   ELSE 0
               END AS opponent_score,
               CASE
                   WHEN home_team = '{team}' AND home_score > away_score THEN 'Win'
                   WHEN away_team = '{team}' AND away_score > home_score THEN 'Win'
                   WHEN home_score = away_score THEN 'Draw'
                   ELSE 'Loss'
               END AS result
        FROM soccer_data
        WHERE ({filter_conditions}) AND (home_team = '{team}' OR away_team = '{team}')
        ORDER BY date
        """

    matches_df = conn.execute(matches_query).fetchdf()

    # Calculate summary statistics
    games_played = len(matches_df)
    wins = len(matches_df[matches_df['result'] == 'Win'])
    win_rate = f"{round(wins / games_played * 100, 1)}%" if games_played > 0 else "0%"

    goals_scored = matches_df['team_score'].sum()
    goals_conceded = matches_df['opponent_score'].sum()
    goal_diff = goals_scored - goals_conceded

    # Prepare data for the match results table
    table_data = []
    for _, row in matches_df.iterrows():
        table_data.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'home_team': row['home_team'],
            'away_team': row['away_team'],
            'score': f"{row['home_score']} - {row['away_score']}",
            'result': row['result']
        })

    # Create performance trend chart
    matches_df['cumulative_wins'] = (matches_df['result'] == 'Win').cumsum()
    matches_df['cumulative_draws'] = (matches_df['result'] == 'Draw').cumsum()
    matches_df['cumulative_losses'] = (matches_df['result'] == 'Loss').cumsum()
    matches_df['match_number'] = range(1, len(matches_df) + 1)

    performance_fig = go.Figure()
    if not matches_df.empty:
        # Add traces with improved styling
        performance_fig.add_trace(go.Scatter(
            x=matches_df['date'],
            y=matches_df['cumulative_wins'],
            mode='lines+markers',
            name='Wins',
            line=dict(color='#28a745', width=3),
            marker=dict(size=8, symbol='circle', line=dict(width=2, color='white')),
            hovertemplate='Date: %{x}<br>Wins: %{y}<extra></extra>'
        ))
        performance_fig.add_trace(go.Scatter(
            x=matches_df['date'],
            y=matches_df['cumulative_draws'],
            mode='lines+markers',
            name='Draws',
            line=dict(color='#5B6AFE', width=3),
            marker=dict(size=8, symbol='circle', line=dict(width=2, color='white')),
            hovertemplate='Date: %{x}<br>Draws: %{y}<extra></extra>'
        ))
        performance_fig.add_trace(go.Scatter(
            x=matches_df['date'],
            y=matches_df['cumulative_losses'],
            mode='lines+markers',
            name='Losses',
            line=dict(color='#dc3545', width=3),
            marker=dict(size=8, symbol='circle', line=dict(width=2, color='white')),
            hovertemplate='Date: %{x}<br>Losses: %{y}<extra></extra>'
        ))

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

    # Create goal statistics chart with unified styling
    goal_stats = pd.DataFrame([
        {'Metric': 'Goals Scored', 'Value': goals_scored},
        {'Metric': 'Goals Conceded', 'Value': goals_conceded},
        {'Metric': 'Goal Difference', 'Value': goal_diff}
    ])

    # Define custom colors that match our CSS palette
    colors = ['#28A745', '#DC3545', '#5B6AFE']

    # Create a more visually appealing bar chart
    goal_fig = go.Figure()

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

    goal_fig.update_layout(
        title={
            'text': f'{display_team} Goal Statistics',
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

    return (
        games_played,
        win_rate,
        goals_scored,
        goal_diff,
        performance_fig,
        table_data,
        goal_fig
    )

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
        start_date = min_date
        end_date = max_date
    elif preset.startswith('year_'):
        year = int(preset.split('_')[1])
        start_date = date(year, 1, 1).strftime('%Y-%m-%d')
        end_date = date(year, 12, 31).strftime('%Y-%m-%d')
    else:
        # Default to current year
        start_date = date(today.year, 1, 1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    return start_date, end_date

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)