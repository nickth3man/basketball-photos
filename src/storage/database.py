import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from src.types.analysis import AnalysisResult
from src.types.errors import DatabaseError

logger = logging.getLogger(__name__)

# Current schema version - increment when making schema changes
SCHEMA_VERSION = 2


class PhotoDatabase:
    """SQLite database for storing photo analysis results."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init_database()

    def _init_database(self) -> None:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()

        self._ensure_schema_version_table(cursor)
        self._run_migrations(cursor)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                format TEXT,
                file_size INTEGER,
                color_mode TEXT,
                aspect_ratio REAL,
                megapixels REAL,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                photo_id INTEGER PRIMARY KEY,
                resolution_clarity REAL,
                composition REAL,
                action_moment REAL,
                lighting REAL,
                color_quality REAL,
                subject_isolation REAL,
                emotional_impact REAL,
                technical_quality REAL,
                relevance REAL,
                instagram_suitability REAL,
                overall_score REAL,
                grade TEXT,
                quality_tier TEXT,
                FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                photo_id INTEGER PRIMARY KEY,
                primary_category TEXT,
                tags TEXT,
                FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_identities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER NOT NULL,
                player_id INTEGER,
                name TEXT,
                jersey_number TEXT,
                team TEXT,
                confidence REAL,
                detection_confidence REAL,
                ocr_confidence REAL,
                bbox TEXT,
                review_status TEXT,
                method TEXT,
                FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_path ON photos(path)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_player_identities_photo ON player_identities(photo_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scores_overall ON scores(overall_score DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_categories_primary ON categories(primary_category)"
        )

        self._conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def _ensure_schema_version_table(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """)

    def _run_migrations(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        current_version = cursor.fetchone()[0]

        if current_version < 1:
            cursor.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (1, "Initial schema with photos, scores, categories tables"),
            )

        if current_version < 2:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_identities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    photo_id INTEGER NOT NULL,
                    player_id INTEGER,
                    name TEXT,
                    jersey_number TEXT,
                    team TEXT,
                    confidence REAL,
                    detection_confidence REAL,
                    ocr_confidence REAL,
                    bbox TEXT,
                    review_status TEXT,
                    method TEXT,
                    FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_player_identities_photo ON player_identities(photo_id)"
            )
            cursor.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (2, "Added player_identities table for NBA player identification"),
            )

    def _save_player_identities(
        self, cursor: sqlite3.Cursor, photo_id: int, identities: list
    ) -> None:
        if not identities:
            return

        cursor.execute("DELETE FROM player_identities WHERE photo_id = ?", (photo_id,))
        for identity in identities:
            cursor.execute(
                """
                INSERT INTO player_identities
                (photo_id, player_id, name, jersey_number, team, confidence,
                 detection_confidence, ocr_confidence, bbox, review_status, method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    photo_id,
                    identity.player_id,
                    identity.name,
                    identity.jersey_number,
                    identity.team,
                    identity.confidence,
                    identity.detection_confidence,
                    identity.ocr_confidence,
                    json.dumps(identity.bbox),
                    identity.review_status,
                    identity.method,
                ),
            )

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DatabaseError("Database connection not initialized")
        return self._conn

    def _save_analysis_rows(
        self, cursor: sqlite3.Cursor, result: AnalysisResult
    ) -> int:
        cursor.execute(
            """
            INSERT OR REPLACE INTO photos 
            (path, filename, width, height, format, file_size, color_mode, aspect_ratio, megapixels, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                result.metadata.path,
                result.metadata.filename,
                result.metadata.width,
                result.metadata.height,
                result.metadata.format,
                result.metadata.file_size,
                result.metadata.color_mode,
                result.metadata.aspect_ratio,
                result.metadata.megapixels,
                datetime.now().isoformat(),
            ),
        )

        photo_id = cursor.lastrowid

        if photo_id == 0:
            cursor.execute(
                "SELECT id FROM photos WHERE path = ?", (result.metadata.path,)
            )
            row = cursor.fetchone()
            photo_id = row["id"] if row else 0

        cursor.execute(
            """
            INSERT OR REPLACE INTO scores
            (photo_id, resolution_clarity, composition, action_moment, lighting,
             color_quality, subject_isolation, emotional_impact, technical_quality,
             relevance, instagram_suitability, overall_score, grade, quality_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                photo_id,
                result.scores.resolution_clarity,
                result.scores.composition,
                result.scores.action_moment,
                result.scores.lighting,
                result.scores.color_quality,
                result.scores.subject_isolation,
                result.scores.emotional_impact,
                result.scores.technical_quality,
                result.scores.relevance,
                result.scores.instagram_suitability,
                result.scores.overall_score,
                result.scores.grade,
                result.scores.quality_tier,
            ),
        )

        cursor.execute(
            """
            INSERT OR REPLACE INTO categories
            (photo_id, primary_category, tags)
            VALUES (?, ?, ?)
        """,
            (
                photo_id,
                result.category,
                json.dumps(result.tags),
            ),
        )

        if photo_id:
            self._save_player_identities(cursor, photo_id, result.player_identities)

        return int(photo_id or 0)

    def save_analysis(self, result: AnalysisResult) -> int:
        with self._transaction() as cursor:
            photo_id = self._save_analysis_rows(cursor, result)

            logger.debug(
                f"Saved analysis for {result.metadata.path} with ID {photo_id}"
            )
            return int(photo_id or 0)

    def get_photo_by_path(self, path: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM photos WHERE path = ?", (path,))
        photo = cursor.fetchone()

        if not photo:
            return None

        photo_dict = dict(photo)
        photo_id = photo_dict["id"]

        cursor.execute("SELECT * FROM scores WHERE photo_id = ?", (photo_id,))
        scores = cursor.fetchone()
        if scores:
            photo_dict["scores"] = dict(scores)

        cursor.execute("SELECT * FROM categories WHERE photo_id = ?", (photo_id,))
        categories = cursor.fetchone()
        if categories:
            photo_dict["categories"] = dict(categories)
            if photo_dict["categories"].get("tags"):
                photo_dict["categories"]["tags"] = json.loads(
                    photo_dict["categories"]["tags"]
                )

        return photo_dict

    def get_all_photos(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.*, s.overall_score, s.grade, c.primary_category
            FROM photos p
            LEFT JOIN scores s ON p.id = s.photo_id
            LEFT JOIN categories c ON p.id = c.photo_id
            ORDER BY s.overall_score DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_photos_by_category(
        self, category: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.*, s.overall_score, s.grade, c.primary_category
            FROM photos p
            JOIN scores s ON p.id = s.photo_id
            JOIN categories c ON p.id = c.photo_id
            WHERE c.primary_category = ?
            ORDER BY s.overall_score DESC
            LIMIT ?
        """,
            (category, limit),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_top_photos(self, limit: int = 10) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.*, s.overall_score, s.grade, c.primary_category
            FROM photos p
            JOIN scores s ON p.id = s.photo_id
            LEFT JOIN categories c ON p.id = c.photo_id
            ORDER BY s.overall_score DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> dict[str, Any]:
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM photos")
        total_photos = cursor.fetchone()["count"]

        cursor.execute("SELECT AVG(overall_score) as avg FROM scores")
        avg_score = cursor.fetchone()["avg"] or 0.0

        cursor.execute("""
            SELECT primary_category, COUNT(*) as count
            FROM categories
            GROUP BY primary_category
            ORDER BY count DESC
        """)
        category_distribution = {
            row["primary_category"]: row["count"] for row in cursor.fetchall()
        }

        cursor.execute("""
            SELECT MIN(overall_score) as min, MAX(overall_score) as max
            FROM scores
        """)
        score_range = cursor.fetchone()

        return {
            "total_photos": total_photos,
            "average_score": round(float(avg_score), 2),
            "min_score": round(float(score_range["min"] or 0.0), 2),
            "max_score": round(float(score_range["max"] or 0.0), 2),
            "category_distribution": category_distribution,
        }

    def delete_photo(self, path: str) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM photos WHERE path = ?", (path,))
        deleted = cursor.rowcount > 0
        conn.commit()

        return deleted

    def clear_all(self) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM photos")
        total_photos = cursor.fetchone()["count"]

        cursor.execute("DELETE FROM categories")
        cursor.execute("DELETE FROM scores")
        cursor.execute("DELETE FROM photos")
        conn.commit()

        return total_photos

    def save_batch(self, results: list[AnalysisResult]) -> list[int]:
        photo_ids: list[int] = []
        with self._transaction() as cursor:
            for result in results:
                photo_ids.append(self._save_analysis_rows(cursor, result))

        logger.info(f"Saved batch of {len(photo_ids)} analyses")
        return photo_ids

    def get_schema_version(self) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        return cursor.fetchone()[0]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info(f"Database connection closed: {self.db_path}")

    def __enter__(self) -> "PhotoDatabase":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
