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
from config import Config, PROJECT_TYPES
from document_processor import DocumentProcessor
from llm_analyzer import LLMAnalyzer
from pdf_generator import PDFGenerator
import time
import tempfile
from utils import log_with_timestamp

# Отключаем предупреждения SSL только если явно указано в конфигурации
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MattermostBot:
    """Основной класс бота для Mattermost"""
    
    def __init__(self, config: Config):
        self.config = config
        
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
        self.llm_analyzer = LLMAnalyzer(config.llm)
        self.pdf_generator = PDFGenerator()
        
        # Состояния пользователей
        self.user_sessions = {}
        
        # Кэш команд и каналов
        self.teams = []
        self.channels = []
        
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
            self.channels = []
            for team in self.teams:
                team_channels = self.driver.channels.get_channels_for_user(self.bot_user_id, team['id'])
                self.channels.extend(team_channels)
                print(f"📢 В команде '{team['name']}' найдено каналов: {len(team_channels)}")
            
            print(f"✅ Всего каналов для мониторинга: {len(self.channels)}")
            
        except Exception as e:
            print(f"❌ Ошибка при инициализации каналов: {str(e)}")
            raise
    
    async def _listen_for_messages(self):
        """Основной цикл прослушивания сообщений"""
        last_post_time = int(time.time() * 1000)  # Время в миллисекундах
        print(f"👂 Начинаю слушать сообщения с времени: {last_post_time}")
        
        while self.running:
            try:
                # Проверяем новые сообщения в каждом канале
                for channel in self.channels:
                    # Получаем новые посты
                    posts = self.driver.posts.get_posts_for_channel(
                        channel['id'], 
                        params={'since': last_post_time}
                    )
                    
                    new_posts = [p for p in posts.get('posts', {}).values() 
                                if p['user_id'] != self.bot_user_id and p['create_at'] > last_post_time]
                    
                    if new_posts:
                        print(f"📨 Найдено новых сообщений в канале {channel.get('name', channel['id'])}: {len(new_posts)}")
                    
                    for post in new_posts:
                        await self._handle_message(post, channel['id'])
                        last_post_time = max(last_post_time, post['create_at'])
                
                # Небольшая пауза между проверками
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Ошибка в цикле прослушивания: {str(e)}")
                await asyncio.sleep(5)
    
    async def _handle_message(self, post: Dict, channel_id: str):
        """Обработка входящего сообщения"""
        try:
            user_id = post['user_id']
            message = post['message']
            
            log_with_timestamp(f"📨 Получено сообщение: '{message}' от пользователя {user_id}")
            
            # Проверяем, обращается ли сообщение к боту
            is_for_bot = self._is_message_for_bot(message, post)
            log_with_timestamp(f"🤖 Сообщение для бота: {is_for_bot}")
            
            if not is_for_bot:
                return
            
            print(f"✅ Обрабатываем сообщение от пользователя {user_id}")
            
            # Получаем или создаем сессию пользователя
            session = self._get_user_session(user_id)
            
            # Обрабатываем действие пользователя
            await self._process_user_action(user_id, channel_id, message, post, session)
            
        except Exception as e:
            print(f"Ошибка при обработке сообщения: {str(e)}")
            await self._send_error_message(channel_id, "Произошла ошибка при обработке сообщения")
    
    def _is_message_for_bot(self, message: str, post: Dict) -> bool:
        """Проверяет, предназначено ли сообщение для бота"""
        try:
            # Получаем информацию о канале
            channel_info = self.driver.channels.get_channel(post['channel_id'])
            channel_type = channel_info.get('type', '')
            
            print(f"🔍 Проверка сообщения: канал {post['channel_id']}, тип: {channel_type}")
            
            # Прямое сообщение боту
            if channel_type == 'D':  # Direct message
                print("✅ Это прямое сообщение")
                return True
            
            # Получаем имя бота
            bot_user = self.driver.users.get_user('me')
            bot_username = bot_user['username']
            
            print(f"🤖 Имя бота: {bot_username}")
            
            # Проверяем упоминание бота в сообщении
            if f"@{bot_username}" in message:
                print("✅ Найдено упоминание бота")
                return True
            
            # Также проверяем общие команды, которые могут быть адресованы боту
            trigger_words = ['привет', 'начать', 'help', 'старт', 'bot']
            if any(word in message.lower() for word in trigger_words):
                print(f"✅ Найдено ключевое слово: {message}")
                return True
                
            print("❌ Сообщение не для бота")
            return False
            
        except Exception as e:
            print(f"❌ Ошибка при проверке сообщения: {str(e)}")
            # В случае ошибки считаем что сообщение для бота (безопаснее)
            return True
    
    def _get_user_session(self, user_id: str) -> Dict:
        """Получает или создает сессию пользователя"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'state': 'initial',
                'project_types': [],
                'documents': [],
                'waiting_for_documents': False
            }
        return self.user_sessions[user_id]
    
    async def _process_user_action(self, user_id: str, channel_id: str, message: str, 
                                 post: Dict, session: Dict):
        """Обрабатывает действие пользователя в зависимости от состояния"""
        
        state = session['state']
        print(f"🎯 Обрабатываю действие пользователя {user_id}. Состояние: {state}")
        
        if state == 'initial':
            print("🏁 Обработка начального состояния")
            await self._handle_initial_state(user_id, channel_id, message, session)
        elif state == 'waiting_project_types':
            print("📋 Обработка выбора типа проекта")
            await self._handle_project_type_selection(user_id, channel_id, message, session)
        elif state == 'waiting_documents':
            print("📁 Обработка отправки документов")
            await self._handle_document_submission(user_id, channel_id, message, post, session)
        elif state == 'asking_more_documents':
            print("❓ Обработка вопроса о дополнительных документах")
            await self._handle_more_documents_question(user_id, channel_id, message, post, session)
        else:
            print(f"⚠️ Неизвестное состояние: {state}")
            await self._handle_initial_state(user_id, channel_id, message, session)
    
    async def _handle_initial_state(self, user_id: str, channel_id: str, message: str, session: Dict):
        """Обрабатывает начальное состояние"""
        if "начать анализ" in message.lower() or "start" in message.lower():
            await self._ask_project_types(channel_id, session)
        else:
            # Отправляем приветствие только если не команда "начать анализ"
            await self._send_welcome_message(channel_id)
    
    async def _send_welcome_message(self, channel_id: str):
        """Отправляет приветственное сообщение"""
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

**Для начала работы напишите:** `начать анализ` или `start`
        """
        
        await self._send_message(channel_id, message)
    
    async def _ask_project_types(self, channel_id: str, session: Dict):
        """Спрашивает тип проекта"""
        session['state'] = 'waiting_project_types'
        
        message = """
📋 **Какой тип проекта необходимо проанализировать?**

Доступные типы проектов:
"""
        
        for code, name in PROJECT_TYPES.items():
            message += f"• `{code}` - {name}\n"
        
        message += """
**Напишите код типа проекта** (например: `BI` или `BI,DWH` для нескольких типов)
        """
        
        await self._send_message(channel_id, message)
    
    async def _handle_project_type_selection(self, user_id: str, channel_id: str, 
                                           message: str, session: Dict):
        """Обрабатывает выбор типа проекта"""
        # Парсим выбранные типы из сообщения
        selected_types = []
        
        # Убираем лишние символы и разделяем по запятой
        clean_message = message.replace(' ', '').replace(',', ',').upper()
        possible_codes = clean_message.split(',')
        
        for code in possible_codes:
            code = code.strip()
            if code in PROJECT_TYPES:
                selected_types.append(code)
        
        # Также проверяем полные названия
        if not selected_types:
            for code, name in PROJECT_TYPES.items():
                if code.lower() in message.lower() or name.lower() in message.lower():
                    selected_types.append(code)
        
        if not selected_types:
            await self._send_message(channel_id, 
                "❌ Не найдено подходящих типов проектов.\n\n" +
                "**Доступные коды:**\n" + 
                "\n".join([f"• `{code}` - {name}" for code, name in PROJECT_TYPES.items()]) +
                "\n\n**Пример:** `BI` или `BI,DWH`")
            return
        
        # Убираем дубликаты
        selected_types = list(set(selected_types))
        session['project_types'] = selected_types
        session['state'] = 'waiting_documents'
        
        types_text = ", ".join([PROJECT_TYPES[t] for t in selected_types])
        await self._send_message(channel_id, 
            f"✅ **Выбранные типы проектов:** {types_text}\n\n" +
            "📁 **Теперь предоставьте документы или ссылки для анализа:**\n" +
            "• Прикрепите файлы (PDF, DOCX, XLSX, RTF)\n" +
            "• Отправьте ссылки на Confluence\n" +
            "• Можно делать это в одном сообщении\n\n" +
            "💡 **Для Confluence:** используйте полный URL из адресной строки браузера")
    
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
            
            # Спрашиваем, нужно ли добавить еще документы
            session['state'] = 'asking_more_documents'
            
            docs_count = len(session['documents'])
            message_text = f"""
✅ **Получено документов: {docs_count}**

**Что дальше?**
• Напишите `еще` или `добавить` - чтобы добавить еще документы
• Напишите `анализ` или `все документы` - чтобы начать анализ
            """
            
            await self._send_message(channel_id, message_text)
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
        if "добавить" in message.lower() or "еще" in message.lower():
            session['state'] = 'waiting_documents'
            await self._send_message(channel_id, 
                "Отправьте дополнительные документы или ссылки.")
        elif "все документы" in message.lower() or "анализ" in message.lower():
            await self._start_analysis(user_id, channel_id, session)
        else:
            # Проверяем, есть ли новые документы в сообщении
            await self._handle_document_submission(user_id, channel_id, message, post, session)
    
    async def _start_analysis(self, user_id: str, channel_id: str, session: Dict):
        """Запускает анализ документов"""
        try:
            await self._send_message(channel_id, 
                "🔄 Начинаю анализ документов. Это может занять несколько минут...")
            
            # Обрабатываем документы
            processed_docs = self.document_processor.process_documents(session['documents'])
            
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
        
        # Простое сообщение вместо кнопки
        await self._send_message(channel_id, "🚀 **Готовы к новому анализу?** Напишите `начать анализ`")
    
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
            'waiting_for_documents': False
        })
    
    async def _send_message(self, channel_id: str, message: str, attachments: List = None, file_ids: List = None):
        """Отправляет сообщение в канал"""
        try:
            print(f"📤 Попытка отправить сообщение в канал {channel_id}: '{message[:50]}...'")
            
            post_data = {
                'channel_id': channel_id,
                'message': message
            }
            
            if attachments:
                post_data['props'] = {'attachments': attachments}
                print(f"📎 С вложениями: {len(attachments)}")
            
            if file_ids:
                post_data['file_ids'] = file_ids
                print(f"📁 С файлами: {len(file_ids)}")
            
            result = self.driver.posts.create_post(post_data)
            print(f"✅ Сообщение отправлено успешно. ID поста: {result.get('id', 'неизвестно')}")
            
        except Exception as e:
            print(f"❌ Ошибка при отправке сообщения: {str(e)}")
            print(f"   Канал: {channel_id}")
            print(f"   Сообщение: {message[:100]}")
            raise
    
    async def _send_error_message(self, channel_id: str, error_text: str):
        """Отправляет сообщение об ошибке"""
        message = f"❌ **Ошибка:** {error_text}"
        await self._send_message(channel_id, message) 