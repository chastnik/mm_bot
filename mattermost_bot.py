"""
Основной модуль бота для Mattermost
"""
import asyncio
import json
import base64
import os
import urllib3
import warnings
from typing import Dict, List, Any, Optional
from mattermostdriver import Driver
from config import Config
from document_processor import (
    ConfluenceAuthenticationError,
    ConfluenceCredentialsMissingError,
    DocumentProcessor,
)
from llm_analyzer import LLMAnalyzer
from pdf_generator import PDFGenerator
from settings_db import SettingsDatabase
import time
import tempfile
from utils import log_with_timestamp

# Отключаем предупреждения SSL только если явно указано в конфигурации
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MattermostBot:
    """Основной класс бота для Mattermost"""
    
    def __init__(self, config: Config):
        self.config = config
        self.settings_db = SettingsDatabase(config.database.path)
        self.settings_db.initialize()
        self.project_types = self.settings_db.load_project_types()
        self.artifacts_structure = self.settings_db.load_artifacts_structure()
        if not self.project_types or not self.artifacts_structure:
            raise RuntimeError("Настройки проверки не загружены из БД")
        
        # Инициализация драйвера Mattermost
        # Извлекаем хост из URL без протокола
        mattermost_url = config.mattermost.url
        if mattermost_url.startswith('https://'):
            mattermost_host = mattermost_url[8:]  # Убираем 'https://'
        elif mattermost_url.startswith('http://'):
            mattermost_host = mattermost_url[7:]   # Убираем 'http://'
        else:
            mattermost_host = mattermost_url
        
        # Убираем завершающий слеш если есть
        mattermost_host = mattermost_host.rstrip('/')
        
        # Настройки SSL - по умолчанию включена проверка для безопасности
        ssl_verify = getattr(config.mattermost, 'ssl_verify', True)
        
        self.driver = Driver({
            'url': mattermost_host,
            'login_id': config.mattermost.username,
            'password': config.mattermost.password,
            'token': config.mattermost.token,
            'scheme': 'https',
            'port': 443,
            'verify': ssl_verify,
            'timeout': 30,
            'request_timeout': 30,
        })
        
        # Инициализация компонентов
        self.document_processor = DocumentProcessor(config.confluence)
        self.llm_analyzer = LLMAnalyzer(config.llm, self.artifacts_structure)
        self.pdf_generator = PDFGenerator()
        
        # Состояния пользователей
        self.user_sessions = {}
        
        # Кэш команд и каналов
        self.teams = []
        self.channels = []
        
        # Отслеживание обработанных сообщений
        self.processed_messages = set()
        
        # Флаг для остановки бота
        self.running = False
    
    async def start(self):
        """Запуск бота"""
        try:
            log_with_timestamp(f"🔗 Подключение к Mattermost: {self.config.mattermost.url}")
            log_with_timestamp(f"👤 Пользователь: {self.config.mattermost.username}")
            
            # Проверяем доступность сервера
            try:
                import requests
                url_to_check = self.config.mattermost.url
                if not url_to_check.startswith('http'):
                    url_to_check = f"https://{url_to_check}"
                
                print(f"🔍 Проверка доступности сервера: {url_to_check}")
                
                # Используем те же настройки SSL что и для драйвера
                ssl_verify = getattr(self.config.mattermost, 'ssl_verify', True)
                response = requests.get(url_to_check, timeout=10, verify=ssl_verify)
                print(f"✅ Сервер отвечает. Status: {response.status_code}")
                
                if not ssl_verify:
                    print("⚠️  SSL проверка отключена для данного сервера")
                    
            except Exception as e:
                print(f"⚠️  Проблема с доступностью сервера: {str(e)}")
            
            # Подключение к Mattermost
            self.driver.login()
            print("Бот успешно подключился к Mattermost")
            
            self.running = True
            
            # Получаем информацию о боте
            bot_user = self.driver.users.get_user('me')
            self.bot_user_id = bot_user['id']
            
            print(f"Бот запущен. ID: {self.bot_user_id}")
            
            # Получаем команды и каналы один раз при запуске
            await self._initialize_channels()
            
            # Начинаем слушать сообщения
            await self._listen_for_messages()
            
        except Exception as e:
            print(f"Ошибка при запуске бота: {str(e)}")
            print("💡 Возможные причины:")
            print("   • Неправильный URL Mattermost сервера")
            print("   • Неверные credentials (token/username/password)")
            print("   • Сервер недоступен или имеет проблемы с SSL")
            print("   • Блокировка файрволом")
            raise
    
    async def stop(self):
        """Остановка бота"""
        self.running = False
        try:
            self.driver.logout()
            print("Бот остановлен")
        except Exception as e:
            print(f"Ошибка при остановке бота: {str(e)}")
    
    async def _initialize_channels(self):
        """Инициализация списка команд и каналов"""
        try:
            print("📋 Инициализация команд и каналов...")
            
            # Получаем команды
            self.teams = self.driver.teams.get_user_teams(self.bot_user_id)
            print(f"✅ Найдено команд: {len(self.teams)}")
            
            # Получаем все каналы
            all_channels = []
            for team in self.teams:
                team_channels = self.driver.channels.get_channels_for_user(self.bot_user_id, team['id'])
                all_channels.extend(team_channels)
                print(f"📢 В команде '{team['name']}' найдено каналов: {len(team_channels)}")
            
            # Фильтруем каналы - ТОЛЬКО Direct Messages для безопасности
            self.channels = []
            
            for channel in all_channels:
                channel_type = channel.get('type', '')
                channel_name = channel.get('name', 'Безымянный')
                
                # Оставляем ТОЛЬКО Direct Messages (тип D) для личного общения с ботом
                if channel_type == 'D':
                    self.channels.append(channel)
                    print(f"✅ Добавлен Direct Message канал: '{channel_name}' (ID: {channel['id']})")
                else:
                    print(f"⏭️ Пропускаем канал '{channel_name}' (тип: {channel_type}) - не Direct Message")
            
            print(f"✅ Всего каналов для мониторинга: {len(self.channels)} (из {len(all_channels)} доступных)")
            
            if len(self.channels) == 0:
                print("⚠️ ВНИМАНИЕ: Нет каналов для мониторинга! Бот может не получать сообщения.")
            
        except Exception as e:
            print(f"❌ Ошибка при инициализации каналов: {str(e)}")
            raise
    
    async def _listen_for_messages(self):
        """Основной цикл прослушивания сообщений"""
        last_post_time = int(time.time() * 1000)  # Время в миллисекундах
        last_channel_refresh = 0  # Время последнего обновления каналов
        print(f"👂 Начинаю слушать сообщения с времени: {last_post_time}")
        print(f"🔗 Подключен к каналам: {len(self.channels)}")
        for i, channel in enumerate(self.channels):
            print(f"   {i+1}. {channel.get('name', 'Безымянный')} (ID: {channel['id']})")
        
        while self.running:
            try:
                current_time = int(time.time() * 1000)
                
                # Обновляем список каналов каждые 30 секунд для обнаружения новых пользователей
                if current_time - last_channel_refresh > 30000:  # 30 секунд
                    await self._refresh_channels()
                    last_channel_refresh = current_time
                
                # Собираем все новые сообщения из всех каналов
                all_new_posts = []
                
                # Проверяем новые сообщения в каждом канале
                for channel_idx, channel in enumerate(self.channels):
                    # Получаем новые посты
                    posts = self.driver.posts.get_posts_for_channel(
                        channel['id'], 
                        params={'since': last_post_time}
                    )
                    
                    new_posts = [p for p in posts.get('posts', {}).values() 
                                if p['user_id'] != self.bot_user_id and p['create_at'] > last_post_time]
                    
                    if new_posts:
                        print(f"📨 Канал {channel_idx+1} ({channel.get('name', channel['id'])}): найдено {len(new_posts)} новых сообщений")
                        for post_idx, post in enumerate(new_posts):
                            print(f"   Сообщение {post_idx+1}: ID={post.get('id', 'нет')}, текст='{post.get('message', '')[:50]}', время={post.get('create_at', 0)}")
                            # Добавляем информацию о канале к посту
                            post['_source_channel_id'] = channel['id']
                            all_new_posts.append(post)
                
                # Удаляем дубликаты постов по ID
                unique_posts = {}
                for post in all_new_posts:
                    post_id = post.get('id')
                    if post_id and post_id not in unique_posts:
                        unique_posts[post_id] = post
                    elif post_id:
                        print(f"⚠️ ОБНАРУЖЕН ДУБЛИКАТ: Сообщение {post_id} найдено в нескольких каналах")
                
                # Обрабатываем уникальные сообщения
                for post in unique_posts.values():
                    source_channel_id = post.pop('_source_channel_id', post.get('channel_id', ''))
                    await self._handle_message(post, source_channel_id)
                    last_post_time = max(last_post_time, post['create_at'])
                
                # Небольшая пауза между проверками
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Ошибка в цикле прослушивания: {str(e)}")
                await asyncio.sleep(5)
    
    async def _refresh_channels(self):
        """Обновляет список каналов для обнаружения новых пользователей"""
        try:
            # Получаем все каналы заново
            all_channels = []
            for team in self.teams:
                team_channels = self.driver.channels.get_channels_for_user(self.bot_user_id, team['id'])
                all_channels.extend(team_channels)
            
            # Фильтруем Direct Messages
            new_dm_channels = []
            existing_channel_ids = {ch['id'] for ch in self.channels}
            
            for channel in all_channels:
                if channel.get('type') == 'D' and channel['id'] not in existing_channel_ids:
                    new_dm_channels.append(channel)
                    print(f"🆕 Обнаружен новый Direct Message канал: '{channel.get('name', 'Безымянный')}' (ID: {channel['id']})")
            
            # Добавляем новые каналы в список мониторинга
            if new_dm_channels:
                self.channels.extend(new_dm_channels)
                print(f"✅ Добавлено {len(new_dm_channels)} новых каналов. Всего каналов: {len(self.channels)}")
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении каналов: {str(e)}")
    
    async def _handle_message(self, post: Dict, channel_id: str):
        """Обработка входящего сообщения"""
        try:
            user_id = post['user_id']
            message = post['message']
            post_id = post.get('id', '')
            
            log_with_timestamp(f"🔍 ОТЛАДКА: Обработка сообщения")
            log_with_timestamp(f"   Post ID: {post_id}")
            log_with_timestamp(f"   Channel ID: {channel_id}")
            log_with_timestamp(f"   User ID: {user_id}")
            log_with_timestamp(f"   Сообщение: '{message}'")
            log_with_timestamp(f"   Уже обработанных сообщений: {len(self.processed_messages)}")
            
            # Проверяем, не обрабатывали ли мы уже это сообщение
            if post_id in self.processed_messages:
                log_with_timestamp(f"⚠️ ДУБЛИРОВАНИЕ: Сообщение {post_id} уже было обработано!")
                return
            
            # Добавляем сообщение в список обработанных
            self.processed_messages.add(post_id)
            log_with_timestamp(f"✅ Сообщение {post_id} добавлено в обработанные. Всего: {len(self.processed_messages)}")
            
            # Ограничиваем размер кэша (оставляем последние 1000 сообщений)
            if len(self.processed_messages) > 1000:
                self.processed_messages = set(list(self.processed_messages)[-500:])
                log_with_timestamp(f"🧹 Очистка кэша сообщений. Осталось: {len(self.processed_messages)}")
            
            log_with_timestamp(f"📨 Получено сообщение: '{message}' от пользователя {user_id}")
            
            # Проверяем интерактивные действия (нажатие кнопок)
            if self._is_interactive_action(post):
                log_with_timestamp(f"🔘 Обрабатываем как интерактивную команду")
                await self._handle_interactive_action(post, channel_id)
                return
            
            # Проверяем, обращается ли сообщение к боту
            is_for_bot = self._is_message_for_bot(message, post)
            log_with_timestamp(f"🤖 Сообщение для бота: {is_for_bot}")
            
            if not is_for_bot:
                log_with_timestamp(f"🚫 Сообщение игнорируется")
                return
            
            # Получаем или создаем сессию пользователя
            session = self._get_user_session(user_id)
            log_with_timestamp(f"👤 Состояние пользователя: {session.get('state', 'неизвестно')}")
            
            # Обрабатываем действие пользователя
            log_with_timestamp(f"⚙️ Начинаем обработку действия пользователя")
            await self._process_user_action(user_id, channel_id, message, post, session)
            log_with_timestamp(f"✅ Обработка действия завершена")
            
        except Exception as e:
            print(f"❌ Ошибка при обработке сообщения: {str(e)}")
            import traceback
            traceback.print_exc()
            await self._send_error_message(channel_id, "Произошла ошибка при обработке сообщения")
    
    def _is_interactive_action(self, post: Dict) -> bool:
        """Проверяет, является ли сообщение интерактивным действием"""
        message = post.get('message', '').strip()
        
        # Проверяем только команды с эмодзи (строгое соответствие)
        emoji_commands = ['🚀', '📋', '📁', '🔄', '✅', '➕']
        
        # Команда должна содержать эмодзи или быть точной командой
        has_emoji = any(emoji in message for emoji in emoji_commands)
        
        # Точные интерактивные команды (без конфликта с обычными)
        exact_commands = [
            '🚀 начать анализ', '🚀 новый анализ',
            '➕ добавить документы', '🔄 начать анализ'
        ]
        
        message_lower = message.lower()
        is_exact_command = any(cmd in message_lower for cmd in exact_commands)
        
        # Команды с эмодзи кодов проектов
        is_project_command = '📋' in message and any(code in message.upper() for code in self.project_types.keys())
        
        return has_emoji and (is_exact_command or is_project_command)
    
    async def _handle_interactive_action(self, post: Dict, channel_id: str):
        """Обрабатывает интерактивные действия (эмодзи-команды)"""
        try:
            user_id = post['user_id']
            message = post.get('message', '').strip()
            
            log_with_timestamp(f"🔘 Интерактивная команда: '{message}' от пользователя {user_id}")
            
            session = self._get_user_session(user_id)
            
            # Определяем действие по эмодзи и тексту
            if '🚀' in message and ('начать анализ' in message.lower() or 'новый анализ' in message.lower()):
                if 'новый' in message.lower():
                    await self._handle_restart_analysis_action(user_id, channel_id, session)
                else:
                    await self._handle_start_analysis_action(user_id, channel_id, session)
                    
            elif '📋' in message:
                # Извлекаем коды типов проектов
                selected_types = []
                message_upper = message.upper()
                for code in self.project_types.keys():
                    if code in message_upper:
                        selected_types.append(code)
                
                if selected_types:
                    await self._handle_project_types_selection_action(user_id, channel_id, selected_types, session)
                else:
                    await self._ask_project_types_with_selector(channel_id, session)
                    
            elif '➕' in message and 'добавить' in message.lower():
                await self._handle_add_more_documents_action(user_id, channel_id, session)
                
            elif '🔄' in message and 'анализ' in message.lower():
                await self._start_analysis(user_id, channel_id, session)
                
            else:
                # Неизвестная интерактивная команда - игнорируем
                log_with_timestamp(f"⚠️ Неизвестная интерактивная команда: '{message}'")
                
        except Exception as e:
            print(f"Ошибка при обработке интерактивной команды: {str(e)}")
            await self._send_error_message(channel_id, "Произошла ошибка при обработке команды")
    
    def _is_message_for_bot(self, message: str, post: Dict) -> bool:
        """Проверяет, предназначено ли сообщение для бота
        
        Бот отвечает ТОЛЬКО:
        1. В Direct Messages (все сообщения)
        2. При упоминании @bot_username в каналах (если бы мониторили каналы)
        """
        channel_id = post.get('channel_id', '')
        
        # Определяем тип канала по ID
        for channel in self.channels:
            if channel['id'] == channel_id:
                channel_type = channel.get('type', '')
                
                # В Direct Messages (тип D) ВСЕ сообщения предназначены для бота
                if channel_type == 'D':
                    return True
                break
        
        # В других типах каналов (если бы мониторили) - только при упоминании
        mention_pattern = f"@{self.config.mattermost.username}"
        if mention_pattern in message:
            return True
        
        # По умолчанию игнорируем (но сейчас мониторим только Direct Messages)
        return False
    
    def _get_user_session(self, user_id: str) -> Dict:
        """Получает или создает сессию пользователя"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'state': 'initial',
                'project_types': [],
                'documents': [],
                'waiting_for_documents': False,
                'pending_confluence_username': None,
            }
        return self.user_sessions[user_id]
    
    async def _process_user_action(self, user_id: str, channel_id: str, message: str, 
                                 post: Dict, session: Dict):
        """Обрабатывает действие пользователя в зависимости от состояния"""
        message_lower = message.lower().strip()

        # Глобальные команды управления credentials Confluence
        if await self._handle_confluence_credentials_commands(user_id, channel_id, message, session):
            return

        # Обработка состояний ввода credentials Confluence
        if await self._handle_confluence_credentials_states(user_id, channel_id, message, session):
            return
        
        # Проверяем команды сброса состояния (глобальные команды)
        reset_commands = ['начать анализ', 'start', 'привет', 'hello', 'помощь', 'help', '🚀 начать анализ', '🚀 новый анализ']
        if any(cmd in message_lower for cmd in reset_commands):
            # При стартовых командах всегда сбрасываем состояние
            self._reset_session(session)
            if 'начать анализ' in message_lower or '🚀' in message_lower:
                # Сразу переходим к выбору типов проектов
                await self._ask_project_types_with_selector(channel_id, session)
                return
            else:
                # Для команд привет/help отправляем приветственное сообщение и завершаем
                await self._send_welcome_message(channel_id)
                return
        
        # Команды для состояния asking_more_documents
        if session.get('state') == 'asking_more_documents':
            if 'анализ' in message_lower or '🔄' in message_lower:
                await self._start_analysis(user_id, channel_id, session)
                return
            elif 'добавить' in message_lower or '➕' in message_lower:
                await self._handle_add_more_documents_action(user_id, channel_id, session)
                return
        
        state = session.get('state', 'initial')
        
        if state == 'initial':
            await self._handle_initial_state(user_id, channel_id, message, session)
        elif state == 'waiting_project_types':
            await self._handle_project_type_selection(user_id, channel_id, message, session)
        elif state == 'waiting_documents':
            await self._handle_document_submission(user_id, channel_id, message, post, session)
        elif state == 'asking_more_documents':
            await self._handle_more_documents_question(user_id, channel_id, message, post, session)
        else:
            # Неизвестное состояние - сбрасываем
            self._reset_session(session)
            await self._handle_initial_state(user_id, channel_id, message, session)

    async def _handle_confluence_credentials_commands(
        self,
        user_id: str,
        channel_id: str,
        message: str,
        session: Dict[str, Any],
    ) -> bool:
        message_lower = message.lower().strip()
        has_setup_command = "настроить confluence" in message_lower or "confluence логин" in message_lower
        has_change_login_command = (
            "сменить логин confluence" in message_lower
            or "изменить логин confluence" in message_lower
        )
        has_change_password_command = (
            "сменить пароль confluence" in message_lower
            or "изменить пароль confluence" in message_lower
        )

        if has_setup_command:
            session["state"] = "waiting_confluence_username_setup"
            await self._send_message(
                channel_id,
                "🔐 Введите логин Confluence (обычно корпоративный username или email).",
            )
            return True

        if has_change_login_command:
            existing = self.settings_db.get_user_confluence_credentials(user_id)
            if not existing:
                await self._send_message(
                    channel_id,
                    "⚠️ Учетные данные Confluence еще не настроены.\n"
                    "Сначала выполните `настроить confluence`.",
                )
                return True
            session["state"] = "waiting_confluence_username_change"
            await self._send_message(channel_id, "👤 Введите новый логин Confluence.")
            return True

        if has_change_password_command:
            existing = self.settings_db.get_user_confluence_credentials(user_id)
            if not existing:
                await self._send_message(
                    channel_id,
                    "⚠️ Учетные данные Confluence еще не настроены.\n"
                    "Сначала выполните `настроить confluence`.",
                )
                return True
            session["state"] = "waiting_confluence_password_change"
            await self._send_message(channel_id, "🔑 Введите новый пароль (или API token) Confluence.")
            return True

        return False

    async def _handle_confluence_credentials_states(
        self,
        user_id: str,
        channel_id: str,
        message: str,
        session: Dict[str, Any],
    ) -> bool:
        state = session.get("state")
        value = message.strip()

        if state == "waiting_confluence_username_setup":
            if not value:
                await self._send_message(channel_id, "❌ Логин не должен быть пустым. Введите логин Confluence.")
                return True
            session["pending_confluence_username"] = value
            session["state"] = "waiting_confluence_password_setup"
            await self._send_message(channel_id, "🔑 Введите пароль (или API token) Confluence.")
            return True

        if state == "waiting_confluence_password_setup":
            username = session.get("pending_confluence_username")
            if not username:
                session["state"] = "waiting_confluence_username_setup"
                await self._send_message(channel_id, "⚠️ Не найден введенный логин. Введите логин Confluence заново.")
                return True
            if not value:
                await self._send_message(channel_id, "❌ Пароль не должен быть пустым. Введите пароль Confluence.")
                return True

            self.settings_db.set_user_confluence_credentials(
                user_id=user_id,
                username=username.strip(),
                password=value,
            )
            session["pending_confluence_username"] = None
            session["state"] = "initial"
            await self._send_message(
                channel_id,
                "✅ Учетные данные Confluence сохранены. "
                "При следующих анализах пароль повторно запрашиваться не будет.",
            )
            return True

        if state == "waiting_confluence_username_change":
            if not value:
                await self._send_message(channel_id, "❌ Логин не должен быть пустым. Введите новый логин.")
                return True
            self.settings_db.set_user_confluence_credentials(user_id=user_id, username=value.strip())
            session["state"] = "initial"
            await self._send_message(channel_id, "✅ Логин Confluence обновлен.")
            return True

        if state == "waiting_confluence_password_change":
            if not value:
                await self._send_message(channel_id, "❌ Пароль не должен быть пустым. Введите новый пароль.")
                return True
            self.settings_db.set_user_confluence_credentials(user_id=user_id, password=value)
            session["state"] = "initial"
            await self._send_message(channel_id, "✅ Пароль Confluence обновлен.")
            return True

        return False
    
    async def _handle_initial_state(self, user_id: str, channel_id: str, message: str, session: Dict):
        """Обрабатывает начальное состояние"""
        await self._send_welcome_message(channel_id)
    
    async def _send_welcome_message(self, channel_id: str):
        """Отправляет приветственное сообщение с интерактивными кнопками"""
        message = """
