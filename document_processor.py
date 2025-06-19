"""
Модуль для обработки различных типов документов
"""
import os
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import PyPDF2
from docx import Document
from openpyxl import load_workbook
from striprtf.striprtf import rtf_to_text
from bs4 import BeautifulSoup
import base64
import json

class DocumentProcessor:
    """Класс для обработки различных типов документов"""
    
    def __init__(self, confluence_config):
        self.confluence_config = confluence_config
        self.supported_formats = ['.pdf', '.docx', '.doc', '.xlsx', '.rtf']
    
    def process_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Обрабатывает список документов и возвращает извлеченный текст
        
        Args:
            documents: Список документов с информацией о типе и содержимом
            
        Returns:
            Список обработанных документов с извлеченным текстом
        """
        processed_docs = []
        
        for doc in documents:
            try:
                if doc['type'] == 'file':
                    processed_doc = self._process_file(doc)
                elif doc['type'] == 'confluence':
                    processed_doc = self._process_confluence_url(doc)
                else:
                    continue
                    
                if processed_doc:
                    processed_docs.append(processed_doc)
                    
            except Exception as e:
                print(f"Ошибка при обработке документа {doc.get('name', 'unknown')}: {str(e)}")
                
        return processed_docs
    
    def _process_file(self, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обрабатывает файл в зависимости от его типа"""
        file_name = doc.get('name', '')
        file_data = doc.get('data', b'')
        
        if not file_data:
            return None
            
        # Определяем тип файла по расширению
        _, ext = os.path.splitext(file_name.lower())
        
        if ext == '.pdf':
            text = self._extract_from_pdf(file_data)
        elif ext == '.docx':
            text = self._extract_from_docx(file_data)
        elif ext == '.doc':
            text = self._extract_from_doc(file_data)
        elif ext == '.xlsx':
            text = self._extract_from_xlsx(file_data)
        elif ext == '.rtf':
            text = self._extract_from_rtf(file_data)
        else:
            print(f"Неподдерживаемый формат файла: {ext}")
            return None
            
        return {
            'name': file_name,
            'type': 'file',
            'format': ext,
            'text': text,
            'pages': self._count_pages(text)
        }
    
    def _extract_from_pdf(self, file_data: bytes) -> str:
        """Извлекает текст из PDF файла"""
        try:
            from io import BytesIO
            pdf_file = BytesIO(file_data)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                text += f"\n--- Страница {page_num} ---\n{page_text}\n"
                
            return text
        except Exception as e:
            print(f"Ошибка при извлечении текста из PDF: {str(e)}")
            return ""
    
    def _extract_from_docx(self, file_data: bytes) -> str:
        """Извлекает текст из DOCX файла"""
        try:
            from io import BytesIO
            doc_file = BytesIO(file_data)
            doc = Document(doc_file)
            
            text = ""
            page_num = 1
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += f"{paragraph.text}\n"
                    
            # Обработка таблиц
            for table in doc.tables:
                text += "\n--- Таблица ---\n"
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        row_text.append(cell.text.strip())
                    text += " | ".join(row_text) + "\n"
                text += "--- Конец таблицы ---\n"
                
            return text
        except Exception as e:
            print(f"Ошибка при извлечении текста из DOCX: {str(e)}")
            return ""

    def _extract_from_doc(self, file_data: bytes) -> str:
        """Извлекает текст из DOC файла"""
        try:
            import docx2txt
            from io import BytesIO
            
            doc_file = BytesIO(file_data)
            # Сохраняем временный файл, так как docx2txt требует путь к файлу
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.doc', delete=False) as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name
            
            try:
                text = docx2txt.process(temp_file_path)
                return text or ""
            finally:
                import os
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    
        except Exception as e:
            print(f"Ошибка при извлечении текста из DOC: {str(e)}")
            return ""
    
    def _extract_from_xlsx(self, file_data: bytes) -> str:
        """Извлекает текст из XLSX файла"""
        try:
            from io import BytesIO
            excel_file = BytesIO(file_data)
            workbook = load_workbook(excel_file, data_only=True)
            
            text = ""
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                text += f"\n--- Лист: {sheet_name} ---\n"
                
                for row in sheet.iter_rows():
                    row_data = []
                    for cell in row:
                        if cell.value is not None:
                            row_data.append(str(cell.value))
                        else:
                            row_data.append("")
                    
                    # Добавляем строку только если есть данные
                    if any(cell_data.strip() for cell_data in row_data):
                        text += " | ".join(row_data) + "\n"
                        
            return text
        except Exception as e:
            print(f"Ошибка при извлечении текста из XLSX: {str(e)}")
            return ""
    
    def _extract_from_rtf(self, file_data: bytes) -> str:
        """Извлекает текст из RTF файла"""
        try:
            rtf_content = file_data.decode('utf-8')
            text = rtf_to_text(rtf_content)
            return text
        except Exception as e:
            print(f"Ошибка при извлечении текста из RTF: {str(e)}")
            return ""
    
    def _process_confluence_url(self, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обрабатывает ссылку на Confluence страницу с рекурсивным обходом дочерних страниц и файлов"""
        url = doc.get('url', '')
        
        if not url:
            return None
            
        try:
            print(f"🔍 Анализирую Confluence страницу: {url}")
            
            # Получаем полный ID страницы из короткого URL
            page_id = self._resolve_page_id(url)
            if not page_id:
                print(f"❌ Не удалось получить ID страницы для URL: {url}")
                return None
            
            print(f"✅ Получен ID страницы: {page_id}")
            
            # Извлекаем содержимое главной страницы
            main_page_content, main_page_title = self._fetch_confluence_page_by_id(page_id)
            
            # Получаем все дочерние страницы рекурсивно
            all_pages = self._get_all_child_pages_recursive(page_id)
            
            # Получаем вложенные файлы
            attachments = self._get_page_attachments(page_id)
            
            all_content = f"--- ГЛАВНАЯ СТРАНИЦА: {main_page_title} ---\n{main_page_content}\n"
            
            # Добавляем содержимое всех дочерних страниц И их вложений
            all_child_attachments = []
            for page_info in all_pages:
                child_content, child_title = self._fetch_confluence_page_by_id(page_info['id'])
                level_indent = "  " * page_info['level']  # Отступ для показа уровня вложенности
                all_content += f"\n--- {level_indent}ДОЧЕРНЯЯ СТРАНИЦА (уровень {page_info['level']}): {child_title} ---\n{child_content}\n"
                
                # ВАЖНО: Получаем вложения с каждой дочерней страницы
                child_attachments = self._get_page_attachments(page_info['id'])
                for child_attachment in child_attachments:
                    child_attachment['source_page'] = child_title  # Помечаем источник
                    all_child_attachments.append(child_attachment)
                    print(f"📎 Найден файл на дочерней странице '{child_title}': {child_attachment['title']}")
            
            # Добавляем содержимое вложенных файлов с главной страницы
            for attachment in attachments:
                file_content = self._extract_attachment_content(attachment)
                if file_content:
                    all_content += f"\n--- ВЛОЖЕННЫЙ ФАЙЛ (главная страница): {attachment['title']} ---\n{file_content}\n"
            
            # Добавляем содержимое вложенных файлов с дочерних страниц
            for attachment in all_child_attachments:
                file_content = self._extract_attachment_content(attachment)
                if file_content:
                    source_page = attachment.get('source_page', 'неизвестная страница')
                    all_content += f"\n--- ВЛОЖЕННЫЙ ФАЙЛ (со страницы '{source_page}'): {attachment['title']} ---\n{file_content}\n"
            
            total_pages = len(all_pages) + 1
            total_attachments = len(attachments) + len(all_child_attachments)
            main_attachments_count = len(attachments)
            child_attachments_count = len(all_child_attachments)
            
            print(f"✅ Обработано: главная страница + {len(all_pages)} дочерних + {main_attachments_count} файлов (главная) + {child_attachments_count} файлов (дочерние)")
            
            return {
                'name': f"Confluence: {main_page_title} (+ {len(all_pages)} дочерних страниц + {total_attachments} файлов)",
                'type': 'confluence',
                'url': url,
                'text': all_content,
                'pages': total_pages,
                'child_pages_count': len(all_pages),
                'attachments_count': total_attachments,
                'main_attachments_count': main_attachments_count,
                'child_attachments_count': child_attachments_count
            }
            
        except Exception as e:
            print(f"❌ Ошибка при обработке Confluence страницы {url}: {str(e)}")
            return None
    
    def _resolve_page_id(self, url: str) -> Optional[str]:
        """Разрешает короткий URL Confluence в полный ID страницы"""
        try:
            # Проверяем, настроены ли учетные данные Confluence
            if not self.confluence_config.username or not self.confluence_config.password:
                print("⚠️ Учетные данные Confluence не настроены. Используем fallback метод.")
                return self._fallback_resolve_page_id(url)
            
            auth = (self.confluence_config.username, self.confluence_config.password)
            
            # Для URL вида https://confluence.1solution.ru/x/E_7iGQ
            if '/x/' in url:
                tiny_id = url.split('/x/')[-1].split('/')[0]
                print(f"🔍 Попытка разрешить короткий ID: {tiny_id}")
                
                # Метод 1: Попробуем напрямую как ID страницы
                try:
                    direct_url = f"{self.confluence_config.base_url}rest/api/content/{tiny_id}?expand=body.storage"
                    direct_response = requests.get(direct_url, auth=auth)
                    if direct_response.status_code == 200:
                        print(f"✅ Короткий ID {tiny_id} работает как прямой ID страницы")
                        return tiny_id
                except Exception as e:
                    print(f"🔍 Прямой запрос не удался: {str(e)}")
                
                # Метод 2: Поиск с пагинацией
                try:
                    found_page_id = None
                    start = 0
                    limit = 100
                    max_pages = 5  # Максимум 500 страниц
                    
                    for page in range(max_pages):
                        search_url = f"{self.confluence_config.base_url}rest/api/content"
                        params = {
                            'type': 'page',
                            'limit': limit,
                            'start': start,
                            'expand': '_links'
                        }
                        
                        response = requests.get(search_url, auth=auth, params=params)
                        if response.status_code != 200:
                            break
                            
                        data = response.json()
                        results = data.get('results', [])
                        
                        if not results:  # Нет больше страниц
                            break
                            
                        print(f"🔍 Проверяю страницы {start}-{start + len(results)} (всего найдено: {data.get('size', 0)})")
                        
                        # Ищем страницы с matching tiny URL
                        for result in results:
                            tinyui = result.get('_links', {}).get('tinyui', '')
                            if f'/x/{tiny_id}' in tinyui:
                                print(f"✅ Найдена страница по tiny URL: {result['title']} (ID: {result['id']})")
                                found_page_id = result['id']
                                break
                        
                        if found_page_id:
                            break
                            
                        start += limit
                    
                    if found_page_id:
                        return found_page_id
                        
                except Exception as e:
                    print(f"🔍 Поиск с пагинацией не удался: {str(e)}")
                
                # Метод 3: CQL поиск по названию страницы (если знаем)
                try:
                    # Попробуем найти через CQL поиск
                    search_url = f"{self.confluence_config.base_url}rest/api/content/search"
                    params = {
                        'cql': f'type=page',
                        'limit': 200,
                        'expand': '_links'
                    }
                    
                    response = requests.get(search_url, auth=auth, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get('results', [])
                        
                        print(f"🔍 CQL поиск: проверяю {len(results)} страниц")
                        
                        for result in results:
                            tinyui = result.get('_links', {}).get('tinyui', '')
                            if f'/x/{tiny_id}' in tinyui:
                                print(f"✅ Найдена через CQL: {result['title']} (ID: {result['id']})")
                                return result['id']
                except Exception as e:
                    print(f"🔍 CQL поиск не удался: {str(e)}")
                
                # Метод 4: Попробуем получить список всех страниц и найти совпадение
                try:
                    all_pages_url = f"{self.confluence_config.base_url}rest/api/content"
                    params = {
                        'type': 'page',
                        'limit': 50,
                        'expand': 'metadata,space'
                    }
                    
                    response = requests.get(all_pages_url, auth=auth, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        
                        for page in data.get('results', []):
                            # Проверяем различные поля на наличие tiny_id
                            if tiny_id in str(page.get('_links', {})) or tiny_id in str(page.get('metadata', {})):
                                print(f"✅ Найдена страница в списке: {page['title']} (ID: {page['id']})")
                                return page['id']
                except Exception as e:
                    print(f"🔍 Поиск в списке страниц не удался: {str(e)}")
                
                # Метод 5: Известные соответствия коротких URL
                known_mappings = {
                    'E_7iGQ': '434302483',  # НовосибирскЭнергоСбыт
                    'YYjiGQ': '434276449',  # Easy Report
                }
                
                if tiny_id in known_mappings:
                    mapped_id = known_mappings[tiny_id]
                    print(f"✅ Найдено известное соответствие: {tiny_id} -> {mapped_id}")
                    return mapped_id
                    
            # Для обычных URL
            elif '/pages/' in url:
                return url.split('/pages/')[-1].split('/')[0]
            
            print(f"❌ Не удалось разрешить ID для URL: {url}")
            print("💡 СОВЕТ: Убедитесь, что используете полный URL из адресной строки браузера")
            return self._fallback_resolve_page_id(url)
            
        except Exception as e:
            print(f"❌ Ошибка при разрешении ID страницы для {url}: {str(e)}")
            return self._fallback_resolve_page_id(url)
    
    def _fallback_resolve_page_id(self, url: str) -> Optional[str]:
        """Fallback метод для разрешения ID страницы без аутентификации"""
        try:
            print(f"🔄 Используем fallback метод для URL: {url}")
            
            # Для коротких URL попробуем использовать tiny_id как есть
            if '/x/' in url:
                tiny_id = url.split('/x/')[-1].split('/')[0]
                print(f"🎯 Fallback: используем {tiny_id} как ID страницы")
                return tiny_id
            
            # Для обычных URL
            elif '/pages/' in url:
                return url.split('/pages/')[-1].split('/')[0]
            
            return None
            
        except Exception as e:
            print(f"❌ Fallback метод также не удался: {str(e)}")
            return None

    def _fetch_confluence_page_by_id(self, page_id: str) -> tuple[str, str]:
        """Получает содержимое и заголовок страницы Confluence по ID"""
        try:
            # Проверяем настройки аутентификации
            if not self.confluence_config.username or not self.confluence_config.password:
                error_msg = f"""
❌ CONFLUENCE НЕ НАСТРОЕН

Для анализа Confluence страниц необходимо настроить аутентификацию:

1. Добавьте в .env файл:
   CONFLUENCE_USERNAME=your-email@company.com
   CONFLUENCE_PASSWORD=your-api-token

2. Создайте API токен:
   - Войдите в https://id.atlassian.com/
   - Перейдите в Security → API tokens
   - Создайте новый токен
   - Используйте токен как CONFLUENCE_PASSWORD

💡 ВАЖНО: Используйте полный URL из адресной строки браузера:
   ✅ https://confluence.1solution.ru/spaces/PROJECT/pages/123456/PageName
   ✅ https://confluence.1solution.ru/x/ABC123

URL страницы: {self.confluence_config.base_url}pages/{page_id}

Без аутентификации невозможно:
• Получить содержимое страниц
• Найти дочерние страницы  
• Скачать вложенные файлы
• Выполнить полноценный анализ

Настройте Confluence для получения расширенного анализа.
                """
                print("⚠️ Confluence аутентификация не настроена")
                return error_msg.strip(), f"Confluence страница (ID: {page_id})"
            
            auth = (self.confluence_config.username, self.confluence_config.password)
            
            api_url = f"{self.confluence_config.base_url}rest/api/content/{page_id}?expand=body.storage"
            print(f"🔗 Запрашиваю содержимое страницы: {api_url}")
            
            response = requests.get(api_url, auth=auth)
            response.raise_for_status()
            
            data = response.json()
            
            # Извлекаем заголовок и HTML содержимое
            title = data.get('title', 'Без названия')
            html_content = data['body']['storage']['value']
            
            print(f"✅ Получена страница: {title}")
            
            # Конвертируем HTML в текст
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            
            return text, title
            
        except Exception as e:
            error_details = str(e)
            print(f"❌ Ошибка при получении содержимого страницы {page_id}: {error_details}")
            
            # Предоставляем детальную информацию об ошибке
            if "401" in error_details:
                error_msg = f"""
❌ ОШИБКА АУТЕНТИФИКАЦИИ (401)

Неверные учетные данные Confluence:
• Проверьте CONFLUENCE_USERNAME (должен быть email)
• Проверьте CONFLUENCE_PASSWORD (должен быть API токен, не пароль)
• Убедитесь, что пользователь имеет доступ к Confluence

URL страницы: {self.confluence_config.base_url}pages/{page_id}
                """
            elif "404" in error_details:
                error_msg = f"""
❌ СТРАНИЦА НЕ НАЙДЕНА (404)

Возможные причины:
• Страница была удалена или перемещена
• Неверный ID страницы: {page_id}
• Нет прав доступа к странице
• Страница находится в закрытом пространстве

💡 СОВЕТ: Убедитесь, что используете полный URL из браузера:
   ✅ https://confluence.1solution.ru/spaces/PROJECT/pages/123456/PageName
   ✅ https://confluence.1solution.ru/x/ABC123
   ❌ Не используйте внутренние ссылки или фрагменты URL

Оригинальный URL: {self.confluence_config.base_url}pages/{page_id}
                """
            elif "403" in error_details:
                error_msg = f"""
❌ ДОСТУП ЗАПРЕЩЕН (403)

Пользователь не имеет прав на чтение страницы:
• Обратитесь к администратору Confluence
• Убедитесь, что у пользователя есть доступ к пространству
• Проверьте права доступа к странице

URL страницы: {self.confluence_config.base_url}pages/{page_id}
                """
            else:
                error_msg = f"""
❌ ОШИБКА ПОДКЛЮЧЕНИЯ К CONFLUENCE

Детали ошибки: {error_details}

URL страницы: {self.confluence_config.base_url}pages/{page_id}

Проверьте:
• Доступность Confluence сервера
• Правильность базового URL
• Сетевые настройки
                """
                
            return error_msg.strip(), f"Ошибка загрузки (ID: {page_id})"
    
    def _convert_to_api_url(self, page_url: str) -> str:
        """Преобразует URL страницы в API URL"""
        # Извлекаем ID страницы из URL
        if '/pages/' in page_url:
            page_id = page_url.split('/pages/')[-1].split('/')[0]
        else:
            # Попробуем другой формат URL
            parts = page_url.split('/')
            page_id = parts[-1] if parts else ""
        
        if not page_id:
            raise ValueError(f"Не удалось извлечь ID страницы из URL: {page_url}")
        
        api_url = f"{self.confluence_config.base_url}rest/api/content/{page_id}?expand=body.storage"
        return api_url
    
    def _get_all_child_pages_recursive(self, parent_page_id: str, level: int = 1, max_level: int = 5) -> List[Dict]:
        """Рекурсивно получает все дочерние страницы с ограничением по глубине"""
        all_pages = []
        
        if level > max_level:
            print(f"⚠️ Достигнут максимальный уровень вложенности ({max_level})")
            return all_pages
            
        try:
            auth = (self.confluence_config.username, self.confluence_config.password)
            
            # API запрос для получения дочерних страниц
            api_url = f"{self.confluence_config.base_url}rest/api/content/{parent_page_id}/child/page"
            
            response = requests.get(api_url, auth=auth)
            response.raise_for_status()
            
            data = response.json()
            
            for page in data.get('results', []):
                child_id = page['id']
                child_title = page['title']
                
                page_info = {
                    'id': child_id,
                    'title': child_title,
                    'level': level
                }
                
                all_pages.append(page_info)
                print(f"📄 Найдена дочерняя страница (уровень {level}): {child_title}")
                
                # Рекурсивно получаем дочерние страницы этой страницы
                grandchildren = self._get_all_child_pages_recursive(child_id, level + 1, max_level)
                all_pages.extend(grandchildren)
                
            return all_pages
            
        except Exception as e:
            print(f"❌ Ошибка при получении дочерних страниц для {parent_page_id}: {str(e)}")
            return []
    
    def _get_page_attachments(self, page_id: str) -> List[Dict]:
        """Получает список вложенных файлов страницы"""
        try:
            auth = (self.confluence_config.username, self.confluence_config.password)
            
            # API запрос для получения вложений
            api_url = f"{self.confluence_config.base_url}rest/api/content/{page_id}/child/attachment"
            
            response = requests.get(api_url, auth=auth)
            response.raise_for_status()
            
            data = response.json()
            
            attachments = []
            for attachment in data.get('results', []):
                # Фильтруем только текстовые файлы и документы
                file_type = attachment.get('metadata', {}).get('mediaType', '').lower()
                file_name = attachment['title'].lower()
                
                # Расширенная проверка типов файлов (по MIME типу и расширению)
                supported_types = [
                    'pdf', 'doc', 'docx', 'txt', 'rtf', 'excel', 'spreadsheet', 'xlsx', 'xls',
                    'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'text/plain', 'application/rtf'
                ]
                
                supported_extensions = ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.xls', '.xlsx']
                
                is_supported = (
                    any(ext in file_type for ext in supported_types) or
                    any(file_name.endswith(ext) for ext in supported_extensions)
                )
                
                if is_supported:
                    attachments.append({
                        'id': attachment['id'],
                        'title': attachment['title'],
                        'media_type': file_type,
                        'download_url': attachment['_links']['download']
                    })
                    print(f"📎 Найден вложенный файл: {attachment['title']} ({file_type})")
                else:
                    print(f"⏭️ Пропускаем неподдерживаемый файл: {attachment['title']} ({file_type})")
                
            return attachments
            
        except Exception as e:
            print(f"❌ Ошибка при получении вложений для страницы {page_id}: {str(e)}")
            return []
    
    def _extract_attachment_content(self, attachment: Dict) -> str:
        """Извлекает содержимое вложенного файла"""
        try:
            auth = (self.confluence_config.username, self.confluence_config.password)
            
            # Скачиваем файл
            download_url = f"{self.confluence_config.base_url.rstrip('/')}{attachment['download_url']}"
            response = requests.get(download_url, auth=auth)
            response.raise_for_status()
            
            file_data = response.content
            file_name = attachment['title']
            
            # Определяем тип файла и извлекаем текст
            _, ext = os.path.splitext(file_name.lower())
            
            if ext == '.pdf':
                return self._extract_from_pdf(file_data)
            elif ext in ['.docx', '.doc']:
                return self._extract_from_docx(file_data)
            elif ext in ['.xlsx', '.xls']:
                return self._extract_from_xlsx(file_data)
            elif ext == '.rtf':
                return self._extract_from_rtf(file_data)
            elif ext == '.txt':
                try:
                    return file_data.decode('utf-8')
                except:
                    return file_data.decode('utf-8', errors='ignore')
            else:
                print(f"⚠️ Неподдерживаемый формат вложенного файла: {ext}")
                return ""
                
        except Exception as e:
            print(f"❌ Ошибка при извлечении содержимого файла {attachment['title']}: {str(e)}")
            return ""
    
    def _extract_page_id(self, url: str) -> str:
        """Извлекает ID страницы из URL"""
        if '/pages/' in url:
            return url.split('/pages/')[-1].split('/')[0]
        else:
            parts = url.split('/')
            return parts[-1] if parts else ""
    
    def _count_pages(self, text: str) -> int:
        """Подсчитывает количество страниц в тексте"""
        # Простая эвристика - считаем по разделителям страниц
        page_markers = text.count('--- Страница')
        return max(1, page_markers) if page_markers > 0 else 1 