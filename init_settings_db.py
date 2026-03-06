#!/usr/bin/env python3
"""
Инициализация БД настроек (миграции + первичное заполнение).
"""
import sys

from config import Config
from settings_db import SettingsDatabase


def main() -> int:
    config = Config()
    settings_db = SettingsDatabase(config.database.path)
    settings_db.initialize()

    project_types = settings_db.load_project_types()
    artifacts_structure = settings_db.load_artifacts_structure()
    seed_metadata = settings_db.get_seed_metadata() or {}
    artifacts_count = sum(len(section.get("items", [])) for section in artifacts_structure.values())

    print(f"✅ БД настроек готова: {config.database.path}")
    print(f"   Типов проектов: {len(project_types)}")
    print(f"   Секций артефактов: {len(artifacts_structure)}")
    print(f"   Артефактов: {artifacts_count}")
    if seed_metadata:
        print(f"   Seed version: {seed_metadata.get('seed_version')}")
        print(f"   Seed hash: {seed_metadata.get('seed_hash')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