🤖 **Привет! Я бот для анализа документации ИТ проектов.**

**Я умею:**
• Анализировать документы (PDF, DOCX, XLSX, RTF)
• Обрабатывать ссылки на Confluence
• Находить артефакты проекта с помощью ИИ
• Генерировать отчеты в формате PDF

**💡 Совет по Confluence:**
Всегда используйте **полный URL** из адресной строки браузера:
• ✅ `https://confluence.1solution.ru/spaces/PROJECT/pages/123456/PageName`
• ✅ `https://confluence.1solution.ru/x/ABC123`
        """
        
        # Создаём красивую карточку с инструкциями
        attachments = [{
            "fallback": "Начать анализ - напишите: начать анализ",
            "color": "#36a64f", 
            "title": "🚀 Готовы начать анализ?",
            "text": "Напишите команду для начала работы с ботом",
            "fields": [
                {
                    "title": "Доступные команды:",
                    "value": "• **`начать анализ`** - запустить новый анализ\n• **`настроить confluence`** - сохранить логин/пароль\n• **`изменить логин confluence`** - сменить логин\n• **`изменить пароль confluence`** - сменить пароль\n• **`помощь`** - показать справку\n• **`привет`** - вернуться в главное меню",
                    "short": False
                }
            ]
        }]
        
        await self._send_message(channel_id, message, attachments=attachments)
    
    async def _handle_start_analysis_action(self, user_id: str, channel_id: str, session: Dict):
        """Обрабатывает нажатие кнопки 'Начать анализ'"""
        await self._ask_project_types_with_selector(channel_id, session)
    
    async def _ask_project_types_with_selector(self, channel_id: str, session: Dict):
        """Спрашивает тип проекта с помощью селектора"""
        session['state'] = 'waiting_project_types'
        
        message = """
