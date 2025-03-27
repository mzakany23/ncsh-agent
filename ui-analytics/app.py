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
import sqlite3
import json

# Add parent directory to path to find modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get the path to the parquet file from environment variables
PARQUET_FILE = os.environ.get('PARQUET_FILE', 'analysis/data/data.parquet')

# SQLite database utilities for team groups - inlined from db_utils.py
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"Created data directory at {DATA_DIR}")

DB_PATH = os.path.join(DATA_DIR, 'team_groups.db')

def init_db():
    """Initialize the SQLite database for team groups."""
    # Get the directory path
    dir_path = os.path.join(os.path.dirname(__file__), 'data')

    # Create the directory if it doesn't exist
    os.makedirs(dir_path, exist_ok=True)

    # Set the database path
    db_path = os.path.join(dir_path, 'team_groups.db')
    print(f"Initializing SQLite database at {db_path}")

    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable foreign key support
    cursor.execute("PRAGMA foreign_keys = ON")

    # Create the team_groups table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create the team_group_members table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_group_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        team_name TEXT NOT NULL,
        FOREIGN KEY (group_id) REFERENCES team_groups(id) ON DELETE CASCADE,
        UNIQUE(group_id, team_name)
    )
    ''')

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

def get_db_connection():
    """Get a SQLite database connection."""
    # Get the directory path
    dir_path = os.path.join(os.path.dirname(__file__), 'data')

    # Create the directory if it doesn't exist
    os.makedirs(dir_path, exist_ok=True)

    # Set the database path
    db_path = os.path.join(dir_path, 'team_groups.db')

    # Connect to the database and enable foreign keys
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    return conn

def create_team_group(name, teams):
    """Create a new team group."""
    print(f"Attempting to create team group '{name}' with {len(teams)} teams")
    if not name or not teams:
        print(f"Invalid team group creation: name='{name}', teams count={len(teams) if teams else 0}")
        return False

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Insert the team group
        cursor.execute("INSERT INTO team_groups (name) VALUES (?)", (name,))
        group_id = cursor.lastrowid

        # Insert the team members
        for team in teams:
            cursor.execute(
                "INSERT INTO team_group_members (group_id, team_name) VALUES (?, ?)",
                (group_id, team)
            )

        conn.commit()
        print(f"Successfully created team group '{name}' with {len(teams)} teams at {DB_PATH}")
        return True
    except sqlite3.IntegrityError as e:
        print(f"Error creating team group: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_team_groups():
    """Get all team groups from the database."""
    print(f"Retrieving team groups from {get_db_connection().execute('PRAGMA database_list').fetchone()[2]}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Get all team groups
        cursor.execute("SELECT id, name FROM team_groups ORDER BY name")
        groups = cursor.fetchall()

        # Create a dictionary of team groups
        team_groups = {}
        for group_id, group_name in groups:
            # Get all teams in the group
            cursor.execute("SELECT team_name FROM team_group_members WHERE group_id = ?", (group_id,))
            teams = [row[0] for row in cursor.fetchall()]
            team_groups[group_name] = teams

        print(f"Found {len(team_groups)} team groups in database")
        return team_groups
    except sqlite3.Error as e:
        print(f"Error retrieving team groups: {str(e)}")
        return {}
    finally:
        conn.close()

def update_team_group(name, teams):
    """Update an existing team group."""
    if not name:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Get the group ID
        cursor.execute("SELECT id FROM team_groups WHERE name = ?", (name,))
        row = cursor.fetchone()

        if not row:
            print(f"Team group '{name}' not found")
            return False

        group_id = row[0]

        # Delete existing members
        cursor.execute("DELETE FROM team_group_members WHERE group_id = ?", (group_id,))

        # Insert new members
        for team in teams:
            cursor.execute(
                "INSERT INTO team_group_members (group_id, team_name) VALUES (?, ?)",
                (group_id, team)
            )

        conn.commit()
        print(f"Updated team group '{name}' with {len(teams)} teams")
        return True
    except sqlite3.Error as e:
        print(f"Error updating team group: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def delete_team_group(name):
    """Delete a team group."""
    if not name:
        print(f"Error: Cannot delete team group with empty name")
        return False

    print(f"Attempting to delete team group: '{name}'")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Start a transaction
        conn.execute("BEGIN TRANSACTION")

        # Enable foreign keys for cascading deletes
        cursor.execute("PRAGMA foreign_keys = ON")

        # First check if the group exists
        cursor.execute("SELECT id FROM team_groups WHERE name = ?", (name,))
        group = cursor.fetchone()

        if not group:
            print(f"Error: Team group '{name}' not found in database")
            return False

        group_id = group[0]
        print(f"Found team group with ID: {group_id}")

        # Count members to be deleted
        cursor.execute("SELECT COUNT(*) FROM team_group_members WHERE group_id = ?", (group_id,))
        member_count = cursor.fetchone()[0]
        print(f"Team group has {member_count} members that will be deleted")

        # First delete the members explicitly, ignoring errors
        try:
            cursor.execute("DELETE FROM team_group_members WHERE group_id = ?", (group_id,))
            print(f"Deleted {member_count} team members")
        except sqlite3.Error as e:
            print(f"Warning when deleting members: {str(e)}")
            # Continue with deletion of the group

        # Then delete the team group
        cursor.execute("DELETE FROM team_groups WHERE id = ?", (group_id,))

        # Verify the deletion
        cursor.execute("SELECT id FROM team_groups WHERE id = ?", (group_id,))
        if cursor.fetchone():
            print(f"Error: Group {group_id} still exists after attempted deletion")
            conn.rollback()
            return False

        # Commit and return success
        conn.commit()
        print(f"Successfully deleted team group '{name}' with ID {group_id}")
        return True
    except sqlite3.Error as e:
        print(f"Database error deleting team group: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

# Initialize the SQLite database for team groups
init_db()

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

# Get team groups from the database
team_groups = get_team_groups()
print(f"Loaded {len(team_groups)} team groups")

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

/* Fix for date picker overlapping issues */
.DayPicker {
    z-index: 1500 !important;
    background-color: white !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2) !important;
}

.DayPicker_focusRegion,
.DayPicker_focusRegion_1 {
    background-color: white !important;
    z-index: 1500 !important;
}

.CalendarMonth {
    background-color: white !important;
}

.DayPicker_transitionContainer {
    background-color: white !important;
}

.DayPickerNavigation {
    z-index: 1501 !important;
}

.DayPicker_portal {
    z-index: 1502 !important;
    background-color: rgba(255, 255, 255, 0.95) !important;
}

/* Additional fixes for date picker */
.CalendarMonthGrid {
    background-color: white !important;
}

.DateRangePicker_picker {
    background-color: white !important;
    z-index: 1500 !important;
}

.SingleDatePicker_picker {
    background-color: white !important;
    z-index: 1500 !important;
}

.CalendarMonth_table {
    background-color: white !important;
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

/* Loading Spinner Styles */
.dash-spinner.dash-default-spinner {
    opacity: 0.7;
    width: 45px !important;
    height: 45px !important;
    border-width: 5px !important;
    border-color: var(--primary) !important;
    border-bottom-color: transparent !important;
    border-radius: 50% !important;
}

.dash-spinner.dash-circle-spinner {
    opacity: 0.7;
    width: 45px !important;
    height: 45px !important;
    border-width: 5px !important;
    border-color: var(--primary) !important;
    border-bottom-color: transparent !important;
    border-radius: 50% !important;
}

.dash-spinner-container {
    background-color: rgba(255, 255, 255, 0.8) !important;
}

/* Fullscreen loading overlay */
._dash-loading {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(255, 255, 255, 0.85);
    z-index: 9999;
    display: flex;
    justify-content: center;
    align-items: center;
}

._dash-loading-callback::after {
    content: 'Loading dashboard...';
    font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    font-size: 1.5rem;
    color: var(--primary);
    margin-top: 1rem;
    margin-left: -1rem;
}

._dash-loading::before {
    content: '';
    display: block;
    width: 80px;
    height: 80px;
    border-radius: 50%;
    border: 6px solid var(--primary);
    border-color: var(--primary) transparent var(--primary) transparent;
    animation: dash-spinner 1.2s linear infinite;
}

@keyframes dash-spinner {
    0% {
        transform: rotate(0deg);
    }
    100% {
        transform: rotate(360deg);
    }
}
'''

