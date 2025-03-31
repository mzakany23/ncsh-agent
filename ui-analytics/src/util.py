from datetime import date
import pandas as pd


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


def normalize_team_name(team_name):
    """
    Normalize a team name for case-insensitive matching.

    Args:
        team_name: The team name to normalize

    Returns:
        Normalized team name (lowercase, alphanumeric only)
    """
    if not isinstance(team_name, str):
        return ""
    return team_name.lower().replace(' ', '').replace('-', '').replace('_', '')


def normalize_team_names_in_dataframe(df, column_name='opponent_team', output_column='normalized_opponent'):
    """
    Add a normalized column to a dataframe for easier team name matching.

    Args:
        df: Pandas DataFrame containing team names
        column_name: Column containing team names to normalize
        output_column: Name of the normalized column to add

    Returns:
        DataFrame with additional normalized column
    """
    if df.empty or column_name not in df.columns:
        return df

    normalized_df = df.copy()
    normalized_df[output_column] = normalized_df[column_name].str.lower().str.replace('[^a-z0-9]', '', regex=True)
    return normalized_df


def filter_matches_by_opponents(matches_df, opponents, normalized_column='normalized_opponent'):
    """
    Filter matches dataframe to include only matches against specific opponents.

    Args:
        matches_df: DataFrame containing match data
        opponents: List of opponent team names
        normalized_column: Name of the normalized column to use for matching

    Returns:
        Filtered DataFrame containing only matches against specified opponents
    """
    if matches_df.empty or not opponents or len(opponents) == 0:
        return matches_df

    # Ensure we have a normalized column
    if normalized_column not in matches_df.columns:
        matches_df = normalize_team_names_in_dataframe(matches_df, output_column=normalized_column)

    # Normalize the opponent names for matching
    normalized_opponents = [normalize_team_name(op) for op in opponents]

    print(f"Debug: Filtering matches against opponents: {opponents}")
    print(f"Debug: Normalized opponent names for matching: {normalized_opponents}")
    print(f"Debug: Unique normalized opponents in data: {matches_df[normalized_column].unique()}")

    # Create a mask of matches against the specified opponents using exact matching
    # This improves reliability compared to substring matching
    mask = matches_df['opponent_team'].isin(opponents)

    # If exact matching didn't find all matches, try normalized matching
    if mask.sum() < len(normalized_opponents):
        # Create a mask using normalized values for more flexible matching
        norm_mask = matches_df[normalized_column].isin(normalized_opponents)
        # Combine masks with logical OR
        mask = mask | norm_mask

    filtered_df = matches_df[mask]
    print(f"Debug: Found {len(filtered_df)} matches after opponent filtering")

    return filtered_df


def calculate_competitiveness_score(match_group):
    """
    Calculate a competitiveness score for an opponent based on their match history.

    Args:
        match_group: DataFrame containing matches against a specific opponent

    Returns:
        Competitiveness score (0-100, higher = more competitive)
    """
    if len(match_group) == 0:
        return 0

    # Calculate loss rate
    losses = len(match_group[match_group['result'] == 'Loss'])
    loss_rate = losses / len(match_group)
    loss_factor = loss_rate * 100  # 0-100 based on loss percentage

    # Calculate average goal differential
    match_group['goal_diff'] = abs(match_group['team_score'] - match_group['opponent_score'])
    avg_goal_diff = match_group['goal_diff'].mean()
    margin_factor = max(0, 100 - min(avg_goal_diff * 20, 100))  # 0-100 based on goal margin

    # Combined score: weight loss_factor more heavily (70%) than margin_factor (30%)
    return (loss_factor * 0.7) + (margin_factor * 0.3)


def identify_worthy_opponents(matches_df, competitiveness_threshold):
    """
    Identify worthy opponents based on competitiveness score.

    Args:
        matches_df: DataFrame containing match data
        competitiveness_threshold: Minimum competitiveness score to be considered worthy

    Returns:
        List of worthy opponent team names
    """
    if matches_df.empty:
        return []

    opponent_groups = matches_df.groupby('opponent_team')
    worthy_opponents = []
    opponents_with_wins = set()

    # First pass - identify opponents who have beaten us
    for opponent, group in opponent_groups:
        opponent_wins = len(group[group['result'] == 'Loss'])
        if opponent_wins > 0:
            opponents_with_wins.add(opponent)
            worthy_opponents.append(opponent)

    # Second pass - evaluate other opponents based on competitiveness
    for opponent, group in opponent_groups:
        # Skip opponents who already defeated us (already included)
        if opponent in opponents_with_wins:
            continue

        if len(group) >= 1:
            competitiveness_score = calculate_competitiveness_score(group)
            if competitiveness_score >= competitiveness_threshold:
                worthy_opponents.append(opponent)

    return worthy_opponents