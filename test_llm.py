#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к корпоративной LLM
"""
import os
import sys
import requests
from dotenv import load_dotenv
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
        base_url=os.getenv('LLM_BASE_URL', 'https://llm.1bitai.ru'),
        model=os.getenv('LLM_MODEL', 'llama3.1:8b-instruct-fp16')
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
    
    # Создаем анализатор
    analyzer = LLMAnalyzer(llm_config)
    
    # Тест 1: Получение списка моделей
    print("🔍 Тест 1: Получение списка доступных моделей")
    try:
        models_url = f"{llm_config.base_url}/v1/models"
        print(f"🌐 URL: {models_url}")
        headers = {
            'X-PROXY-AUTH': llm_config.proxy_token,
            'Content-Type': 'application/json',
            'User-Agent': 'Python-LLM-Test/1.0'
        }
        print(f"📋 Заголовки: {headers}")
        
        response = requests.get(models_url, headers=headers, timeout=30)
        
        print(f"📊 Статус ответа: {response.status_code}")
        print(f"📊 Заголовки ответа: {dict(response.headers)}")
        
        if response.status_code == 200:
            models_data = response.json()
            models = [model['id'] for model in models_data.get('data', [])]
            print(f"✅ Получено {len(models)} моделей")
            print(f"📋 Первые 5 моделей: {', '.join(models[:5])}")
        else:
            print(f"❌ Ошибка получения моделей HTTP {response.status_code}")
            print(f"📄 Ответ сервера: {response.text}")
            print("⚠️ Не удалось получить список моделей")
        
    except Exception as e:
        print(f"❌ Ошибка при получении моделей: {str(e)}")
    
    print()
    
    # Тест 2: Запрос к чату
    print("🔍 Тест 2: Простой запрос к LLM")
    try:
        chat_url = f"{llm_config.base_url}/api/chat"
        
        payload = {
            "model": llm_config.model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": "Привет! Ответь кратко: сколько будет 2+2?"
                }
            ]
        }
        
        print(f"📡 Отправляю запрос к LLM: {chat_url}")
        print(f"🤖 Модель: {llm_config.model}")
        print(f"📋 Заголовки: {headers}")
        print(f"📦 Payload: {payload}")
        
        response = requests.post(
            chat_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"📊 Статус ответа: {response.status_code}")
        print(f"📊 Заголовки ответа: {dict(response.headers)}")
        
        if response.status_code == 200:
            response_data = response.json()
            content = response_data.get('message', {}).get('content', '')
            
            if content:
                print(f"✅ Успешный ответ: {content}")
                return True
            else:
                print("❌ Получен пустой ответ от LLM")
                print(f"📄 Полный ответ: {response_data}")
        else:
            print(f"❌ Ошибка HTTP {response.status_code}: {response.text}")
            
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