"""
Date utility functions for the NC Soccer Analytics Dashboard.
"""

from datetime import date, timedelta

def get_date_range_options():
    """Get date range preset options."""
    today = date.today()

    # Create date range options
    options = [
        {"label": "Last 30 Days", "value": "last_30_days"},
        {"label": "Last 90 Days", "value": "last_90_days"},
        {"label": "This Year", "value": "this_year"},
        {"label": "Last Year", "value": "last_year"},
        {"label": "All Time", "value": "all_time"},
    ]

    return options

def get_date_range_from_preset(preset, min_date, max_date):
    """Get start and end dates based on preset selection."""
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