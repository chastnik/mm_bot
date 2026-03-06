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
    base_url: str
    model: str
    max_tokens: int = 4096
    stream: bool = False
    num_ctx: int = 65536  # 64K токенов контекста для обработки больших документов

@dataclass
class ConfluenceConfig:
    """Настройки подключения к Confluence"""
    username: str
    password: str
    base_url: str

@dataclass
class DatabaseConfig:
    """Настройки БД с параметрами проверки документов"""
    path: str
    
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
            base_url=os.getenv('LLM_BASE_URL', ''),
            model=os.getenv('LLM_MODEL', '')
        )
        
        self.confluence = ConfluenceConfig(
            username=os.getenv('CONFLUENCE_USERNAME', ''),
            password=os.getenv('CONFLUENCE_PASSWORD', ''),
            base_url=os.getenv('CONFLUENCE_BASE_URL', '')
        )

        self.database = DatabaseConfig(
            path=os.getenv('SETTINGS_DB_PATH', 'data/bot_settings.db')
        )
    
    def validate(self) -> bool:
        """Проверка корректности настроек"""
        if not self.mattermost.url or not self.mattermost.token:
            print("Ошибка: не настроены параметры Mattermost")
            return False
            
        if not self.llm.proxy_token:
            print("Ошибка: не настроен токен для корпоративной LLM")
            return False

        if not self.llm.base_url:
            print("Ошибка: не настроен LLM_BASE_URL")
            return False

        if not self.llm.model:
            print("Ошибка: не настроен LLM_MODEL")
            return False
            
        if not self.confluence.username or not self.confluence.password:
            print("Ошибка: не настроены параметры Confluence")
            return False

        if not self.confluence.base_url:
            print("Ошибка: не настроен CONFLUENCE_BASE_URL")
            return False
            
        return True