📋 **Какой тип проекта необходимо проанализировать?**

Выберите один или несколько типов проектов нажав на кнопки ниже:
        """
        
        # Создаём красивую карточку с типами проектов
        project_types_text = ""
        for code, name in self.project_types.items():
            project_types_text += f"• **`{code}`** - {name}\n"
        
        attachments = [{
            "fallback": "Выбор типа проекта - напишите код типа проекта",
            "color": "#439fe0",
            "title": "📋 Выберите тип проекта",
            "text": "Напишите код одного или нескольких типов проектов",
            "fields": [
                {
                    "title": "Доступные типы:",
                    "value": project_types_text,
                    "short": False
                },
                {
                    "title": "Примеры команд:",
                    "value": "• **`BI`** - выбрать один тип\n• **`BI,DWH`** - выбрать несколько типов\n• **`📋 BI`** - можно с эмодзи",
                    "short": False
                }
            ]
        }]
        
        await self._send_message(channel_id, message, attachments=attachments)
    
    async def _handle_project_types_selection_action(self, user_id: str, channel_id: str, 
                                                    selected_types: List[str], session: Dict):
        """Обрабатывает выбор типов проектов через селектор"""
        if not selected_types:
            await self._send_message(channel_id, 
                "❌ Типы проектов не выбраны. Пожалуйста, выберите хотя бы один тип.")
            return
        
        session['project_types'] = selected_types
        session['state'] = 'waiting_documents'
        
        types_text = ", ".join([self.project_types.get(t, t) for t in selected_types])
        
        message = f"""
