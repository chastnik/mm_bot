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
    artifacts_count = sum(len(section.get("items", [])) for section in artifacts_structure.values())

    print(f"✅ БД настроек готова: {config.database.path}")
    print(f"   Типов проектов: {len(project_types)}")
    print(f"   Секций артефактов: {len(artifacts_structure)}")
    print(f"   Артефактов: {artifacts_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
