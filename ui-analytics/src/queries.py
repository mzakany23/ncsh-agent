"""
SQL query generation functions for the soccer dashboard.
This module contains functions to generate SQL queries for retrieving
match data and team information from the soccer database.
"""

def get_team_group_filter(teams):
    """
    Returns SQL filter condition for a team group.

    Args:
        teams: List of team names in the group

    Returns:
        SQL condition that matches if any home_team or away_team is in the group
    """
    if not teams:
        return "(1=0)"  # Return a condition that always evaluates to false

    conditions = []
    for team in teams:
        # Escape single quotes in team names
        escaped_team = team.replace("'", "''")
        conditions.append(f"home_team = '{escaped_team}'")
        conditions.append(f"away_team = '{escaped_team}'")

    return f"({' OR '.join(conditions)})"

def get_key_west_team_filter():
    """
    Returns SQL filter condition for identifying Key West team variations.
    Used to filter matches where Key West (or its variations) is either home or away team.
    """
    return """(
        LOWER(home_team) LIKE '%key west%' OR
        LOWER(home_team) LIKE '%keywest%' OR
        LOWER(home_team) LIKE '%key-west%' OR
        LOWER(home_team) LIKE '%kw%' OR
        LOWER(home_team) = 'kwfc' OR
        LOWER(home_team) LIKE '%keystone%' OR
        LOWER(away_team) LIKE '%key west%' OR
        LOWER(away_team) LIKE '%keywest%' OR
        LOWER(away_team) LIKE '%key-west%' OR
        LOWER(away_team) LIKE '%kw%' OR
        LOWER(away_team) = 'kwfc' OR
        LOWER(away_team) LIKE '%keystone%'
    )"""


def get_key_west_team_identification():
    """
    Returns SQL CASE expression pattern for identifying when a team is Key West.
    Used in multiple query components to identify if home_team or away_team is Key West.
    """
    return """LOWER(home_team) LIKE '%key west%' OR
        LOWER(home_team) LIKE '%keywest%' OR
        LOWER(home_team) LIKE '%key-west%' OR
        LOWER(home_team) LIKE '%kw%' OR
        LOWER(home_team) = 'kwfc' OR
        LOWER(home_team) LIKE '%keystone%'"""


def get_key_west_away_identification():
    """
    Returns SQL CASE expression pattern for identifying when an away team is Key West.
    Used in multiple query components.
    """
    return """LOWER(away_team) LIKE '%key west%' OR
        LOWER(away_team) LIKE '%keywest%' OR
        LOWER(away_team) LIKE '%key-west%' OR
        LOWER(away_team) LIKE '%kw%' OR
        LOWER(away_team) = 'kwfc' OR
        LOWER(away_team) LIKE '%keystone%'"""


def get_combined_matches_query(team, filter_conditions):
    """
    Generate a SQL query for retrieving matches for a combined team (Key West).

    Args:
        team: The team name ('Key West (Combined)')
        filter_conditions: Additional SQL filter conditions (date range, etc.)

    Returns:
        SQL query string for retrieving Key West matches
    """
    if team != 'Key West (Combined)':
        return get_team_matches_query(team, filter_conditions)

    home_team_pattern = get_key_west_team_identification()
    away_team_pattern = get_key_west_away_identification()
    team_filter = get_key_west_team_filter()

    return f"""
    SELECT date, home_team, away_team, home_score, away_score,
        CASE
            WHEN {home_team_pattern} THEN home_score
            WHEN {away_team_pattern} THEN away_score
            ELSE 0
        END AS team_score,
        CASE
            WHEN {home_team_pattern} THEN away_score
            WHEN {away_team_pattern} THEN home_score
            ELSE 0
        END AS opponent_score,
        CASE
            WHEN {home_team_pattern} THEN away_team
            WHEN {away_team_pattern} THEN home_team
            ELSE ''
        END AS opponent_team,
        CASE
            WHEN ({home_team_pattern}) AND home_score > away_score THEN 'Win'
            WHEN ({away_team_pattern}) AND away_score > home_score THEN 'Win'
            WHEN home_score = away_score THEN 'Draw'
            ELSE 'Loss'
        END AS result
    FROM soccer_data
    WHERE ({filter_conditions}) AND {team_filter}
    ORDER BY date DESC
    """


