from datetime import date


def get_date_range_options(conn):
    today = date.today()


    years_query = """
    SELECT DISTINCT EXTRACT(YEAR FROM date) AS year
    FROM soccer_data
    ORDER BY year DESC
    """
    years_df = conn.execute(years_query).fetchdf()
    years = years_df['year'].tolist()


    options = [
        {"label": "Last 30 Days", "value": "last_30_days"},
        {"label": "Last 90 Days", "value": "last_90_days"},
        {"label": "This Year", "value": "this_year"},
        {"label": "Last Year", "value": "last_year"},
        {"label": "All Time", "value": "all_time"},
    ]


    for year in years:
        options.append({"label": f"Year {int(year)}", "value": f"year_{int(year)}"})

    return options