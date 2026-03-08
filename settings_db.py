"""
Хранение настроек проверки документов в SQLite с миграциями.
"""
import hashlib
import json
import os
import sqlite3
from typing import Any, Callable, Dict, List, Optional, Tuple


class SettingsDatabase:
    """Работа с БД настроек и версиями схемы."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.seed_path = os.path.join(os.path.dirname(__file__), "settings_seed.json")

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

    def get_user_confluence_credentials(self, user_id: str) -> Optional[Dict[str, str]]:
        """Возвращает сохраненные credentials Confluence для пользователя."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT confluence_username, confluence_password
                FROM user_confluence_credentials
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "username": row["confluence_username"],
            "password": row["confluence_password"],
        }

    def set_user_confluence_credentials(
        self,
        user_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Создает или обновляет credentials Confluence пользователя."""
        if username is None and password is None:
            raise ValueError("Нужно передать username и/или password")

        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT confluence_username, confluence_password
                FROM user_confluence_credentials
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

            if existing is None:
                if username is None or password is None:
                    raise ValueError(
                        "Для первичной настройки нужно передать и username, и password"
                    )
                conn.execute(
                    """
                    INSERT INTO user_confluence_credentials(
                        user_id,
                        confluence_username,
                        confluence_password
                    ) VALUES (?, ?, ?)
                    """,
                    (user_id, username, password),
                )
                return

            resolved_username = username if username is not None else existing["confluence_username"]
            resolved_password = password if password is not None else existing["confluence_password"]

            conn.execute(
                """
                UPDATE user_confluence_credentials
                SET confluence_username = ?,
                    confluence_password = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (resolved_username, resolved_password, user_id),
            )

    def get_seed_metadata(self) -> Optional[Dict[str, Any]]:
        """Возвращает текущую метаинформацию о примененном seed."""
        with self._connect() as conn:
            return self._get_seed_metadata(conn)

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
            (2, "create_seed_metadata_table", self._migration_002_create_seed_metadata_table),
            (3, "create_user_confluence_credentials", self._migration_003_create_user_confluence_credentials),
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

    def _migration_002_create_seed_metadata_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seed_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                seed_version INTEGER NOT NULL,
                seed_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _migration_003_create_user_confluence_credentials(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_confluence_credentials (
                user_id TEXT PRIMARY KEY,
                confluence_username TEXT NOT NULL,
                confluence_password TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _seed_defaults_if_needed(self, conn: sqlite3.Connection) -> None:
        seed_data = self._load_seed_data()
        seed_version = int(seed_data.get("seed_version", 1))
        seed_hash = self._calculate_seed_hash(seed_data)
        project_types_seed = seed_data.get("project_types", {})
        artifacts_structure_seed = seed_data.get("artifacts_structure", {})

        project_types_count = conn.execute("SELECT COUNT(*) AS cnt FROM project_types").fetchone()["cnt"]
        sections_count = conn.execute("SELECT COUNT(*) AS cnt FROM artifact_sections").fetchone()["cnt"]
        artifacts_count = conn.execute("SELECT COUNT(*) AS cnt FROM artifacts").fetchone()["cnt"]
        metadata = self._get_seed_metadata(conn)

        is_empty = project_types_count == 0 and sections_count == 0 and artifacts_count == 0
        seed_changed = metadata is None or metadata.get("seed_hash") != seed_hash
        needs_sync = is_empty or seed_changed
        if not needs_sync:
            return

        self._upsert_project_types(conn, project_types_seed)
        self._upsert_artifacts_structure(conn, artifacts_structure_seed)
        self._set_seed_metadata(conn, seed_version, seed_hash)

    def _upsert_project_types(self, conn: sqlite3.Connection, project_types_seed: Dict[str, str]) -> None:
        for order, (code, name) in enumerate(project_types_seed.items(), start=1):
            conn.execute(
                """
                INSERT INTO project_types(code, name, sort_order, is_active, updated_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    sort_order = excluded.sort_order,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (code, name, order),
            )

    def _upsert_artifacts_structure(
        self, conn: sqlite3.Connection, artifacts_structure_seed: Dict[str, Dict[str, Any]]
    ) -> None:
        for order, (section_code, section_data) in enumerate(artifacts_structure_seed.items(), start=1):
            conn.execute(
                """
                INSERT INTO artifact_sections(code, name, scope, sort_order, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    scope = excluded.scope,
                    sort_order = excluded.sort_order,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (section_code, section_data["name"], self._section_scope(section_code), order),
            )

            for item_order, item_text in enumerate(section_data["items"], start=1):
                conn.execute(
                    """
                    INSERT INTO artifacts(section_code, item_text, sort_order, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(section_code, item_text) DO UPDATE SET
                        sort_order = excluded.sort_order,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (section_code, item_text, item_order),
                )

    def _get_seed_metadata(self, conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
        row = conn.execute(
            "SELECT seed_version, seed_hash FROM seed_metadata WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return {"seed_version": row["seed_version"], "seed_hash": row["seed_hash"]}

    def _set_seed_metadata(self, conn: sqlite3.Connection, seed_version: int, seed_hash: str) -> None:
        conn.execute(
            """
            INSERT INTO seed_metadata(id, seed_version, seed_hash, updated_at)
            VALUES (1, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                seed_version = excluded.seed_version,
                seed_hash = excluded.seed_hash,
                updated_at = CURRENT_TIMESTAMP
            """,
            (seed_version, seed_hash),
        )

    def _calculate_seed_hash(self, seed_data: Dict[str, Any]) -> str:
        canonical_json = json.dumps(seed_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def _load_seed_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.seed_path):
            raise FileNotFoundError(f"Не найден seed-файл настроек: {self.seed_path}")

        with open(self.seed_path, "r", encoding="utf-8") as seed_file:
            data = json.load(seed_file)

        if "project_types" not in data or "artifacts_structure" not in data:
            raise ValueError("Некорректный формат settings_seed.json")
        return data

    def _section_scope(self, section_code: str) -> str:
        normalized = section_code.lower()
        if normalized in ("bi", "dwh", "rpa"):
            return normalized.upper()
        return "ALL"
