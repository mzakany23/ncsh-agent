"""
Database utility functions for SQLite team groups.
"""

import os
import sqlite3
from typing import List, Dict, Any, Tuple, Optional
import json

# Path for the SQLite database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'team_groups.db')

def init_db():
    """Initialize the SQLite database with necessary tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create team_groups table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create team_group_members table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_group_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        team_name TEXT NOT NULL,
        FOREIGN KEY (group_id) REFERENCES team_groups (id) ON DELETE CASCADE,
        UNIQUE(group_id, team_name)
    )
    ''')

    # Ensure foreign key constraints are enforced
    cursor.execute('PRAGMA foreign_keys = ON')

    conn.commit()
    conn.close()

    print(f"SQLite database initialized at {DB_PATH}")
    return DB_PATH

def get_connection():
    """Get a SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign key constraints
    return conn

def create_team_group(name: str, teams: List[str]) -> bool:
    """
    Create a new team group.

    Args:
        name: Name of the team group
        teams: List of team names to include in the group

    Returns:
        bool: True if successful, False otherwise
    """
    if not name or not teams:
        return False

    conn = get_connection()
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
        print(f"Created team group '{name}' with {len(teams)} teams")
        return True
    except sqlite3.IntegrityError as e:
        print(f"Error creating team group: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_team_groups() -> Dict[str, List[str]]:
    """
    Get all team groups with their members.

    Returns:
        Dict mapping group names to lists of team names
    """
    conn = get_connection()
    cursor = conn.cursor()

    result = {}

    try:
        # Get all team groups
        cursor.execute("SELECT id, name FROM team_groups ORDER BY name")
        groups = cursor.fetchall()

        # For each group, get its members
        for group_id, group_name in groups:
            cursor.execute(
                "SELECT team_name FROM team_group_members WHERE group_id = ? ORDER BY team_name",
                (group_id,)
            )
            teams = [row[0] for row in cursor.fetchall()]
            result[group_name] = teams

        return result
    finally:
        conn.close()

def update_team_group(name: str, teams: List[str]) -> bool:
    """
    Update an existing team group.

    Args:
        name: Name of the team group to update
        teams: New list of team names for the group

    Returns:
        bool: True if successful, False otherwise
    """
    if not name:
        return False

    conn = get_connection()
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

def delete_team_group(name: str) -> bool:
    """
    Delete a team group.

    Args:
        name: Name of the team group to delete

    Returns:
        bool: True if successful, False otherwise
    """
    if not name:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Delete the team group (members will be cascaded)
        cursor.execute("DELETE FROM team_groups WHERE name = ?", (name,))

        if cursor.rowcount == 0:
            print(f"Team group '{name}' not found")
            return False

        conn.commit()
        print(f"Deleted team group '{name}'")
        return True
    except sqlite3.Error as e:
        print(f"Error deleting team group: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def import_team_groups_from_json(json_path: str) -> bool:
    """
    Import team groups from a JSON file.

    Args:
        json_path: Path to the JSON file

    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(json_path):
        print(f"JSON file not found at {json_path}")
        return False

    try:
        with open(json_path, 'r') as f:
            team_groups = json.load(f)

        success = True
        for group_name, teams in team_groups.items():
            # Try to create the group, if it fails (e.g., already exists), update it
            if not create_team_group(group_name, teams):
                if not update_team_group(group_name, teams):
                    print(f"Failed to import team group '{group_name}'")
                    success = False

        return success
    except Exception as e:
        print(f"Error importing team groups from JSON: {str(e)}")
        return False

def export_team_groups_to_json(json_path: str) -> bool:
    """
    Export team groups to a JSON file.

    Args:
        json_path: Path to save the JSON file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        team_groups = get_team_groups()

        with open(json_path, 'w') as f:
            json.dump(team_groups, f, indent=2)

        print(f"Exported {len(team_groups)} team groups to {json_path}")
        return True
    except Exception as e:
        print(f"Error exporting team groups to JSON: {str(e)}")
        return False