✅ **Выбранные типы проектов:** {types_text}

📁 **Теперь предоставьте документы или ссылки для анализа:**
• Прикрепите файлы (PDF, DOCX, XLSX, RTF)
• Отправьте ссылки на Confluence
• Можно делать это в одном сообщении

💡 **Для Confluence:** используйте полный URL из адресной строки браузера
        """
        
        await self._send_message(channel_id, message)
    
    async def _ask_project_types(self, channel_id: str, session: Dict):
        """Спрашивает тип проекта (устаревший метод, оставлен для совместимости)"""
        await self._ask_project_types_with_selector(channel_id, session)
    
    async def _handle_project_type_selection(self, user_id: str, channel_id: str, 
                                           message: str, session: Dict):
        """Обрабатывает выбор типа проекта (устаревший метод для текстового ввода)"""
        # Парсим выбранные типы из сообщения
        selected_types = []
        
        # Убираем лишние символы и разделяем по запятой
        clean_message = message.replace(' ', '').replace(',', ',').upper()
        possible_codes = clean_message.split(',')
        
        for code in possible_codes:
            code = code.strip()
            if code in self.project_types:
                selected_types.append(code)
        
        # Также проверяем полные названия
        if not selected_types:
            for code, name in self.project_types.items():
                if code.lower() in message.lower() or name.lower() in message.lower():
                    selected_types.append(code)
        
        if not selected_types:
            await self._send_message(channel_id, 
                "❌ Не найдено подходящих типов проектов.\n\n" +
                "**Доступные коды:**\n" + 
                "\n".join([f"• `{code}` - {name}" for code, name in self.project_types.items()]) +
                "\n\n**Пример:** `BI` или `BI,DWH`")
            return
        
        # Убираем дубликаты
        selected_types = list(set(selected_types))
        await self._handle_project_types_selection_action(user_id, channel_id, selected_types, session)
    
    async def _handle_add_more_documents_action(self, user_id: str, channel_id: str, session: Dict):
        """Обрабатывает нажатие кнопки 'Добавить еще документы'"""
        session['state'] = 'waiting_documents'
        await self._send_message(channel_id, 
            "📁 **Отправьте дополнительные документы или ссылки:**\n\n"
            "• Прикрепите файлы (PDF, DOCX, XLSX, RTF)\n"
            "• Отправьте ссылки на Confluence\n"
            "• Можно делать это в одном сообщении")
    
    async def _handle_restart_analysis_action(self, user_id: str, channel_id: str, session: Dict):
        """Обрабатывает нажатие кнопки 'Новый анализ'"""
        self._reset_session(session)
        await self._send_welcome_message(channel_id)
    
    async def _handle_document_submission(self, user_id: str, channel_id: str, 
                                        message: str, post: Dict, session: Dict):
        """Обрабатывает отправку документов"""
        documents = []
        
        # Отладка: проверяем структуру поста
        log_with_timestamp(f"🔍 Отладка поста:")
        log_with_timestamp(f"   Сообщение: '{message}'")
        log_with_timestamp(f"   File IDs в посте: {post.get('file_ids', [])}")
        log_with_timestamp(f"   Метаданные поста: {post.get('metadata', {})}")
        log_with_timestamp(f"   Вложения (attachments): {post.get('attachments', [])}")
        
        # Обрабатываем файлы
        file_ids = post.get('file_ids', [])
        file_metadata = post.get('metadata', {}).get('files', [])
        
        if file_ids:
            print(f"📁 Найдены file_ids: {file_ids}")
            for file_id in file_ids:
                try:
                    # Используем метаданные из поста, если доступны
                    file_info = None
                    for metadata in file_metadata:
                        if metadata.get('id') == file_id:
                            file_info = metadata
                            break
                    
                    # Если метаданных нет, получаем их через API
                    if not file_info:
                        file_info = self.driver.files.get_file_metadata(file_id)
                    
                    # Скачиваем файл - получаем Response объект
                    file_response = self.driver.files.get_file(file_id)
                    file_data = file_response.content  # Извлекаем bytes данные
                    
                    print(f"✅ Получен файл: {file_info.get('name', 'Неизвестно')} ({file_info.get('size', 0)} байт)")
                    
                    documents.append({
                        'type': 'file',
                        'name': file_info.get('name', f'file_{file_id}'),
                        'data': file_data,
                        'metadata': file_info
                    })
                except Exception as e:
                    print(f"❌ Ошибка при получении файла {file_id}: {str(e)}")
        
        # Обрабатываем ссылки на Confluence
        confluence_urls = self._extract_confluence_urls(message)
        for url in confluence_urls:
            documents.append({
                'type': 'confluence',
                'url': url
            })
        
        if documents:
            session['documents'].extend(documents)
            
            # Спрашиваем, нужно ли добавить еще документы с интерактивными кнопками
            session['state'] = 'asking_more_documents'
            
            docs_count = len(session['documents'])
            message_text = f"✅ **Получено документов: {docs_count}**\n\n**Что дальше?**"
            
            # Создаём карточку для выбора действия
            attachments = [{
                "fallback": "Выбор действия - напишите: анализ или добавить",
                "color": "#36a64f",
                "title": "🎯 Что дальше?",
                "text": "Выберите следующее действие:",
                "fields": [
                    {
                        "title": "Доступные команды:",
                        "value": "• **`анализ`** или **`🔄 начать анализ`** - анализировать все документы\n• **`добавить`** или **`➕ добавить документы`** - добавить еще файлы",
                        "short": False
                    }
                ]
            }]
            
            await self._send_message(channel_id, message_text, attachments=attachments)
        else:
            print(f"❌ Документы не найдены!")
            print(f"   Файлы: {len(file_ids)} (IDs: {file_ids})")
            print(f"   Confluence URLs: {len(confluence_urls)} (URLs: {confluence_urls})")
            
            confluence_help = """
