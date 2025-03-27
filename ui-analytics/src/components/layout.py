"""
Layout components for the NC Soccer Analytics Dashboard.
"""

import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from datetime import datetime, timedelta

def create_header():
    """Create the dashboard header."""
    return dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("Game Dashboard", className="text-center my-3")
            ], className="p-3", style={'background-color': 'white', 'border-radius': '8px', 'box-shadow': '0 2px 4px rgba(0,0,0,0.05)'})
        ], width=12)
    ], className="mb-4")

def create_filters(teams, min_date, max_date, date_range_options):
    """Create the filters panel."""
    return dbc.Col([
        html.Div([
            html.H4("Filters", className="mb-4", style={'color': '#5B6AFE'}),

            html.Label("Team:", className="fw-bold mb-2"),
            dcc.Dropdown(
                id='team-dropdown',
                options=[{'label': team, 'value': team} for team in teams],
                value='Key West (Combined)',
                searchable=True,
                className="mb-4"
            ),

            html.Label("Opponent Filter:", className="fw-bold mb-2"),
            dcc.RadioItems(
                id='opponent-filter-type',
                options=[
                    {'label': 'All Opponents', 'value': 'all'},
                    {'label': 'Specific Opponent(s)', 'value': 'specific'},
                    {'label': 'Worthy Adversaries', 'value': 'worthy'}
                ],
                value='all',
                className="mb-2"
            ),

            html.Div(id="opponent-selection-div", style={'display': 'none'}),
            html.Div(id="worthy-adversaries-controls", style={'display': 'none'}),

            html.Label("Quick Date Selection:", className="fw-bold mb-2"),
            dcc.Dropdown(
                id='date-preset-dropdown',
                options=date_range_options,
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
            )
        ], className="filter-panel")
    ], lg=3, md=4, sm=12, className="mb-4")

def create_summary_cards():
    """Create the summary statistics cards."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Games Played"),
                dbc.CardBody([
                    html.Div(html.H3(id="games-played", children="0", className="summary-value")),
                    html.Div("Total matches", className="text-muted small")
                ])
            ], className="summary-card h-100")
        ], width=2, className="px-1"),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Win Rate"),
                dbc.CardBody([
                    html.Div(html.H3(id="win-rate", children="0.0%", className="summary-value")),
                    html.Div("Percentage of wins", className="text-muted small")
                ])
            ], className="summary-card h-100")
        ], width=2, className="px-1"),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Loss Rate"),
                dbc.CardBody([
                    html.Div(html.H3(id="loss-rate-display", children="0.0%", className="summary-value")),
                    html.Div("Percentage of losses", className="text-muted small")
                ])
            ], className="summary-card h-100")
        ], width=2, className="px-1"),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Goals Scored"),
                dbc.CardBody([
                    html.Div(html.H3(id="goals-scored", children="0", className="summary-value")),
                    html.Div("Total goals for", className="text-muted small")
                ])
            ], className="summary-card h-100")
        ], width=2, className="px-1"),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Goals Conceded"),
                dbc.CardBody([
                    html.Div(html.H3(id="goals-conceded-display", children="0", className="summary-value")),
                    html.Div("Total goals against", className="text-muted small")
                ])
            ], className="summary-card h-100")
        ], width=2, className="px-1"),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Goal Difference"),
                dbc.CardBody([
                    html.Div(html.H3(id="goal-difference", children="0", className="summary-value")),
                    html.Div("Goals scored - conceded", className="text-muted small")
                ])
            ], className="summary-card h-100")
        ], width=2, className="px-1")
    ], className="mb-4 mx-0")

def create_match_results_table():
    """Create the match results table."""
    return dash_table.DataTable(
        id='match-results-table',
        columns=[
            {"name": "Date", "id": "date", "type": "datetime"},
            {"name": "Home Team", "id": "home_team"},
            {"name": "Away Team", "id": "away_team"},
            {"name": "Score", "id": "score"},
            {"name": "Result", "id": "result"}
        ],
        page_size=10,
        sort_action='native',
        sort_mode='single',
        sort_by=[{'column_id': 'date', 'direction': 'desc'}],
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
            }
        ]
    )