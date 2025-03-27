"""
SQL query building functions for the NC Soccer Analytics Dashboard.
"""

def build_team_matches_query(team, start_date, end_date):
    """Build SQL query for team matches."""
    filter_conditions = f"date >= '{start_date}' AND date <= '{end_date}'"

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

        query = f"""
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
        query = f"""
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

    return query