def get_team_matches_query(team, filter_conditions):
    """
    Generate a SQL query for retrieving matches for a specific team.

    Args:
        team: The specific team name
        filter_conditions: Additional SQL filter conditions (date range, etc.)

    Returns:
        SQL query string for retrieving team matches
    """
    return f"""
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


def get_debug_key_west_query(filter_conditions):
    """
    Generate a SQL query for debugging Key West games.

    Args:
        filter_conditions: SQL filter conditions (date range, etc.)

    Returns:
        SQL query string for retrieving debug information about Key West games
    """
    team_filter = get_key_west_team_filter()
    return f"""
    SELECT date, home_team, away_team, home_score, away_score
    FROM soccer_data
    WHERE {team_filter} AND {filter_conditions}
    ORDER BY date
    """


def get_opponent_query_for_key_west(filter_conditions, team_filter=None):
    """
    Generate a SQL query for retrieving opponent information for Key West.

    Args:
        filter_conditions: SQL filter conditions (date range, etc.)
        team_filter: Optional team filter condition

    Returns:
        SQL query string for retrieving opponent data for Key West
    """
    if team_filter is None:
        team_filter = get_key_west_team_filter()

    home_team_pattern = get_key_west_team_identification()
    away_team_pattern = get_key_west_away_identification()

    return f"""
    SELECT
        CASE
            WHEN {home_team_pattern} THEN away_team
            WHEN {away_team_pattern} THEN home_team
        END AS opponent,
        CASE
            WHEN ({home_team_pattern}) AND home_score > away_score THEN 'Win'
            WHEN ({away_team_pattern}) AND away_score > home_score THEN 'Win'
            WHEN home_score = away_score THEN 'Draw'
            ELSE 'Loss'
        END AS result,
        CASE
            WHEN {home_team_pattern} THEN home_score
            WHEN {away_team_pattern} THEN away_score
        END AS team_score,
        CASE
            WHEN {home_team_pattern} THEN away_score
            WHEN {away_team_pattern} THEN home_score
        END AS opponent_score
    FROM soccer_data
    WHERE ({filter_conditions}) AND {team_filter}
    """


def get_opponent_query_for_team(team, filter_conditions):
    """
    Generate a SQL query for retrieving opponent information for a specific team.

    Args:
        team: The specific team name
        filter_conditions: SQL filter conditions (date range, etc.)

    Returns:
        SQL query string for retrieving opponent data for the team
    """
    return f"""
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

def get_team_group_matches_query(teams, filter_conditions):
    """
    Generate a SQL query for retrieving matches for a team group.

    Args:
        teams: List of team names in the group
        filter_conditions: Additional SQL filter conditions (date range, etc.)

    Returns:
        SQL query string for retrieving team group matches
    """
    if not teams:
        # Return a query that gives an empty result
        return "SELECT * FROM soccer_data WHERE 1=0"

    # Create a SQL filter for the team group
    team_filter = get_team_group_filter(teams)

    # Build condition strings without using backslashes in f-strings
    home_conditions = []
    away_conditions = []
    for team in teams:
        # Double the single quotes for SQL escaping
        escaped_team = team.replace("'", "''")
        home_conditions.append(f"home_team = '{escaped_team}'")
        away_conditions.append(f"away_team = '{escaped_team}'")

    home_condition_str = " OR ".join(home_conditions)
    away_condition_str = " OR ".join(away_conditions)

    return f"""
    SELECT date, home_team, away_team, home_score, away_score,
        CASE
            WHEN ({home_condition_str}) THEN home_score
            WHEN ({away_condition_str}) THEN away_score
            ELSE 0
        END AS team_score,
        CASE
            WHEN ({home_condition_str}) THEN away_score
            WHEN ({away_condition_str}) THEN home_score
            ELSE 0
        END AS opponent_score,
        CASE
            WHEN ({home_condition_str}) THEN away_team
            WHEN ({away_condition_str}) THEN home_team
            ELSE ''
        END AS opponent_team,
        CASE
            WHEN ({home_condition_str}) AND home_score > away_score THEN 'Win'
            WHEN ({away_condition_str}) AND away_score > home_score THEN 'Win'
            WHEN home_score = away_score THEN 'Draw'
            ELSE 'Loss'
        END AS result
    FROM soccer_data
    WHERE ({filter_conditions}) AND {team_filter}
    ORDER BY date DESC
    """

def get_opponent_query_for_team_group(teams, filter_conditions):
    """
    Generate a SQL query for retrieving opponent information for a team group.

    Args:
        teams: List of team names in the group
        filter_conditions: SQL filter conditions (date range, etc.)

    Returns:
        SQL query string for retrieving opponent data for the team group
    """
    if not teams:
        return "SELECT * FROM soccer_data WHERE 1=0"  # Empty query

    # Create condition for identifying team matches
    team_filter = get_team_group_filter(teams)

    # Build condition strings without using backslashes in f-strings
    home_conditions = []
    away_conditions = []
    for team in teams:
        # Double the single quotes for SQL escaping
        escaped_team = team.replace("'", "''")
        home_conditions.append(f"home_team = '{escaped_team}'")
        away_conditions.append(f"away_team = '{escaped_team}'")

    home_condition_str = " OR ".join(home_conditions)
    away_condition_str = " OR ".join(away_conditions)

    return f"""
    SELECT
        CASE
            WHEN ({home_condition_str}) THEN away_team
            WHEN ({away_condition_str}) THEN home_team
        END AS opponent,
        CASE
            WHEN ({home_condition_str}) AND home_score > away_score THEN 'Win'
            WHEN ({away_condition_str}) AND away_score > home_score THEN 'Win'
            WHEN home_score = away_score THEN 'Draw'
            ELSE 'Loss'
        END AS result,
        CASE
            WHEN ({home_condition_str}) THEN home_score
            WHEN ({away_condition_str}) THEN away_score
        END AS team_score,
        CASE
            WHEN ({home_condition_str}) THEN away_score
            WHEN ({away_condition_str}) THEN home_score
        END AS opponent_score
    FROM soccer_data
    WHERE ({filter_conditions}) AND {team_filter}
    """