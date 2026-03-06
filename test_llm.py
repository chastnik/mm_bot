#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к корпоративной LLM
"""
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI
from llm_analyzer import LLMAnalyzer
from config import LLMConfig

def test_llm_connection():
    """Тестирует подключение к корпоративной LLM"""
    print("🧪 ТЕСТ ПОДКЛЮЧЕНИЯ К КОРПОРАТИВНОЙ LLM")
    print("=" * 50)
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Создаем конфигурацию
    llm_config = LLMConfig(
        proxy_token=os.getenv('LLM_PROXY_TOKEN', ''),
        base_url=os.getenv('LLM_BASE_URL', ''),
        model=os.getenv('LLM_MODEL', '')
    )
    
    print(f"📝 Настройки:")
    print(f"   URL: {llm_config.base_url}")
    print(f"   Модель: {llm_config.model}")
    print(f"   Токен: {'✅ есть' if llm_config.proxy_token else '❌ отсутствует'}")
    print()
    
    if not llm_config.proxy_token:
        print("❌ ОШИБКА: Не задан LLM_PROXY_TOKEN в .env файле")
        print("Добавьте в .env файл:")
        print("LLM_PROXY_TOKEN=your_token_here")
        return False

    if not llm_config.base_url:
        print("❌ ОШИБКА: Не задан LLM_BASE_URL в .env файле")
        print("Добавьте в .env файл:")
        print("LLM_BASE_URL=https://litellm.1bitai.ru")
        return False

    if not llm_config.model:
        print("❌ ОШИБКА: Не задан LLM_MODEL в .env файле")
        print("Добавьте в .env файл:")
        print("LLM_MODEL=auragpt")
        return False
    
    # Создаем анализатор
    analyzer = LLMAnalyzer(llm_config)
    client = OpenAI(
        api_key=llm_config.proxy_token,
        base_url=llm_config.base_url.rstrip('/')
    )
    
    # Тест 1: Получение списка моделей
    print("🔍 Тест 1: Получение списка доступных моделей")
    try:
        print(f"🌐 Base URL: {llm_config.base_url}")
        models_response = client.models.list()
        models = [model.id for model in models_response.data if getattr(model, 'id', '')]
        print(f"✅ Получено {len(models)} моделей")
        print(f"📋 Первые 5 моделей: {', '.join(models[:5])}")
        
    except Exception as e:
        print(f"❌ Ошибка при получении моделей: {str(e)}")
    
    print()
    
    # Тест 2: Запрос через Responses API
    print("🔍 Тест 2: Простой запрос к LLM через Responses API")
    try:
        print(f"📡 Отправляю запрос к LLM через Responses API: {llm_config.base_url}")
        print(f"🤖 Модель: {llm_config.model}")
        response = client.responses.create(
            model=llm_config.model,
            input=[
                {
                    "role": "system",
                    "content": "/no_think"
                },
                {
                    "role": "user",
                    "content": "Привет! Ответь кратко: сколько будет 2+2?"
                }
            ]
        )

        content = analyzer._extract_response_text(response)
        if content:
            print(f"✅ Успешный ответ: {content}")
            return True

        print("❌ Получен пустой ответ от LLM")
        print(f"📄 Полный ответ: {response}")
            
    except Exception as e:
        print(f"❌ Ошибка при запросе к LLM: {str(e)}")
    
    print("❌ Получен пустой ответ от LLM")
    return False

if __name__ == "__main__":
    try:
        success = test_llm_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Тесты прерваны пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1) 