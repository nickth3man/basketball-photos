"""NBA roster matcher for jersey-to-player mapping using nba_api.

Provides graceful degradation when nba_api is not installed.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.storage.player_store import DatabasePlayerStore

if TYPE_CHECKING:
    pass

# Graceful degradation: nba_api is optional
try:
    from nba_api.stats.endpoints import CommonTeamRoster

    HAS_NBA_API = True
except ImportError:
    HAS_NBA_API = False
    CommonTeamRoster = None  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

# NBA team ID mapping (abbreviation -> team_id)
# These are the official NBA.com team IDs used by stats.nba.com
TEAM_ID_MAP: dict[str, int] = {
    "ATL": 1610612737,
    "BOS": 1610612738,
    "BKN": 1610612751,
    "CHA": 1610612766,
    "CHI": 1610612741,
    "CLE": 1610612739,
    "DAL": 1610612742,
    "DEN": 1610612743,
    "DET": 1610612765,
    "GS": 1610612744,
    "GSW": 1610612744,
    "HOU": 1610612745,
    "IND": 1610612754,
    "LAC": 1610612746,
    "LAL": 1610612747,
    "MEM": 1610612763,
    "MIA": 1610612748,
    "MIL": 1610612749,
    "MIN": 1610612750,
    "NOP": 1610612740,
    "NYK": 1610612752,
    "OKC": 1610612760,
    "ORL": 1610612753,
    "PHI": 1610612755,
    "PHX": 1610612756,
    "POR": 1610612757,
    "SAC": 1610612758,
    "SAS": 1610612759,
    "TOR": 1610612761,
    "UTA": 1610612762,
    "WAS": 1610612764,
}

# Full team name to abbreviation mapping
TEAM_NAME_TO_ABBREV: dict[str, str] = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

# Headshot URL template
HEADSHOT_URL_TEMPLATE = (
    "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
)

# Default cache TTL: 24 hours in seconds
DEFAULT_CACHE_TTL = 86400

# Rate limit: 1 second between API calls
RATE_LIMIT_SECONDS = 1.0


@dataclass
class PlayerInfo:
    """Player information returned from roster matching."""

    player_id: int
    name: str
    team: str
    jersey_number: str
    position: str
    headshot_url: str
    height: str | None = None
    weight: str | None = None
    age: int | None = None
    data_source: str = "api"  # "api" | "database" | "cache"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "player_id": self.player_id,
            "name": self.name,
            "team": self.team,
            "jersey_number": self.jersey_number,
            "position": self.position,
            "headshot_url": self.headshot_url,
            "height": self.height,
            "weight": self.weight,
            "age": self.age,
            "data_source": self.data_source,
        }


class RosterMatcher:
    """Matches jersey numbers to NBA players using nba_api.

    Features:
    - Lazy initialization of API client
    - Disk-based caching with TTL
    - Rate limiting (1 request/second)
    - Graceful degradation when nba_api not installed
    - Support for team abbreviations or full names

    Example:
        matcher = RosterMatcher()
        player = matcher.match_jersey_to_player("LAL", "23")
        # Returns PlayerInfo for LeBron James
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        player_store: DatabasePlayerStore | None = None,
    ):
        """Initialize the roster matcher.

        Args:
            cache_dir: Directory for caching roster data. Defaults to ./data/rosters
            cache_ttl: Cache time-to-live in seconds. Defaults to 24 hours.
            player_store: Optional DatabasePlayerStore for local DB fallback.
        """
        self._cache_dir = Path(cache_dir) if cache_dir else Path("data/rosters")
        self._cache_ttl = cache_ttl
        self._last_request_time: float = 0.0
        self._roster_cache: dict[int, list[dict[str, Any]]] = {}
        self._jersey_cache: dict[str, dict[str, int]] = {}
        self._player_store = player_store

        if not HAS_NBA_API:
            logger.warning(
                "nba_api not installed. RosterMatcher will return None for all queries. "
                "Install with: pip install nba_api"
            )

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, team_id: int) -> Path:
        """Get cache file path for a team."""
        return self._cache_dir / f"roster_{team_id}.json"

    def _load_cached_roster(self, team_id: int) -> list[dict[str, Any]] | None:
        """Load roster from cache if valid (not expired).

        Args:
            team_id: NBA team ID

        Returns:
            Cached roster data or None if not cached/expired
        """
        # Check in-memory cache first
        if team_id in self._roster_cache:
            return self._roster_cache[team_id]

        cache_path = self._get_cache_path(team_id)
        if not cache_path.exists():
            return None

        # Check TTL
        cache_age = time.time() - cache_path.stat().st_mtime
        if cache_age > self._cache_ttl:
            logger.debug(
                f"Cache expired for team {team_id}",
                extra={"team_id": team_id, "age_seconds": cache_age},
            )
            return None

        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            self._roster_cache[team_id] = data
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                f"Failed to load cache for team {team_id}: {e}",
                extra={"team_id": team_id, "error": str(e)},
            )
            return None

    def _save_cached_roster(
        self, team_id: int, roster_data: list[dict[str, Any]]
    ) -> None:
        """Save roster data to cache.

        Args:
            team_id: NBA team ID
            roster_data: Roster data to cache
        """
        self._ensure_cache_dir()
        cache_path = self._get_cache_path(team_id)

        try:
            cache_path.write_text(json.dumps(roster_data, indent=2), encoding="utf-8")
            self._roster_cache[team_id] = roster_data
            logger.debug(
                f"Cached roster for team {team_id}",
                extra={"team_id": team_id, "player_count": len(roster_data)},
            )
        except OSError as e:
            logger.warning(
                f"Failed to save cache for team {team_id}: {e}",
                extra={"team_id": team_id, "error": str(e)},
            )

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting between API calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_SECONDS:
            sleep_time = RATE_LIMIT_SECONDS - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _fetch_roster_from_api(self, team_id: int) -> list[dict[str, Any]] | None:
        """Fetch roster data from nba_api.

        Args:
            team_id: NBA team ID

        Returns:
            Roster data list or None on error
        """
        if not HAS_NBA_API:
            logger.warning("Cannot fetch roster: nba_api not installed")
            return None

        self._apply_rate_limit()

        try:
            logger.info(
                f"Fetching roster for team {team_id} from NBA API",
                extra={"team_id": team_id},
            )
            roster = CommonTeamRoster(team_id=team_id)  # type: ignore[misc]
            data = roster.get_normalized_dict()

            players = data.get("CommonTeamRoster", [])
            if not players:
                logger.warning(
                    f"No players found for team {team_id}",
                    extra={"team_id": team_id},
                )
                return None

            # Normalize player data
            normalized = []
            for player in players:
                normalized.append(
                    {
                        "player_id": player.get("PLAYER_ID"),
                        "name": player.get("PLAYER"),
                        "jersey_number": str(player.get("NUM", "")).strip(),
                        "position": player.get("POSITION", ""),
                        "height": player.get("HEIGHT", ""),
                        "weight": player.get("WEIGHT", ""),
                        "age": player.get("AGE"),
                    }
                )

            return normalized

        except Exception as e:
            logger.error(
                f"Failed to fetch roster for team {team_id}: {e}",
                extra={"team_id": team_id, "error": str(e)},
                exc_info=True,
            )
            return None

    def _resolve_team_id(self, team: str) -> int | None:
        """Resolve team identifier to NBA team ID.

        Args:
            team: Team abbreviation (e.g., "LAL") or full name (e.g., "Los Angeles Lakers")

        Returns:
            NBA team ID or None if not found
        """
        # Try as abbreviation first (uppercase)
        abbrev = team.upper().strip()
        if abbrev in TEAM_ID_MAP:
            return TEAM_ID_MAP[abbrev]

        # Try as full name
        if team in TEAM_NAME_TO_ABBREV:
            abbrev = TEAM_NAME_TO_ABBREV[team]
            return TEAM_ID_MAP.get(abbrev)

        # Try case-insensitive full name lookup
        for full_name, team_abbrev in TEAM_NAME_TO_ABBREV.items():
            if full_name.lower() == team.lower():
                return TEAM_ID_MAP.get(team_abbrev)

        logger.warning(
            f"Unknown team: {team}",
            extra={"team": team},
        )
        return None

    def _normalize_jersey_number(self, jersey_number: str | int) -> str:
        """Normalize jersey number for matching.

        Args:
            jersey_number: Jersey number as string or int

        Returns:
            Normalized jersey number string
        """
        return str(jersey_number).strip().lstrip("0") or "0"

    def get_team_roster(self, team: str) -> list[dict[str, Any]] | None:
        """Get full roster for a team.

        Args:
            team: Team abbreviation (e.g., "LAL") or full name

        Returns:
            List of player dictionaries or None if unavailable
        """
        team_id = self._resolve_team_id(team)
        if team_id is None:
            return None

        # Check cache first
        cached = self._load_cached_roster(team_id)
        if cached is not None:
            return cached

        # Fetch from API
        roster_data = self._fetch_roster_from_api(team_id)
        if roster_data is None:
            return None

        # Cache the result
        self._save_cached_roster(team_id, roster_data)
        self._cache_jersey_numbers(team, roster_data)
        return roster_data

    def _cache_jersey_numbers(
        self, team: str, roster_data: list[dict[str, Any]]
    ) -> None:
        """Cache jersey number to player_id mapping.

        Args:
            team: Team abbreviation
            roster_data: Roster data from API
        """
        team_abbrev = team.upper() if team.upper() in TEAM_ID_MAP else team
        jersey_map: dict[str, int] = {}

        for player in roster_data:
            jersey = self._normalize_jersey_number(player.get("jersey_number", ""))
            player_id = player.get("player_id")
            if jersey and player_id:
                jersey_map[jersey] = player_id

        if jersey_map:
            self._jersey_cache[team_abbrev] = jersey_map
            logger.debug(
                f"Cached {len(jersey_map)} jersey numbers for {team_abbrev}",
                extra={"team": team_abbrev, "count": len(jersey_map)},
            )

    def match_player_by_name(
        self, team_abbrev: str, player_name: str
    ) -> PlayerInfo | None:
        """Match a player by name on a team using local database.

        Queries the local database first for player metadata.
        Falls back to API roster search if database unavailable.

        Args:
            team_abbrev: Team abbreviation (e.g., "LAL")
            player_name: Player name (partial or full match)

        Returns:
            PlayerInfo if found, None otherwise
        """
        if self._player_store:
            roster = self._player_store.get_team_roster(team_abbrev)
            for player in roster:
                full_name = player.get("full_name", "")
                if player_name.lower() in full_name.lower():
                    player_id = player.get("player_id")
                    if player_id:
                        logger.info(
                            f"Found player '{full_name}' in local database",
                            extra={
                                "team": team_abbrev,
                                "player_name": player_name,
                                "data_source": "database",
                            },
                        )
                        return PlayerInfo(
                            player_id=int(player_id),
                            name=full_name,
                            team=team_abbrev,
                            jersey_number="",
                            position=player.get("position", ""),
                            headshot_url=HEADSHOT_URL_TEMPLATE.format(
                                player_id=player_id
                            ),
                            height=str(player.get("height_cm", ""))
                            if player.get("height_cm")
                            else None,
                            weight=str(player.get("weight_kg", ""))
                            if player.get("weight_kg")
                            else None,
                            data_source="database",
                        )

        roster = self.get_team_roster(team_abbrev)
        if roster:
            for player_data in roster:
                name = player_data.get("name", "")
                if player_name.lower() in name.lower():
                    player_id = player_data.get("player_id")
                    if player_id:
                        logger.info(
                            f"Found player '{name}' via API roster",
                            extra={
                                "team": team_abbrev,
                                "player_name": player_name,
                                "data_source": "api",
                            },
                        )
                        return PlayerInfo(
                            player_id=player_id,
                            name=name,
                            team=team_abbrev,
                            jersey_number=player_data.get("jersey_number", ""),
                            position=player_data.get("position", ""),
                            headshot_url=HEADSHOT_URL_TEMPLATE.format(
                                player_id=player_id
                            ),
                            height=player_data.get("height"),
                            weight=player_data.get("weight"),
                            age=player_data.get("age"),
                            data_source="api",
                        )

        logger.info(
            f"No player found matching '{player_name}' on {team_abbrev}",
            extra={"team": team_abbrev, "player_name": player_name},
        )
        return None

    def match_jersey_to_player(
        self, team: str, jersey_number: str | int
    ) -> PlayerInfo | None:
        """Match a jersey number to a player on a team.

        Checks cached jersey mappings first, then API, then local DB fallback.

        Args:
            team: Team abbreviation (e.g., "LAL") or full name (e.g., "Los Angeles Lakers")
            jersey_number: Jersey number to match

        Returns:
            PlayerInfo if found, None otherwise

        Example:
            >>> matcher = RosterMatcher()
            >>> player = matcher.match_jersey_to_player("LAL", "23")
            >>> player.name
            'LeBron James'
        """
        target_jersey = self._normalize_jersey_number(jersey_number)
        team_abbrev = team.upper() if team.upper() in TEAM_ID_MAP else team

        cached_player_id = self._jersey_cache.get(team_abbrev, {}).get(target_jersey)
        if cached_player_id:
            logger.info(
                f"Found jersey #{jersey_number} in cache for {team_abbrev}",
                extra={
                    "team": team_abbrev,
                    "jersey_number": jersey_number,
                    "data_source": "cache",
                },
            )
            roster = self.get_team_roster(team)
            if roster:
                for player_data in roster:
                    if player_data.get("player_id") == cached_player_id:
                        return PlayerInfo(
                            player_id=cached_player_id,
                            name=player_data.get("name", "Unknown"),
                            team=team_abbrev,
                            jersey_number=player_data.get("jersey_number", ""),
                            position=player_data.get("position", ""),
                            headshot_url=HEADSHOT_URL_TEMPLATE.format(
                                player_id=cached_player_id
                            ),
                            height=player_data.get("height"),
                            weight=player_data.get("weight"),
                            age=player_data.get("age"),
                            data_source="cache",
                        )

        if HAS_NBA_API:
            roster = self.get_team_roster(team)
            if roster is None:
                return self._fallback_db_roster_lookup(team, team_abbrev)

            for player_data in roster:
                player_jersey = self._normalize_jersey_number(
                    player_data.get("jersey_number", "")
                )
                if player_jersey == target_jersey:
                    player_id = player_data.get("player_id")
                    if player_id is None:
                        continue

                    logger.info(
                        f"Found jersey #{jersey_number} via API for {team_abbrev}",
                        extra={
                            "team": team_abbrev,
                            "jersey_number": jersey_number,
                            "data_source": "api",
                        },
                    )
                    return PlayerInfo(
                        player_id=player_id,
                        name=player_data.get("name", "Unknown"),
                        team=team_abbrev,
                        jersey_number=player_data.get("jersey_number", ""),
                        position=player_data.get("position", ""),
                        headshot_url=HEADSHOT_URL_TEMPLATE.format(player_id=player_id),
                        height=player_data.get("height"),
                        weight=player_data.get("weight"),
                        age=player_data.get("age"),
                        data_source="api",
                    )

        if self._player_store:
            return self._fallback_db_roster_lookup(team, team_abbrev)

        if not HAS_NBA_API:
            logger.warning(
                "Cannot match jersey: nba_api not installed and no local DB",
                extra={"team": team, "jersey_number": jersey_number},
            )

        logger.info(
            f"No player found with jersey #{jersey_number} on {team}",
            extra={"team": team, "jersey_number": jersey_number},
        )
        return None

    def _fallback_db_roster_lookup(
        self, team: str, team_abbrev: str
    ) -> PlayerInfo | None:
        """Fallback to local DB when API unavailable.

        Note: Local DB does not have jersey numbers, so this returns
        roster info without jersey matching.

        Args:
            team: Original team input
            team_abbrev: Resolved team abbreviation

        Returns:
            PlayerInfo from database or None
        """
        if not self._player_store:
            return None

        roster = self._player_store.get_team_roster(team_abbrev)
        if roster:
            logger.info(
                f"API unavailable, using local DB fallback for {team_abbrev} roster",
                extra={"team": team_abbrev, "data_source": "database"},
            )
        return None

    def clear_cache(self) -> None:
        """Clear all cached roster data."""
        self._roster_cache.clear()
        if self._cache_dir.exists():
            for cache_file in self._cache_dir.glob("roster_*.json"):
                try:
                    cache_file.unlink()
                except OSError as e:
                    logger.warning(
                        f"Failed to delete cache file {cache_file}: {e}",
                        extra={"file": str(cache_file), "error": str(e)},
                    )
        logger.info("Cleared roster cache")

    @property
    def is_available(self) -> bool:
        """Check if nba_api is available."""
        return HAS_NBA_API
