"""
Конфигурационный файл для бота анализа документов
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

@dataclass
class MattermostConfig:
    """Настройки подключения к Mattermost"""
    url: str
    token: str
    team_name: str
    username: str
    password: Optional[str] = None
    ssl_verify: bool = True  # По умолчанию включена проверка SSL

@dataclass
class LLMConfig:
    """Настройки подключения к корпоративной LLM"""
    proxy_token: str
    base_url: str = "https://llm.1bitai.ru"
    model: str = "llama3.3:70b"
    max_tokens: int = 4096
    stream: bool = False

@dataclass
class ConfluenceConfig:
    """Настройки подключения к Confluence"""
    username: str
    password: str
    base_url: str = "https://confluence.1solution.ru/"
    
class Config:
    """Основной класс конфигурации"""
    
    def __init__(self):
        self.mattermost = MattermostConfig(
            url=os.getenv('MATTERMOST_URL', ''),
            token=os.getenv('MATTERMOST_TOKEN', ''),
            team_name=os.getenv('MATTERMOST_TEAM', ''),
            username=os.getenv('MATTERMOST_USERNAME', ''),
            password=os.getenv('MATTERMOST_PASSWORD', ''),
            ssl_verify=os.getenv('MATTERMOST_SSL_VERIFY', 'true').lower() == 'true'
        )
        
        self.llm = LLMConfig(
            proxy_token=os.getenv('LLM_PROXY_TOKEN', ''),
            base_url=os.getenv('LLM_BASE_URL', 'https://llm.1bitai.ru'),
            model=os.getenv('LLM_MODEL', 'llama3.3:70b')
        )
        
        self.confluence = ConfluenceConfig(
            username=os.getenv('CONFLUENCE_USERNAME', ''),
            password=os.getenv('CONFLUENCE_PASSWORD', '')
        )
    
    def validate(self) -> bool:
        """Проверка корректности настроек"""
        if not self.mattermost.url or not self.mattermost.token:
            print("Ошибка: не настроены параметры Mattermost")
            return False
            
        if not self.llm.proxy_token:
            print("Ошибка: не настроен токен для корпоративной LLM")
            return False
            
        if not self.confluence.username or not self.confluence.password:
            print("Ошибка: не настроены параметры Confluence")
            return False
            
        return True

# Типы проектов
PROJECT_TYPES = {
    'BI': 'Бизнес-аналитика',
    'DWH': 'Хранилище данных',
    'RPA': 'Роботизация процессов',
    'MDM': 'Управление мастер-данными'
}

# Структура артефактов для анализа
ARTIFACTS_STRUCTURE = {
    'general': {
        'name': 'Общие требования',
        'items': [
            'Паспорт проекта',
            'Полное описание решения/системы (предназначение, цели, задачи)',
            'Схема взаимодействия систем',
            'Матрица ответственности (RACI)',
            'Перечень заинтересованных сторон'
        ]
    },
    'technical': {
        'name': 'Техническая документация',
        'items': [
            'Архитектурная схема решения',
            'Описание инфраструктурных компонентов',
            'Конфигурационные файлы (с примерами заполнения)',
            'Логины/пароли/ключи доступа',
            'Параметры подключения к источникам данных',
            'Версии ПО',
            'Список используемых библиотек/зависимостей',
            'Инструкция по развертыванию решения'
        ]
    },
    'bi': {
        'name': 'Для BI-проектов дополнительно',
        'items': [
            'Метаданные всех отчетов',
            'Описание источников данных',
            'Логика расчетов показателей (техническая - формулы, описание)',
            'Правила/стандарты визуализации',
            'Пользовательская документация',
            'История изменений отчетов',
            'Документированные SQL-запросы',
            'Описание процессов ETL',
            'Схемы баз данных'
        ]
    },
    'rpa': {
        'name': 'Для RPA-проектов дополнительно',
        'items': [
            'Сценарии автоматизации (bot-процессы)',
            'Пути к исполняемым файлам',
            'Настройки планировщика задач',
            'Логи работы роботов - пути',
            'Описание контрольных точек',
            'Правила масштабирования'
        ]
    },
    'dwh': {
        'name': 'Для DWH-проектов дополнительно',
        'items': [
            'Словарь данных',
            'Матрица соответствия источников и целей',
            'Правила очистки данных',
            'Логика преобразования данных',
            'План загрузки данных',
            'Правила управления версиями',
            'Стратегия архивации',
            'Описание процессов ETL',
            'Документированные SQL-запросы',
            'Схемы баз данных'
        ]
    },
    'operations': {
        'name': 'Операционные процедуры',
        'items': [
            'Инструкция по эксплуатации',
            'Процедура восстановления после сбоя',
            'План обслуживания',
            'Алгоритм действий при инцидентах',
            'Порядок внедрения обновлений'
        ]
    },
    'testing': {
        'name': 'Тестирование и качество',
        'items': [
            'Тест-кейсы',
            'Результаты тестирования',
            'Критерии качества данных',
            'Метрики производительности',
            'План мониторинга'
        ]
    },
    'changes': {
        'name': 'Управление изменениями',
        'items': [
            'Журнал изменений',
            'Процедура согласования изменений',
            'Внедренные улучшения',
            'Запланированные доработки'
        ]
    }
} 