"""Player store for querying NBA database.

Provides read-only access to player, team, and roster data from
the local NBA database (data/nba_raw_data.db).
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/nba_raw_data.db"


class DatabasePlayerStore:
    """Read-only store for querying NBA player data from SQLite database.

    Provides methods to query players, teams, and roster history.
    Handles missing database gracefully with empty results.

    Example:
        with DatabasePlayerStore() as store:
            player = store.get_player_by_id("2544")
            roster = store.get_team_roster("LAL", season_id="2023-24")
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        """Initialize the player store.

        Args:
            db_path: Path to the NBA SQLite database. Defaults to data/nba_raw_data.db.
        """
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._db_exists = Path(self.db_path).exists()

        if not self._db_exists:
            logger.warning(
                f"NBA database not found at {self.db_path}. Queries will return empty results."
            )

    def _get_conn(self) -> sqlite3.Connection | None:
        """Get or create database connection with connection pooling.

        Returns:
            SQLite connection or None if database doesn't exist.
        """
        if not self._db_exists:
            return None

        if self._conn is None:
            try:
                self._conn = sqlite3.connect(self.db_path)
                self._conn.row_factory = sqlite3.Row
                logger.debug(f"Connected to NBA database at {self.db_path}")
            except sqlite3.Error as e:
                logger.error(f"Failed to connect to NBA database: {e}")
                return None

        return self._conn

    def get_player_by_id(self, player_id: str) -> dict[str, Any] | None:
        """Query a player by their NBA player ID.

        Args:
            player_id: NBA player ID as string (e.g., "2544" for LeBron James).

        Returns:
            Player dict with all dim_player fields, or None if not found.
        """
        conn = self._get_conn()
        if conn is None:
            return None

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT player_id, first_name, last_name, full_name, birth_date,
                   birth_city, birth_country, height_cm, weight_kg, position,
                   draft_year, draft_round, draft_number, is_active, bref_id,
                   college, hof
            FROM dim_player
            WHERE player_id = ?
            """,
            (player_id,),
        )

        row = cursor.fetchone()
        return dict(row) if row else None

    def get_player_by_name(self, name: str) -> list[dict[str, Any]]:
        """Fuzzy match players by name (first, last, or full).

        Performs case-insensitive partial matching on full_name.

        Args:
            name: Player name or partial name to search.

        Returns:
            List of matching player dicts, sorted by is_active desc then full_name.
        """
        conn = self._get_conn()
        if conn is None:
            return []

        cursor = conn.cursor()
        # Use LIKE for fuzzy matching on full_name
        search_pattern = f"%{name}%"

        cursor.execute(
            """
            SELECT player_id, first_name, last_name, full_name, birth_date,
                   birth_city, birth_country, height_cm, weight_kg, position,
                   draft_year, draft_round, draft_number, is_active, bref_id,
                   college, hof
            FROM dim_player
            WHERE full_name LIKE ? COLLATE NOCASE
               OR first_name LIKE ? COLLATE NOCASE
               OR last_name LIKE ? COLLATE NOCASE
            ORDER BY is_active DESC, full_name ASC
            """,
            (search_pattern, search_pattern, search_pattern),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_team_roster(
        self, team_abbrev: str, season_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get roster for a team by abbreviation.

        Args:
            team_abbrev: Team abbreviation (e.g., "LAL", "BOS", "GSW").
            season_id: Optional season ID (e.g., "2023-24"). If None, returns
                       current roster (players with end_date IS NULL).

        Returns:
            List of player dicts with player info and roster details.
        """
        conn = self._get_conn()
        if conn is None:
            return []

        cursor = conn.cursor()

        if season_id:
            # Get roster for specific season
            cursor.execute(
                """
                SELECT p.player_id, p.first_name, p.last_name, p.full_name,
                       p.position, p.height_cm, p.weight_kg, p.is_active,
                       r.season_id, r.start_date, r.end_date,
                       t.abbreviation as team_abbrev, t.full_name as team_name
                FROM dim_player p
                JOIN fact_roster r ON p.player_id = r.player_id
                JOIN dim_team t ON r.team_id = t.team_id
                WHERE t.abbreviation = ? COLLATE NOCASE
                  AND r.season_id = ?
                ORDER BY p.full_name ASC
                """,
                (team_abbrev, season_id),
            )
        else:
            # Get current roster (end_date IS NULL)
            cursor.execute(
                """
                SELECT p.player_id, p.first_name, p.last_name, p.full_name,
                       p.position, p.height_cm, p.weight_kg, p.is_active,
                       r.season_id, r.start_date, r.end_date,
                       t.abbreviation as team_abbrev, t.full_name as team_name
                FROM dim_player p
                JOIN fact_roster r ON p.player_id = r.player_id
                JOIN dim_team t ON r.team_id = t.team_id
                WHERE t.abbreviation = ? COLLATE NOCASE
                  AND r.end_date IS NULL
                ORDER BY p.full_name ASC
                """,
                (team_abbrev,),
            )

        return [dict(row) for row in cursor.fetchall()]

    def get_active_players(self) -> list[dict[str, Any]]:
        """Get all currently active players.

        Returns:
            List of active player dicts (is_active=1), sorted by full_name.
        """
        conn = self._get_conn()
        if conn is None:
            return []

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT player_id, first_name, last_name, full_name, birth_date,
                   birth_city, birth_country, height_cm, weight_kg, position,
                   draft_year, draft_round, draft_number, is_active, bref_id,
                   college, hof
            FROM dim_player
            WHERE is_active = 1
            ORDER BY full_name ASC
            """
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_player_team_history(self, player_id: str) -> list[dict[str, Any]]:
        """Get a player's team history from fact_roster.

        Args:
            player_id: NBA player ID as string.

        Returns:
            List of roster entries with team info, sorted by start_date desc.
        """
        conn = self._get_conn()
        if conn is None:
            return []

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.player_id, r.team_id, r.season_id, r.start_date, r.end_date,
                   t.abbreviation as team_abbrev, t.full_name as team_name,
                   t.city as team_city, t.conference, t.division,
                   p.full_name as player_name
            FROM fact_roster r
            JOIN dim_team t ON r.team_id = t.team_id
            JOIN dim_player p ON r.player_id = p.player_id
            WHERE r.player_id = ?
            ORDER BY r.start_date DESC
            """,
            (player_id,),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_team_by_abbrev(self, team_abbrev: str) -> dict[str, Any] | None:
        """Get team info by abbreviation.

        Args:
            team_abbrev: Team abbreviation (e.g., "LAL", "BOS").

        Returns:
            Team dict or None if not found.
        """
        conn = self._get_conn()
        if conn is None:
            return None

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT team_id, abbreviation, full_name, city, nickname,
                   conference, division, color_primary, color_secondary,
                   arena_name, founded_year, bref_abbrev
            FROM dim_team
            WHERE abbreviation = ? COLLATE NOCASE
            """,
            (team_abbrev,),
        )

        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_teams(self) -> list[dict[str, Any]]:
        """Get all NBA teams.

        Returns:
            List of team dicts sorted by abbreviation.
        """
        conn = self._get_conn()
        if conn is None:
            return []

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT team_id, abbreviation, full_name, city, nickname,
                   conference, division, color_primary, color_secondary,
                   arena_name, founded_year, bref_abbrev
            FROM dim_team
            ORDER BY abbreviation ASC
            """
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_seasons(self) -> list[dict[str, Any]]:
        """Get all seasons in the database.

        Returns:
            List of season dicts sorted by start_year desc.
        """
        conn = self._get_conn()
        if conn is None:
            return []

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT season_id, start_year, end_year
            FROM dim_season
            ORDER BY start_year DESC
            """
        )

        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug(f"Closed connection to NBA database: {self.db_path}")

    def __enter__(self) -> "DatabasePlayerStore":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - ensures connection is closed."""
        self.close()
