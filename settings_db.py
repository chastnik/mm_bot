"""
Хранение настроек проверки документов в SQLite с миграциями.
"""
import os
import sqlite3
from typing import Callable, Dict, List, Tuple

from config import ARTIFACTS_STRUCTURE, PROJECT_TYPES


class SettingsDatabase:
    """Работа с БД настроек и версиями схемы."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def initialize(self) -> None:
        """Создает БД, применяет миграции и выполняет первичный seed."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with self._connect() as conn:
            self._ensure_schema_migrations_table(conn)
            self._apply_migrations(conn)
            self._seed_defaults_if_needed(conn)

    def load_project_types(self) -> Dict[str, str]:
        """Возвращает активные типы проектов из БД."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT code, name
                FROM project_types
                WHERE is_active = 1
                ORDER BY sort_order ASC, code ASC
                """
            ).fetchall()
        return {row["code"]: row["name"] for row in rows}

    def load_artifacts_structure(self) -> Dict[str, Dict[str, List[str]]]:
        """Возвращает структуру артефактов в формате, совместимом с текущим кодом."""
        structure: Dict[str, Dict[str, List[str]]] = {}
        with self._connect() as conn:
            sections = conn.execute(
                """
                SELECT code, name
                FROM artifact_sections
                ORDER BY sort_order ASC, code ASC
                """
            ).fetchall()

            for section in sections:
                items_rows = conn.execute(
                    """
                    SELECT item_text
                    FROM artifacts
                    WHERE section_code = ?
                    ORDER BY sort_order ASC, id ASC
                    """,
                    (section["code"],),
                ).fetchall()
                structure[section["code"]] = {
                    "name": section["name"],
                    "items": [row["item_text"] for row in items_rows],
                }
        return structure

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema_migrations_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _apply_migrations(self, conn: sqlite3.Connection) -> None:
        """Применяет все непримененные миграции по порядку."""
        migrations: List[Tuple[int, str, Callable[[sqlite3.Connection], None]]] = [
            (1, "create_settings_tables", self._migration_001_create_settings_tables),
        ]
        applied_rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        applied_versions = {row["version"] for row in applied_rows}

        for version, name, migration in migrations:
            if version in applied_versions:
                continue
            migration(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                (version, name),
            )

    def _migration_001_create_settings_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS project_types (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS artifact_sections (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                scope TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_code TEXT NOT NULL,
                item_text TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(section_code) REFERENCES artifact_sections(code) ON DELETE CASCADE,
                UNIQUE(section_code, item_text)
            );
            """
        )

    def _seed_defaults_if_needed(self, conn: sqlite3.Connection) -> None:
        project_types_count = conn.execute("SELECT COUNT(*) AS cnt FROM project_types").fetchone()["cnt"]
        sections_count = conn.execute("SELECT COUNT(*) AS cnt FROM artifact_sections").fetchone()["cnt"]
        artifacts_count = conn.execute("SELECT COUNT(*) AS cnt FROM artifacts").fetchone()["cnt"]

        if project_types_count == 0:
            for order, (code, name) in enumerate(PROJECT_TYPES.items(), start=1):
                conn.execute(
                    """
                    INSERT INTO project_types(code, name, sort_order, is_active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (code, name, order),
                )

        if sections_count == 0 and artifacts_count == 0:
            for order, (section_code, section_data) in enumerate(ARTIFACTS_STRUCTURE.items(), start=1):
                conn.execute(
                    """
                    INSERT INTO artifact_sections(code, name, scope, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (section_code, section_data["name"], self._section_scope(section_code), order),
                )

                for item_order, item_text in enumerate(section_data["items"], start=1):
                    conn.execute(
                        """
                        INSERT INTO artifacts(section_code, item_text, sort_order)
                        VALUES (?, ?, ?)
                        """,
                        (section_code, item_text, item_order),
                    )

    def _section_scope(self, section_code: str) -> str:
        normalized = section_code.lower()
        if normalized in ("bi", "dwh", "rpa"):
            return normalized.upper()
        return "ALL"
