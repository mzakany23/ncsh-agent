"""
Filter-related callbacks for the NC Soccer Analytics Dashboard.
"""

from dash.dependencies import Input, Output
from ..utils.date_utils import get_date_range_from_preset

def register_filter_callbacks(app, conn):
    """Register all filter-related callbacks."""

    @app.callback(
        [Output('date-range', 'start_date'),
         Output('date-range', 'end_date')],
        [Input('date-preset-dropdown', 'value')]
    )
    def update_date_range(preset):
        """Update date range based on preset selection."""
        # Get min and max dates from database
        date_range_query = """
        SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM soccer_data
        """
        date_range_df = conn.execute(date_range_query).fetchdf()
        min_date = date_range_df['min_date'][0].strftime('%Y-%m-%d')
        max_date = date_range_df['max_date'][0].strftime('%Y-%m-%d')

        return get_date_range_from_preset(preset, min_date, max_date)

    @app.callback(
        [
            Output('opponent-selection-div', 'style'),
            Output('worthy-adversaries-controls', 'style')
        ],
        [Input('opponent-filter-type', 'value')]
    )
    def toggle_opponent_controls(filter_type):
        """Show/hide opponent filter controls based on selection."""
        if filter_type == 'specific':
            return {'display': 'block'}, {'display': 'none'}
        elif filter_type == 'worthy':
            return {'display': 'block'}, {'display': 'block'}
        else:  # 'all' or any other value
            return {'display': 'none'}, {'display': 'none'}