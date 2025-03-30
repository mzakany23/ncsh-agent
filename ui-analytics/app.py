"""
NC Soccer Hudson - Analytics Dashboard

This dashboard provides visualizations and statistics for soccer match data,
allowing users to filter by date range and team to explore performance metrics.
"""

import os
import sys
import dash
import dash_bootstrap_components as dbc

from src.style import init_style
from src.layout import init_layout
from src.db import init_db, get_team_groups, init_duckdb_connection, get_teams, get_date_range
from src.callback import init_callbacks

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

PARQUET_FILE = os.environ.get('PARQUET_FILE', 'analysis/data/data.parquet')
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DATA_DIR, 'team_groups.db')

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"Created data directory at {DATA_DIR}")

# Initialize databases and get data
try:
    init_db()
    conn = init_duckdb_connection(PARQUET_FILE)
    teams = get_teams(conn)
    team_groups = {}

    try:
        team_groups = get_team_groups()
        print(f"Initial load: Found {len(team_groups)} team groups with keys: {list(team_groups.keys())}")
    except Exception as e:
        print(f"Error during initial team_groups load: {str(e)}")
        team_groups = {}

    min_date, max_date = get_date_range(conn)
except Exception as e:
    print(f"Critical error during initialization: {str(e)}")
    raise

custom_css = init_style()

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.FONT_AWESOME,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    ],
    update_title='Loading...',
    suppress_callback_exceptions=True,
    title='NC Soccer Game Dashboard'
)
server = app.server

if not os.path.exists(os.path.join(os.path.dirname(__file__), 'assets')):
    os.makedirs(os.path.join(os.path.dirname(__file__), 'assets'))

with open(os.path.join(os.path.dirname(__file__), 'assets', 'custom.css'), 'w') as f:
    f.write(custom_css)

init_layout(app, teams, team_groups, conn, min_date, max_date)
init_callbacks(app, teams, team_groups, conn)

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)