# Initialize the Dash app with Bootstrap
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.FONT_AWESOME
    ],
    # Use this to optimize load time and add custom loading
    update_title='Loading...',
    suppress_callback_exceptions=True,
    title='NC Soccer Analytics Dashboard'
)
server = app.server  # Needed for gunicorn deployment

# Add the custom CSS to the app's assets
if not os.path.exists(os.path.join(os.path.dirname(__file__), 'assets')):
    os.makedirs(os.path.join(os.path.dirname(__file__), 'assets'))

with open(os.path.join(os.path.dirname(__file__), 'assets', 'custom.css'), 'w') as f:
    f.write(custom_css)

# Create a spinner container with text for better loading UX
loading_spinner = dbc.Spinner(
    id="loading-spinner",
    fullscreen=True,
    color="#6F42C1",
    type="grow",
    children=[
        html.Div([
            html.H3("Loading NC Soccer Analytics Dashboard...",
                   style={"color": "#6F42C1", "text-align": "center", "margin-top": "20px"}),
            html.P("Please wait while we prepare your data.",
                  style={"color": "#5B6AFE", "text-align": "center"})
        ])
    ]
)

# Define the app layout with a standard two-column design
app.layout = dbc.Container([
    # Loading spinner container that will be shown/hidden via callbacks
    html.Div(
        id="loading-spinner-container",
        children=[loading_spinner],
        style={"display": "block"}  # Initially visible
    ),

    # Top Header Row
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("Game Dashboard", className="text-center my-3")
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

                html.Label("Team Selection Type:", className="fw-bold mb-2"),
                dcc.RadioItems(
                    id='team-selection-type',
                    options=[
                        {'label': 'Individual Team', 'value': 'individual'},
                        {'label': 'Team Group', 'value': 'group'}
                    ],
                    value='individual',
                    className="mb-2"
                ),

                html.Div(
                    [
                        html.Label("Select Team Group:", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id='team-group-dropdown',
                            options=[{'label': group_name, 'value': group_name} for group_name in team_groups.keys()],
                            value=next(iter(team_groups.keys())) if team_groups else None,
                            searchable=True,
                            className="mb-2",
                            placeholder="Select a team group"
                        )
                    ],
                    id="team-group-selection-div",
                    style={'display': 'none'}
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

                html.Div(
                    [
                        html.Label("Select Opponent(s):", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id='opponent-selection',
                            options=[], # Will be updated dynamically
                            value=[],
                            multi=True,
                            searchable=True,
                            className="mb-2",
                            placeholder="Select one or more opponents"
                        ),
                        html.Div(
                            [
                                html.Label("Competitiveness Threshold:", className="fw-bold mb-2"),
                                dcc.Slider(
                                    id='competitiveness-threshold',
                                    min=0,
                                    max=100,
                                    step=5,
                                    value=30,
                                    marks={
                                        0: {'label': '0%', 'style': {'color': '#28A745'}},
                                        30: {'label': '30%', 'style': {'color': '#5B6AFE'}},
                                        70: {'label': '70%', 'style': {'color': '#DC3545'}},
                                        100: {'label': '100%', 'style': {'color': '#DC3545'}}
                                    },
                                    className="mb-1"
                                ),
                                html.P("Teams you've lost to or had close matches with (higher = more challenging opponents)",
                                       className="small text-muted mb-3")
                            ],
                            id="worthy-adversaries-controls",
                            style={'display': 'none'}
                        )
                    ],
                    id="opponent-selection-div",
                    style={'display': 'none'}
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

                # Team Groups Management Section
                html.Div([
                    html.H5("Team Groups Management", className="mb-3", style={'color': '#5B6AFE'}),

                    html.Label("Create New Team Group:", className="fw-bold mb-2"),
                    dbc.Input(
                        id="new-group-name",
                        type="text",
                        placeholder="Enter group name",
                        className="mb-2"
                    ),
                    html.Div([
                        html.Label("Select teams to include:", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id='teams-for-group',
                            options=[{'label': team, 'value': team} for team in teams if team != 'Key West (Combined)'],
                            value=[],
                            multi=True,
                            className="mb-2",
                            placeholder="Select teams to include in this group",
                            style={'position': 'relative', 'zIndex': 1010}
                        ),
                    ], style={'position': 'relative', 'zIndex': 1000}),
                    dbc.Button(
                        "Create Group",
                        id="create-group-button",
                        color="primary",
                        className="mb-3"
                    ),

                    html.Div([
                        html.Label("Edit Existing Group:", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id='edit-group-dropdown',
                            options=[{'label': group_name, 'value': group_name} for group_name in team_groups.keys()],
                            placeholder="Select group to edit",
                            className="mb-2",
                            style={'position': 'relative'},
                        ),
                        html.Label("Select teams to edit:", className="fw-bold mb-2"),
                        html.Div([
                            dcc.Dropdown(
                                id='edit-teams-for-group',
                                options=[{'label': team, 'value': team} for team in teams if team != 'Key West (Combined)'],
                                value=[],
                                multi=True,
                                className="mb-2",
                                placeholder="Select teams to include in this group",
                                style={'position': 'relative', 'zIndex': 1010}
                            ),
                        ], style={'position': 'relative', 'zIndex': 1000}),
                        dbc.ButtonGroup([
                            dbc.Button(
                                "Update Group",
                                id="update-group-button",
                                color="primary",
                                className="me-2"
                            ),
                            dbc.Button(
                                "Delete Group",
                                id="delete-group-button",
                                color="danger"
                            ),
                        ], className="mb-3 d-flex"),
                    ], id="edit-group-div"),

                    html.Div(id="group-management-status", className="small text-muted my-2")
                ], className="mb-4"),

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

            # Summary statistics cards in a single row at the top of the story
            html.H4("Performance Summary", className="section-header"),
            dcc.Loading(
                id="loading-performance-metrics",
                type="circle",
                color="#6F42C1",
                children=[
                    dbc.Row([
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
                ]
            ),

            # Performance trend chart
            html.H4("Performance Over Time", className="section-header"),
            dcc.Loading(
                id="loading-performance-chart",
                type="default",
                color="#6F42C1",
                children=[
                    dbc.Card([
                        dbc.CardBody([
                            html.P("This chart shows the cumulative wins, draws, and losses over the selected time period."),
                            dcc.Graph(id="performance-trend")
                        ])
                    ], className="mb-4")
                ]
            ),

            # Goal statistics - with bar chart and pie chart side by side
            html.H4("Goal Analysis", className="section-header"),
            dcc.Loading(
                id="loading-goal-charts",
                type="default",
                color="#6F42C1",
                children=[
                    dbc.Card([
                        dbc.CardBody([
                            html.P("Breakdown of goals scored, conceded, and the resulting goal difference."),
                            dbc.Row([
                                dbc.Col([
                                    dcc.Graph(id="goal-stats-chart")
                                ], md=6),
                                dbc.Col([
                                    dcc.Graph(id="goal-stats-pie")
                                ], md=6)
                            ])
                        ])
                    ], className="mb-4")
                ]
            ),

            # Opponent Analysis Section (conditionally displayed)
            html.Div(
                [
                    html.H4("Opponent Analysis", className="section-header"),
                    dcc.Loading(
                        id="loading-opponent-analysis",
                        type="default",
                        color="#6F42C1",
                        children=[
                            dbc.Card([
                                dbc.CardHeader("Opponent Performance Comparison"),
                                dbc.CardBody([
                                    html.P(id="opponent-analysis-text", children="Detailed comparison against selected opponents."),
                                    dcc.Graph(id="opponent-comparison-chart")
                                ])
                            ], className="mb-4"),

                            dbc.Row([
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardHeader("Win/Loss Distribution"),
                                        dbc.CardBody([
                                            dcc.Graph(id="opponent-win-rate-chart")
                                        ])
                                    ])
                                ], md=6),
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardHeader("Goal Performance"),
                                        dbc.CardBody([
                                            dcc.Graph(id="opponent-goal-diff-chart")
                                        ])
                                    ])
                                ], md=6),
                            ], className="mb-3")
                        ]
                    )
                ],
                id="opponent-analysis-section",
                className="mb-4",
                style={'display': 'block'}  # Make visible by default
            ),

            # Detailed match results
            html.H4("Match Details", className="section-header"),
            dcc.Loading(
                id="loading-match-results",
                type="default",
                color="#6F42C1",
                children=[
                    dbc.Card([
                        dbc.CardBody([
                            html.P("Complete record of individual matches during the selected period."),
                            dash_table.DataTable(
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
                    ], className="mb-4")
                ]
            ),

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
    # Use default date range if not provided
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not team:
        team = 'Key West (Combined)'

    # Common filter conditions
    filter_conditions = f"date >= '{start_date}' AND date <= '{end_date}'"

    # Debug query to check what games are in 2025
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

    # Find all possible Key West team variations
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

    # Print selected date range for debugging
    print(f"Debug: Date range selected: {start_date} to {end_date}")

    # Handle Key West (Combined) option - use LIKE for all Key West teams
    if team == 'Key West (Combined)':
        team_filter = """(
            LOWER(home_team) LIKE '%key west%' OR
            LOWER(home_team) LIKE '%keywest%' OR
            LOWER(home_team) LIKE '%key-west%' OR
            LOWER(home_team) LIKE '%keywest%' OR
            LOWER(home_team) LIKE '%kw%' OR
            LOWER(home_team) = 'kwfc' OR
            LOWER(home_team) LIKE '%key west%' OR
            LOWER(home_team) LIKE '%keystone%' OR
            LOWER(away_team) LIKE '%key west%' OR
            LOWER(away_team) LIKE '%keywest%' OR
            LOWER(away_team) LIKE '%key-west%' OR
            LOWER(away_team) LIKE '%keywest%' OR
            LOWER(away_team) LIKE '%kw%' OR
            LOWER(away_team) = 'kwfc' OR
            LOWER(away_team) LIKE '%key west%' OR
            LOWER(away_team) LIKE '%keystone%'
        )"""

        # Debug query to check what Key West games are in the dataset
        debug_keywest_query = f"""
        SELECT date, home_team, away_team, home_score, away_score
        FROM soccer_data
        WHERE {team_filter} AND {filter_conditions}
        ORDER BY date
        """
        debug_keywest_df = conn.execute(debug_keywest_query).fetchdf()
        print(f"Debug: Found {len(debug_keywest_df)} Key West games after filtering")
        for _, row in debug_keywest_df.iterrows():
            print(f"Debug: Key West Game - {row['date']} - {row['home_team']} vs {row['away_team']}")

        # Query to get team match data (both home and away) for all Key West teams
        matches_query = f"""
        SELECT date, home_team, away_team, home_score, away_score,
               CASE
                   WHEN LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%key-west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%kw%' OR LOWER(home_team) = 'kwfc' OR LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keystone%' THEN home_score
                   WHEN LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%key-west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%kw%' OR LOWER(away_team) = 'kwfc' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keystone%' THEN away_score
                   ELSE 0
               END AS team_score,
               CASE
                   WHEN LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%key-west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%kw%' OR LOWER(home_team) = 'kwfc' OR LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keystone%' THEN away_score
                   WHEN LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%key-west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%kw%' OR LOWER(away_team) = 'kwfc' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keystone%' THEN home_score
                   ELSE 0
               END AS opponent_score,
               CASE
                   WHEN LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%key-west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%kw%' OR LOWER(home_team) = 'kwfc' OR LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keystone%' THEN away_team
                   WHEN LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%key-west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%kw%' OR LOWER(away_team) = 'kwfc' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keystone%' THEN home_team
                   ELSE ''
               END AS opponent_team,
               CASE
                   WHEN (LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%key-west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%kw%' OR LOWER(home_team) = 'kwfc' OR LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keystone%') AND home_score > away_score THEN 'Win'
                   WHEN (LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%key-west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%kw%' OR LOWER(away_team) = 'kwfc' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keystone%') AND away_score > home_score THEN 'Win'
                   WHEN home_score = away_score THEN 'Draw'
                   ELSE 'Loss'
               END AS result
        FROM soccer_data
        WHERE ({filter_conditions}) AND {team_filter}
        ORDER BY date DESC
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
                   WHEN home_team = '{team}' THEN away_team
                   WHEN away_team = '{team}' THEN home_team
                   ELSE ''
               END AS opponent_team,
               CASE
                   WHEN home_team = '{team}' AND home_score > away_score THEN 'Win'
                   WHEN away_team = '{team}' AND away_score > home_score THEN 'Win'
                   WHEN home_score = away_score THEN 'Draw'
                   ELSE 'Loss'
               END AS result
        FROM soccer_data
        WHERE ({filter_conditions}) AND (home_team = '{team}' OR away_team = '{team}')
        ORDER BY date DESC
        """

    matches_df = conn.execute(matches_query).fetchdf()

    # Apply opponent filter if needed
    display_opponent_analysis = {'display': 'block'}  # Default to show opponent analysis

    # Apply opponent filters to get filtered dataset
    filtered_matches_df = matches_df.copy()

    if opponent_filter_type == 'specific' and opponent_selection and len(opponent_selection) > 0:
        # Normalize opponent names for case-insensitive matching
        # Create normalized versions of opponent names for matching
        if not filtered_matches_df.empty:
            filtered_matches_df['normalized_opponent'] = filtered_matches_df['opponent_team'].str.lower().str.replace('[^a-z0-9]', '', regex=True)
            # Create normalized versions of the selected opponents
            normalized_selection = [op.lower().replace(' ', '').replace('-', '').replace('_', '') for op in opponent_selection]

            # Filter using normalized names
            mask = filtered_matches_df['normalized_opponent'].apply(lambda x: any(norm_op in x or x in norm_op for norm_op in normalized_selection))
            filtered_matches_df = filtered_matches_df[mask]

            print(f"Debug: Selected specific opponents: {opponent_selection}, found {len(filtered_matches_df)} matches")
    elif opponent_filter_type == 'worthy':
        # Use opponent_selection which is automatically populated with all worthy opponents
        if opponent_selection and len(opponent_selection) > 0:
            # Normalize opponent names for case-insensitive matching
            if not filtered_matches_df.empty:
                filtered_matches_df['normalized_opponent'] = filtered_matches_df['opponent_team'].str.lower().str.replace('[^a-z0-9]', '', regex=True)
                # Create normalized versions of the selected opponents
                normalized_selection = [op.lower().replace(' ', '').replace('-', '').replace('_', '') for op in opponent_selection]

                # Filter using normalized names
                mask = filtered_matches_df['normalized_opponent'].apply(lambda x: any(norm_op in x or x in norm_op for norm_op in normalized_selection))
                filtered_matches_df = filtered_matches_df[mask]

                print(f"Debug: Selected worthy opponents: {opponent_selection}, found {len(filtered_matches_df)} matches")
        else:
            # Calculate competitiveness for each opponent
            opponent_groups = filtered_matches_df.groupby('opponent_team')
            worthy_opponents = []
            opponents_with_wins = set()  # Track opponents with wins against us

            # First pass - find opponents with wins against our team
            for opponent, group in opponent_groups:
                opponent_wins = len(group[group['result'] == 'Loss'])
                if opponent_wins > 0:
                    opponents_with_wins.add(opponent)
                    worthy_opponents.append(opponent)
                    print(f"Debug: Dashboard - Auto-including opponent {opponent} who defeated us {opponent_wins} times")

            # Second pass - evaluate other opponents based on competitiveness
            for opponent, group in opponent_groups:
                # Skip opponents who already defeated us (already included)
                if opponent in opponents_with_wins:
                    continue

                if len(group) >= 1:  # Reduced minimum match threshold to 1
                    # Calculate results against this opponent
                    wins = len(group[group['result'] == 'Win'])
                    losses = len(group[group['result'] == 'Loss'])
                    loss_rate = losses / len(group)

                    # Calculate average goal differential (absolute value)
                    group['goal_diff'] = abs(group['team_score'] - group['opponent_score'])
                    avg_goal_diff = group['goal_diff'].mean()

                    # New competitiveness calculation:
                    # - Higher score for teams you've lost to (loss_rate factor)
                    # - Higher score for teams with closer goal difference (inverse relationship)
                    loss_factor = loss_rate * 100  # 0-100 based on loss percentage
                    margin_factor = max(0, 100 - min(avg_goal_diff * 20, 100))  # 0-100 based on goal margin

                    # Combined score: weight loss_factor more heavily (70%) than margin_factor (30%)
                    competitiveness_score = (loss_factor * 0.7) + (margin_factor * 0.3)

                    print(f"Debug: Dashboard - Evaluating opponent: {opponent}, Score: {competitiveness_score:.2f}, Threshold: {competitiveness_threshold}")

                    # Threshold now works as: higher threshold = more challenging opponents
                    if competitiveness_score >= competitiveness_threshold:
                        worthy_opponents.append(opponent)

            if worthy_opponents:
                # Filter using normalized names for case-insensitive matching
                filtered_matches_df['normalized_opponent'] = filtered_matches_df['opponent_team'].str.lower().str.replace('[^a-z0-9]', '', regex=True)
                normalized_worthy = [op.lower().replace(' ', '').replace('-', '').replace('_', '') for op in worthy_opponents]

                mask = filtered_matches_df['normalized_opponent'].apply(lambda x: any(norm_op in x or x in norm_op for norm_op in normalized_worthy))
                filtered_matches_df = filtered_matches_df[mask]

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

    # Calculate summary statistics from the filtered dataset
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

    # Sort data by date (newest first)
    if not filtered_matches_df.empty:
        sorted_df = filtered_matches_df.sort_values(by='date', ascending=True)  # Sort in chronological order for charts
    else:
        sorted_df = pd.DataFrame(columns=filtered_matches_df.columns)  # Empty DataFrame with same columns

    # Create performance trend chart
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

    # Create goal statistics pie chart
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

    # Opponent Analysis Section
    if opponent_filter_type == 'all':
        opponent_analysis_text = f"Analysis of all {len(filtered_matches_df['opponent_team'].unique())} opponents"
    elif opponent_filter_type == 'worthy' and 'worthy_opponents' in locals():
        opponent_analysis_text = f"Analysis of {len(worthy_opponents)} worthy adversaries (competitiveness ≥ {competitiveness_threshold}%)"
    elif opponent_filter_type == 'specific' and opponent_selection:
        opponent_analysis_text = f"Analysis of selected opponent(s): {', '.join(opponent_selection)}"
    else:
        opponent_analysis_text = "No opponent filter selected"

    # Opponent Comparison Charts
    opponent_comparison_chart = go.Figure()
    opponent_win_rate_chart = go.Figure()
    opponent_goal_diff_chart = go.Figure()

    if len(filtered_matches_df) > 0:
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
        opponent_stats_df = pd.DataFrame(opponent_stats_list)

        if not opponent_stats_df.empty:
            # Sort by win rate for the comparison chart
            opponent_stats_df = opponent_stats_df.sort_values('win_rate', ascending=False)

            # Create opponent comparison chart (win rate vs. matches played)
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
                    range=[0, max(opponent_stats_df['total_matches']) * 1.2],
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

            # Create win/loss breakdown pie charts for each opponent
            if len(opponent_stats_df) > 0:
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
                        'text': f'Win/Loss Breakdown vs {opponent_stats_df.iloc[0]["opponent"]}',
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
                    }],
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    margin=dict(l=10, r=10, t=120, b=40)
                )

            # Create goal statistics bar chart by opponent
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
        else:
            # Empty figures for no opponent data
            opponent_comparison_chart.update_layout(
                title="No opponent data available",
                xaxis=dict(showticklabels=False),
                yaxis=dict(showticklabels=False)
            )
            opponent_win_rate_chart.update_layout(
                title="No opponent data available",
                xaxis=dict(showticklabels=False),
                yaxis=dict(showticklabels=False)
            )
            opponent_goal_diff_chart.update_layout(
                title="No opponent data available",
                xaxis=dict(showticklabels=False),
                yaxis=dict(showticklabels=False)
            )
    else:
        # Empty figures for no data
        opponent_comparison_chart.update_layout(
            title="No match data available",
            xaxis=dict(showticklabels=False),
            yaxis=dict(showticklabels=False)
        )
        opponent_win_rate_chart.update_layout(
            title="No match data available",
            xaxis=dict(showticklabels=False),
            yaxis=dict(showticklabels=False)
        )
        opponent_goal_diff_chart.update_layout(
            title="No match data available",
            xaxis=dict(showticklabels=False),
            yaxis=dict(showticklabels=False)
        )

    return (
        games_played,
        win_rate_value,
        loss_rate_value,
        str(goals_scored),
        str(goals_conceded),
        str(goal_diff),
        performance_fig,
        table_data,
        goal_fig,
        pie_fig,
        opponent_analysis_text,
        opponent_comparison_chart,
        opponent_win_rate_chart,
        opponent_goal_diff_chart,
        display_opponent_analysis
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

# Callback to show/hide opponent filter controls
@app.callback(
    [
        Output('opponent-selection-div', 'style'),
        Output('worthy-adversaries-controls', 'style')
    ],
    [Input('opponent-filter-type', 'value')]
)
def toggle_opponent_controls(filter_type):
    if filter_type == 'specific':
        return {'display': 'block'}, {'display': 'none'}
    elif filter_type == 'worthy':
        return {'display': 'block'}, {'display': 'block'}
    else:  # 'all' or any other value
        return {'display': 'none'}, {'display': 'none'}

# Callback to update opponent dropdown options based on filter type
@app.callback(
    [Output('opponent-selection', 'options'),
     Output('opponent-selection', 'value')],  # Add this output to control the selection
    [
        Input('opponent-filter-type', 'value'),
        Input('team-dropdown', 'value'),
        Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('competitiveness-threshold', 'value')
    ]
)
def update_opponent_options(filter_type, team, start_date, end_date, competitiveness_threshold):
    # Default opponents (all teams except selected team)
    all_opponents = [{'label': t, 'value': t} for t in teams if t != team and t != 'Key West (Combined)']

    # If filter type is 'worthy', compute worthy opponents
    if filter_type == 'worthy':
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Get data for the selected team
        filter_conditions = f"date >= '{start_date}' AND date <= '{end_date}'"

        if team == 'Key West (Combined)':
            team_filter = "(LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%key-west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%kw%' OR LOWER(home_team) = 'kwfc' OR LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keystone%' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%key-west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%kw%' OR LOWER(away_team) = 'kwfc' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keystone%')"
            opponent_query = f"""
            SELECT
                CASE
                    WHEN LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%key-west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%kw%' OR LOWER(home_team) = 'kwfc' OR LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keystone%' THEN away_team
                    WHEN LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%key-west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%kw%' OR LOWER(away_team) = 'kwfc' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keystone%' THEN home_team
                END AS opponent,
                CASE
                    WHEN (LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%key-west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%kw%' OR LOWER(home_team) = 'kwfc' OR LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keystone%') AND home_score > away_score THEN 'Win'
                    WHEN (LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%key-west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%kw%' OR LOWER(away_team) = 'kwfc' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keystone%') AND away_score > home_score THEN 'Win'
                    WHEN home_score = away_score THEN 'Draw'
                    ELSE 'Loss'
                END AS result,
                CASE
                    WHEN LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%key-west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%kw%' OR LOWER(home_team) = 'kwfc' OR LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keystone%' THEN home_score
                    WHEN LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%key-west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%kw%' OR LOWER(away_team) = 'kwfc' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keystone%' THEN away_score
                END AS team_score,
                CASE
                    WHEN LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%key-west%' OR LOWER(home_team) LIKE '%keywest%' OR LOWER(home_team) LIKE '%kw%' OR LOWER(home_team) = 'kwfc' OR LOWER(home_team) LIKE '%key west%' OR LOWER(home_team) LIKE '%keystone%' THEN away_score
                    WHEN LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%key-west%' OR LOWER(away_team) LIKE '%keywest%' OR LOWER(away_team) LIKE '%kw%' OR LOWER(away_team) = 'kwfc' OR LOWER(away_team) LIKE '%key west%' OR LOWER(away_team) LIKE '%keystone%' THEN home_score
                END AS opponent_score
            FROM soccer_data
            WHERE ({filter_conditions}) AND {team_filter}
            """
        else:
            opponent_query = f"""
            SELECT
                CASE
                    WHEN home_team = '{team}' THEN away_team
                    WHEN away_team = '{team}' THEN home_team
                END AS opponent,
                CASE
                    WHEN home_team = '{team}' AND home_score > away_score THEN 'Win'
                    WHEN away_team = '{team}' AND away_score > home_score THEN 'Win'
                    WHEN home_score = away_score THEN 'Draw'
                    ELSE 'Loss'
                END AS result,
                CASE
                    WHEN home_team = '{team}' THEN home_score
                    WHEN away_team = '{team}' THEN away_score
                END AS team_score,
                CASE
                    WHEN home_team = '{team}' THEN away_score
                    WHEN away_team = '{team}' THEN home_score
                END AS opponent_score
            FROM soccer_data
            WHERE ({filter_conditions}) AND (home_team = '{team}' OR away_team = '{team}')
            """

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

# Callback to populate edit teams dropdown when a group is selected
@app.callback(
    Output('edit-teams-for-group', 'value'),
    [Input('edit-group-dropdown', 'value')]
)
def populate_edit_teams(group_name):
    if not group_name or group_name not in team_groups:
        return []
    return team_groups[group_name]

# Callback to create a new team group
@app.callback(
    [Output('group-management-status', 'children'),
     Output('new-group-name', 'value'),
     Output('teams-for-group', 'value'),
     Output('edit-group-dropdown', 'options'),
     Output('team-group-dropdown', 'options'),
     Output('team-group-dropdown', 'value')],
    [Input('create-group-button', 'n_clicks'),
     Input('update-group-button', 'n_clicks'),
     Input('delete-group-button', 'n_clicks')],
    [State('new-group-name', 'value'),
     State('teams-for-group', 'value'),
     State('edit-group-dropdown', 'value'),
     State('edit-teams-for-group', 'value'),
     State('team-group-dropdown', 'value')]
)
def manage_team_groups(create_clicks, update_clicks, delete_clicks,
                       new_name, new_teams, edit_name, edit_teams, current_selection):
    """Handle team group management operations."""
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    print(f"Team group management triggered by: {triggered_id}")
    print(f"Current state - Create clicks: {create_clicks}, Update clicks: {update_clicks}, Delete clicks: {delete_clicks}")
    print(f"Edit name: {edit_name}, Edit teams count: {len(edit_teams) if edit_teams else 0}")
    print(f"Current group selection: {current_selection}")

    # Default return values
    status = ""
    new_name_value = ""
    new_teams_value = []
    selected_group = current_selection  # Keep current selection by default

    # Declare global to ensure we update the actual shared variable
    global team_groups

    if triggered_id == 'create-group-button' and new_name and new_teams:
        # Create a new team group
        if create_team_group(new_name, new_teams):
            status = f"Team group '{new_name}' created successfully!"
            # Refresh team groups after successful creation
            team_groups = get_team_groups()
            selected_group = new_name  # Auto-select newly created group
        else:
            status = f"Failed to create team group '{new_name}'. It may already exist."
            new_name_value = new_name
            new_teams_value = new_teams

    elif triggered_id == 'update-group-button' and edit_name and edit_teams:
        # Update an existing team group
        if update_team_group(edit_name, edit_teams):
            status = f"Team group '{edit_name}' updated successfully!"
            # Refresh team groups after successful update
            team_groups = get_team_groups()
            # If current selection is the updated group, keep it selected
            if current_selection == edit_name:
                selected_group = edit_name
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
                print(f"After deletion, available groups: {list(team_groups.keys())}")

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

    # Update dropdown options with refreshed team groups
    print(f"Updating dropdowns with team groups: {list(team_groups.keys())}")
    group_options = [{'label': group_name, 'value': group_name} for group_name in team_groups.keys()]

    # Make sure the selected group still exists
    if selected_group and selected_group not in team_groups:
        if team_groups:
            selected_group = next(iter(team_groups.keys()))
            print(f"Selected group not found, defaulting to: {selected_group}")
        else:
            selected_group = None
            print("No groups available, setting selection to None")

    print(f"Final selected group: {selected_group}")
    return status, new_name_value, new_teams_value, group_options, group_options, selected_group

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)