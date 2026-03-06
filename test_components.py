#!/usr/bin/env python3
"""
Скрипт для тестирования компонентов бота анализа документов
"""

import sys
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def test_imports():
    """Тестирует импорт всех модулей"""
    print("🔄 Тестирование импортов...")
    
    try:
        from config import Config
        print("✅ config.py импортирован успешно")
    except ImportError as e:
        print(f"❌ Ошибка импорта config.py: {e}")
        return False
    
    try:
        from document_processor import DocumentProcessor
        print("✅ document_processor.py импортирован успешно")
    except ImportError as e:
        print(f"❌ Ошибка импорта document_processor.py: {e}")
        return False
    
    try:
        from llm_analyzer import LLMAnalyzer
        print("✅ llm_analyzer.py импортирован успешно")
    except ImportError as e:
        print(f"❌ Ошибка импорта llm_analyzer.py: {e}")
        return False
    
    try:
        from pdf_generator import PDFGenerator
        print("✅ pdf_generator.py импортирован успешно")
    except ImportError as e:
        print(f"❌ Ошибка импорта pdf_generator.py: {e}")
        return False
    
    try:
        from mattermost_bot import MattermostBot
        print("✅ mattermost_bot.py импортирован успешно")
    except ImportError as e:
        print(f"❌ Ошибка импорта mattermost_bot.py: {e}")
        return False
    
    return True

def test_config():
    """Тестирует конфигурацию"""
    print("\n🔄 Тестирование конфигурации...")
    
    try:
        from config import Config
        config = Config()
        
        print(f"📋 Mattermost URL: {config.mattermost.url}")
        print(f"📋 Mattermost Username: {config.mattermost.username}")
        print(f"📋 LLM Model: {config.llm.model}")
        print(f"📋 LLM Base URL: {config.llm.base_url}")
        print(f"📋 Confluence URL: {config.confluence.base_url}")
        
        is_valid = config.validate()
        if is_valid:
            print("✅ Конфигурация валидна")
        else:
            print("⚠️  Конфигурация невалидна - заполните переменные окружения")
        
        return is_valid
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании конфигурации: {e}")
        return False

def test_llm_analyzer():
    """Тестирует LLM анализатор"""
    print("\n🔄 Тестирование LLM анализатора...")
    
    try:
        from llm_analyzer import LLMAnalyzer
        from config import Config
        
        config = Config()
        analyzer = LLMAnalyzer(config.llm)
        print("✅ LLM анализатор инициализирован успешно")
        
        # Проверяем доступные модели
        models = analyzer.get_available_models()
        if models:
            print(f"✅ Получено {len(models)} доступных моделей")
            print(f"📋 Первые 3 модели: {', '.join(models[:3])}")
        else:
            print("⚠️ Не удалось получить список моделей")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании LLM анализатора: {e}")
        return False

def test_pdf_generator():
    """Тестирует генератор PDF"""
    print("\n🔄 Тестирование PDF генератора...")
    
    try:
        from pdf_generator import PDFGenerator
        
        generator = PDFGenerator()
        print("✅ PDF генератор инициализирован успешно")
        
        # Создаем тестовые данные
        test_analysis = {
            'found_artifacts': [
                {
                    'name': 'Тестовый артефакт',
                    'status': 'НАЙДЕН',
                    'source': 'Тестовый документ, страница 1',
                    'description': 'Тестовое описание'
                }
            ],
            'not_found_artifacts': [
                {
                    'name': 'Отсутствующий артефакт',
                    'status': 'НЕ НАЙДЕН',
                    'source': '',
                    'description': ''
                }
            ],
            'partially_found_artifacts': [],
            'summary': {
                'total_artifacts': 2,
                'found_count': 1,
                'not_found_count': 1,
                'partially_found_count': 0
            }
        }
        
        test_documents = [
            {
                'name': 'Тестовый документ.pdf',
                'type': 'file',
                'format': '.pdf',
                'pages': 5
            }
        ]
        
        pdf_data = generator.generate_report(test_analysis, ['BI'], test_documents)
        
        if pdf_data and len(pdf_data) > 0:
            print("✅ PDF отчет сгенерирован успешно")
            print(f"📄 Размер PDF: {len(pdf_data)} байт")
            
            # Сохраняем тестовый PDF
            with open('test_report.pdf', 'wb') as f:
                f.write(pdf_data)
            print("💾 Тестовый PDF сохранен как test_report.pdf")
            return True
        else:
            print("❌ PDF не был сгенерирован")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании PDF генератора: {e}")
        return False

def test_document_processor():
    """Тестирует обработчик документов"""
    print("\n🔄 Тестирование обработчика документов...")
    
    try:
        from document_processor import DocumentProcessor
        from config import Config
        
        config = Config()
        processor = DocumentProcessor(config.confluence)
        print("✅ Обработчик документов инициализирован успешно")
        
        # Тестируем поддерживаемые форматы
        print(f"📋 Поддерживаемые форматы: {processor.supported_formats}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании обработчика документов: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🧪 Запуск тестов компонентов бота...\n")
    
    tests = [
        ("Импорты", test_imports),
        ("Конфигурация", test_config),
        ("Обработчик документов", test_document_processor),
        ("LLM анализатор", test_llm_analyzer),
        ("PDF генератор", test_pdf_generator),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Критическая ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))
    
    print("\n" + "="*50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nИтого: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
        return 0
    else:
        print("⚠️  Некоторые тесты провалены. Проверьте настройки и зависимости.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 