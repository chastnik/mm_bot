#!/usr/bin/env python3
"""
Главный файл для запуска бота анализа документов Mattermost
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from config import Config
from mattermost_bot import MattermostBot
from utils import log_with_timestamp

async def main():
    """Главная функция"""
    log_with_timestamp("🤖 Запуск бота анализа документов...")
    
    # Инициализируем конфигурацию
    config = Config()
    
    # Проверяем настройки
    if not config.validate():
        print("❌ Ошибка конфигурации. Проверьте переменные окружения.")
        print("\nНеобходимые переменные:")
        print("- MATTERMOST_URL: URL сервера Mattermost")
        print("- MATTERMOST_TOKEN: Токен бота")
        print("- MATTERMOST_USERNAME: Имя пользователя бота")
        print("- MATTERMOST_PASSWORD: Пароль бота")
        print("- LLM_PROXY_TOKEN: Токен для корпоративной LLM")
        print("- CONFLUENCE_USERNAME: Имя пользователя Confluence")
        print("- CONFLUENCE_PASSWORD: Пароль Confluence")
        return 1
    
    # Создаем экземпляр бота
    bot = MattermostBot(config)
    
    try:
        print("🔄 Подключение к Mattermost...")
        await bot.start()
        
    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал остановки...")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {str(e)}")
        return 1
        
    finally:
        print("🔄 Остановка бота...")
        await bot.stop()
        print("✅ Бот остановлен")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Принудительная остановка")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {str(e)}")
        sys.exit(1) 