Документы не обнаружены. 

**Как правильно указать документы:**

📁 **Файлы:** Прикрепите файлы к сообщению (PDF, DOCX, XLSX, RTF, TXT)

🔗 **Confluence страницы:** 
• Скопируйте **полный URL** из адресной строки браузера
• Например: `https://confluence.1solution.ru/spaces/PROJECT/pages/123456/PageName`
• Или короткий URL: `https://confluence.1solution.ru/x/ABC123`

❌ **НЕ используйте:**
• Неполные ссылки или фрагменты URL
• Внутренние ссылки из Confluence
• Ссылки без протокола (http/https)

**Попробуйте снова!**
            """
            await self._send_message(channel_id, confluence_help.strip())
    
    async def _handle_more_documents_question(self, user_id: str, channel_id: str, 
                                            message: str, post: Dict, session: Dict):
        """Обрабатывает вопрос о дополнительных документах"""
        message_lower = message.lower()
        
        # Явные команды для добавления документов
        if "добавить" in message_lower or "еще" in message_lower or "➕" in message:
            session['state'] = 'waiting_documents'
            await self._send_message(channel_id, 
                "📁 **Отправьте дополнительные документы или ссылки:**\n\n"
                "• Прикрепите файлы (PDF, DOCX, XLSX, RTF)\n"
                "• Отправьте ссылки на Confluence\n"
                "• Можно делать это в одном сообщении")
            return
        
        # Явные команды для начала анализа
        if ("все документы" in message_lower or "анализ" in message_lower or 
            "🔄" in message or "готово" in message_lower or "старт" in message_lower):
            await self._start_analysis(user_id, channel_id, session)
            return
        
        # Проверяем, есть ли файлы или confluence ссылки в сообщении
        has_files = bool(post.get('file_ids', []))
        has_confluence = bool(self._extract_confluence_urls(message))
        
        if has_files or has_confluence:
            # Есть документы - обрабатываем их
            await self._handle_document_submission(user_id, channel_id, message, post, session)
        else:
            # Нет документов и нет явных команд - игнорируем сообщение
            # Можно отправить подсказку только если сообщение выглядит как попытка взаимодействия
            if (len(message.strip()) > 2 and 
                any(word in message_lower for word in ['что', 'как', 'помощь', 'help', '?'])):
                await self._send_message(channel_id, 
                    "💡 **Что дальше?**\n\n"
                    "• `➕ Добавить документы` - добавить еще файлы\n"
                    "• `🔄 Начать анализ` - анализировать все документы")
            # Короткие сообщения (как "1") игнорируем полностью
    
    async def _start_analysis(self, user_id: str, channel_id: str, session: Dict):
        """Запускает анализ документов"""
        try:
            await self._send_message(channel_id, 
                "🔄 Начинаю анализ документов. Это может занять несколько минут...")

            has_confluence_documents = any(
                document.get("type") == "confluence" for document in session.get("documents", [])
            )
            confluence_credentials = self.settings_db.get_user_confluence_credentials(user_id)
            if has_confluence_documents and not confluence_credentials:
                session["state"] = "asking_more_documents"
                await self._send_message(
                    channel_id,
                    "⚠️ Для чтения Confluence нужно один раз настроить личные credentials.\n"
                    "Введите команду `настроить confluence`, укажите логин и пароль, "
                    "затем снова отправьте `анализ`.",
                )
                return
            
            # Обрабатываем документы
            processed_docs = self.document_processor.process_documents(
                session['documents'],
                confluence_credentials=confluence_credentials,
            )
            
            if not processed_docs:
                await self._send_message(channel_id, 
                    "❌ Не удалось обработать ни один документ. Проверьте формат файлов и ссылки.")
                self._reset_session(session)
                return
            
            await self._send_message(channel_id, 
                f"✅ Обработано документов: {len(processed_docs)}\n🤖 Анализирую с помощью ИИ...")
            
            # Анализируем с помощью корпоративной LLM
            analysis_result = self.llm_analyzer.analyze_documents(
                processed_docs, 
                session['project_types']
            )
            
            if analysis_result.get('error'):
                await self._send_message(channel_id, 
                    "❌ Ошибка при анализе документов с помощью корпоративной LLM. Попробуйте позже.")
                self._reset_session(session)
                return
            
            await self._send_message(channel_id, 
                "✅ Анализ завершен! 📄 Генерирую PDF отчет...")
            
            # Генерируем PDF отчет
            pdf_data = self.pdf_generator.generate_report(
                analysis_result,
                session['project_types'],
                processed_docs
            )
            
            # Отправляем результат
            await self._send_analysis_result(channel_id, analysis_result, pdf_data)
            
            # Сбрасываем сессию для нового анализа
            self._reset_session(session)
            
        except Exception as e:
            if isinstance(e, ConfluenceCredentialsMissingError):
                session["state"] = "asking_more_documents"
                await self._send_message(
                    channel_id,
                    "⚠️ Не найдены личные credentials Confluence.\n"
                    "Выполните `настроить confluence`, затем повторите `анализ`.",
                )
                return

            if isinstance(e, ConfluenceAuthenticationError):
                session["state"] = "asking_more_documents"
                await self._send_message(
                    channel_id,
                    "❌ Не удалось войти в Confluence с сохраненным паролем (выполнена 1 попытка).\n"
                    "Скорее всего пароль/токен изменился. Обновите его командой "
                    "`изменить пароль confluence`, затем повторите `анализ`.",
                )
                return

            print(f"Ошибка при анализе: {str(e)}")
            await self._send_error_message(channel_id, 
                "Произошла ошибка при анализе документов. Попробуйте еще раз.")
            self._reset_session(session)
    
    async def _send_analysis_result(self, channel_id: str, analysis_result: Dict, pdf_data: bytes):
        """Отправляет результат анализа"""
        summary = analysis_result.get('summary', {})
        
        # Формируем список всех артефактов с их статусами
        artifacts_list = []
        
        # Найденные артефакты
        for artifact in analysis_result.get('found_artifacts', []):
            artifacts_list.append(f"✅ {artifact.get('name', 'Без названия')}")
        
        # Частично найденные артефакты
        for artifact in analysis_result.get('partially_found_artifacts', []):
            artifacts_list.append(f"🟡 {artifact.get('name', 'Без названия')}")
        
        # Не найденные артефакты
        for artifact in analysis_result.get('not_found_artifacts', []):
            artifacts_list.append(f"❌ {artifact.get('name', 'Без названия')}")
        
        # Ограничиваем количество артефактов в сообщении для читаемости
        max_artifacts_in_message = 15
        if len(artifacts_list) > max_artifacts_in_message:
            shown_artifacts = artifacts_list[:max_artifacts_in_message]
            remaining_count = len(artifacts_list) - max_artifacts_in_message
            artifacts_text = '\n'.join(shown_artifacts) + f"\n... и еще {remaining_count} артефактов"
        else:
            artifacts_text = '\n'.join(artifacts_list)
        
        result_text = f"""
📊 **Результат анализа документов**

**Сводка:**
• Всего артефактов: {summary.get('total_artifacts', 0)}
• Найдено: {summary.get('found_count', 0)}
• Найдено частично: {summary.get('partially_found_count', 0)}
• Не найдено: {summary.get('not_found_count', 0)}

**Анализируемые артефакты:**
{artifacts_text}

**Обозначения:**
✅ - Найден полностью
🟡 - Найден частично  
❌ - Не найден

**Детальный отчет с источниками прикреплен в PDF файле.**

**Для нового анализа напишите:** `начать анализ` или `привет`
        """
        
        # Сохраняем PDF во временный файл
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(pdf_data)
            temp_file_path = temp_file.name
        
        try:
            # Загружаем файл в Mattermost
            file_response = self.driver.files.upload_file(
                channel_id=channel_id,
                files={'files': (f'analysis_report_{int(time.time())}.pdf', open(temp_file_path, 'rb'))}
            )
            
            file_id = file_response['file_infos'][0]['id']
            
            # Отправляем сообщение с прикрепленным файлом
            await self._send_message(channel_id, result_text, file_ids=[file_id])
            
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        
        # Интерактивная карточка для нового анализа
        restart_message = ""
        
        restart_attachments = [{
            "fallback": "Новый анализ - напишите: начать анализ",
            "color": "#ff9500",
            "title": "🚀 Готовы к новому анализу?",
            "text": "Напишите команду для начала нового анализа:",
            "fields": [
                {
                    "title": "Команды для нового анализа:",
                    "value": "• **`начать анализ`** - запустить новый анализ\n• **`привет`** - вернуться в главное меню\n• **`🚀 новый анализ`** - можно с эмодзи",
                    "short": False
                }
            ]
        }]
         
        await self._send_message(channel_id, restart_message, attachments=restart_attachments)
    
    def _extract_confluence_urls(self, message: str) -> List[str]:
        """Извлекает ссылки на Confluence из сообщения"""
        import re
        
        # Паттерн для поиска ссылок на Confluence
        confluence_pattern = r'https?://[^\s]*confluence[^\s]*'
        urls = re.findall(confluence_pattern, message, re.IGNORECASE)
        
        return urls
    
    def _reset_session(self, session: Dict):
        """Сбрасывает сессию пользователя"""
        session.update({
            'state': 'initial',
            'project_types': [],
            'documents': [],
            'waiting_for_documents': False,
            'pending_confluence_username': None,
        })
    
    async def _send_message(self, channel_id: str, message: str, attachments: Optional[List[Dict[str, Any]]] = None, file_ids: Optional[List[str]] = None):
        """Отправляет сообщение в канал"""
        try:
            log_with_timestamp(f"📤 ОТПРАВКА: Готовим сообщение в канал {channel_id}")
            log_with_timestamp(f"   Длина сообщения: {len(message)} символов")
            log_with_timestamp(f"   Начало сообщения: '{message[:100]}...'")
            
            post_data: Dict[str, Any] = {
                'channel_id': channel_id,
                'message': message
            }
            
            if attachments:
                post_data['props'] = {'attachments': attachments}
                log_with_timestamp(f"📎 С вложениями: {len(attachments)}")
            
            if file_ids:
                post_data['file_ids'] = file_ids
                log_with_timestamp(f"📁 С файлами: {len(file_ids)}")
            
            log_with_timestamp(f"🚀 Отправляем сообщение через API...")
            result = self.driver.posts.create_post(post_data)
            post_id = result.get('id', 'неизвестно')
            log_with_timestamp(f"✅ Сообщение отправлено успешно. ID поста: {post_id}")
            
        except Exception as e:
            log_with_timestamp(f"❌ Ошибка при отправке сообщения: {str(e)}")
            log_with_timestamp(f"   Канал: {channel_id}")
            log_with_timestamp(f"   Сообщение: {message[:100]}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _send_error_message(self, channel_id: str, error_text: str):
        """Отправляет сообщение об ошибке"""
        message = f"❌ **Ошибка:** {error_text}"
        await self._send_message(channel_id, message) 