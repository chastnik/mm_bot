"""
Модуль для анализа документов с помощью корпоративной LLM
"""
import requests
import json
from typing import List, Dict, Any
from config import ARTIFACTS_STRUCTURE

class LLMAnalyzer:
    """Класс для анализа документов с помощью корпоративной LLM"""
    
    def __init__(self, llm_config):
        self.config = llm_config
        self.base_url = llm_config.base_url.rstrip('/')
        self.headers = {
            'X-PROXY-AUTH': llm_config.proxy_token,
            'Content-Type': 'application/json'
        }
    
    def analyze_documents(self, documents: List[Dict[str, Any]], project_types: List[str]) -> Dict[str, Any]:
        """
        Анализирует документы и находит артефакты
        
        Args:
            documents: Список обработанных документов
            project_types: Выбранные типы проектов
            
        Returns:
            Результат анализа с найденными артефактами
        """
        print("🤖 Начинаю анализ документов с помощью корпоративной LLM...")
        
        # Формируем контекст для анализа
        context = self._build_analysis_context(documents, project_types)
        
        # Создаем промпт для LLM
        prompt = self._create_analysis_prompt(context, project_types)
        
        try:
            # Отправляем запрос к корпоративной LLM
            response = self._send_llm_request(prompt)
            
            if response:
                # Обрабатываем ответ
                analysis_result = self._parse_llm_response(response)
                
                # Добавляем информацию о проанализированных документах
                analysis_result['analyzed_documents'] = self._prepare_documents_info(documents)
                
                print("✅ Анализ документов завершен успешно")
                return analysis_result
            else:
                print("❌ Не удалось получить ответ от LLM")
                return self._create_empty_result(project_types, documents)
            
        except Exception as e:
            print(f"❌ Ошибка при анализе документов через LLM: {str(e)}")
            return self._create_empty_result(project_types, documents)
    
    def _send_llm_request(self, prompt: str) -> str:
        """Отправляет запрос к корпоративной LLM"""
        try:
            url = f"{self.base_url}/api/chat"
            
            payload = {
                "model": self.config.model,
                "stream": self.config.stream,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            print(f"📡 Отправляю запрос к LLM: {url}")
            print(f"🤖 Модель: {self.config.model}")
            
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=120  # 2 минуты timeout для больших документов
            )
            
            if response.status_code == 200:
                response_data = response.json()
                content = response_data.get('message', {}).get('content', '')
                
                if content:
                    print(f"✅ Получен ответ от LLM ({len(content)} символов)")
                    return content
                else:
                    print("⚠️ Получен пустой ответ от LLM")
                    return ""
            else:
                print(f"❌ Ошибка HTTP {response.status_code}: {response.text}")
                return ""
                
        except requests.exceptions.Timeout:
            print("⏱️ Таймаут при обращении к LLM")
            return ""
        except Exception as e:
            print(f"❌ Ошибка при запросе к LLM: {str(e)}")
            return ""
    
    def get_available_models(self) -> List[str]:
        """Получает список доступных моделей"""
        try:
            url = f"{self.base_url}/v1/models"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                models_data = response.json()
                models = [model.get('id', '') for model in models_data.get('data', [])]
                print(f"📋 Доступные модели: {', '.join(models)}")
                return models
            else:
                print(f"❌ Ошибка получения моделей HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Ошибка при получении списка моделей: {str(e)}")
            return []
    
    def _build_analysis_context(self, documents: List[Dict[str, Any]], project_types: List[str]) -> str:
        """Строит контекст для анализа из документов"""
        context = "ДОКУМЕНТЫ ДЛЯ АНАЛИЗА:\n\n"
        
        for i, doc in enumerate(documents, 1):
            context += f"ДОКУМЕНТ {i}: {doc['name']}\n"
            context += f"Тип: {doc['type']}\n"
            
            if doc['type'] == 'file':
                context += f"Формат: {doc['format']}\n"
            elif doc['type'] == 'confluence':
                context += f"URL: {doc['url']}\n"
                
            context += f"Количество страниц: {doc['pages']}\n"
            context += "СОДЕРЖИМОЕ:\n"
            context += doc['text'][:8000]  # Ограничиваем размер для экономии токенов
            
            if len(doc['text']) > 8000:
                context += "\n... (содержимое обрезано для экономии токенов) ...\n"
                
            context += "\n" + "="*80 + "\n\n"
        
        return context
    
    def _create_analysis_prompt(self, context: str, project_types: List[str]) -> str:
        """Создает промпт для анализа LLM"""
        
        # Определяем какие артефакты нужно искать в зависимости от типов проектов
        artifacts_to_find = []
        
        # Общие артефакты всегда включаем
        artifacts_to_find.extend(ARTIFACTS_STRUCTURE['general']['items'])
        artifacts_to_find.extend(ARTIFACTS_STRUCTURE['technical']['items'])
        artifacts_to_find.extend(ARTIFACTS_STRUCTURE['operations']['items'])
        artifacts_to_find.extend(ARTIFACTS_STRUCTURE['testing']['items'])
        artifacts_to_find.extend(ARTIFACTS_STRUCTURE['changes']['items'])
        
        # Добавляем специфичные для типов проектов
        for project_type in project_types:
            if project_type.lower() == 'bi':
                artifacts_to_find.extend(ARTIFACTS_STRUCTURE['bi']['items'])
            elif project_type.lower() == 'dwh':
                artifacts_to_find.extend(ARTIFACTS_STRUCTURE['dwh']['items'])
            elif project_type.lower() == 'rpa':
                artifacts_to_find.extend(ARTIFACTS_STRUCTURE['rpa']['items'])
        
        prompt = f"""
Ты эксперт по анализу ИТ документации. Твоя задача - проанализировать предоставленные документы и найти следующие артефакты проекта.

ТИПЫ ПРОЕКТОВ: {', '.join(project_types)}

АРТЕФАКТЫ ДЛЯ ПОИСКА:
"""
        
        for i, artifact in enumerate(artifacts_to_find, 1):
            prompt += f"{i}. {artifact}\n"
        
        prompt += f"""

{context}

ИНСТРУКЦИИ ПО АНАЛИЗУ:
1. Для каждого артефакта укажи:
   - НАЙДЕН или НЕ НАЙДЕН
   - Если найден: название документа и номер страницы (или раздел)
   - Краткое описание найденной информации (1-2 предложения)

2. Будь точным в указании источников - обязательно указывай конкретный документ и страницу

3. Если информация частично присутствует, но неполная, отметь это как "ЧАСТИЧНО НАЙДЕН"

4. Используй следующий формат ответа:

РЕЗУЛЬТАТ АНАЛИЗА:

АРТЕФАКТ: [Название артефакта]
СТАТУС: [НАЙДЕН/НЕ НАЙДЕН/ЧАСТИЧНО НАЙДЕН]
ИСТОЧНИК: [Название документа, страница/раздел]
ОПИСАНИЕ: [Краткое описание найденной информации]
---

Проанализируй все артефакты внимательно и дай максимально точный результат.
"""
        
        return prompt
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Парсит ответ LLM и структурирует результат"""
        result = {
            'found_artifacts': [],
            'not_found_artifacts': [],
            'partially_found_artifacts': [],
            'analyzed_documents': [],  # Будет заполнено позже
            'summary': {
                'total_artifacts': 0,
                'found_count': 0,
                'not_found_count': 0,
                'partially_found_count': 0
            }
        }
        
        # Разбираем ответ LLM
        try:
            # Добавляем отладочную информацию
            print(f"🔍 Отладка парсинга ответа LLM:")
            print(f"   Длина ответа: {len(response_text)} символов")
            print(f"   Первые 500 символов: {response_text[:500]}")
            
            # Ищем блоки с артефактами - пытаемся разные форматы
            blocks = response_text.split('АРТЕФАКТ:')
            if len(blocks) <= 1:  # Если не нашли, пробуем другой формат
                blocks = [block for block in response_text.split('АРТЕФАКТ') if block.strip()]
            print(f"   Найдено блоков после разделения: {len(blocks)}")
            
            # Если использовали split('АРТЕФАКТ:'), пропускаем первый блок
            # Если использовали split('АРТЕФАКТ'), обрабатываем все блоки
            start_index = 1 if 'АРТЕФАКТ:' in response_text else 0
            
            for i, block in enumerate(blocks[start_index:], 1):
                print(f"   Обрабатываю блок {i}: {block[:100]}...")
                artifact_info = self._parse_artifact_block(block)
                if artifact_info:
                    print(f"   ✅ Распознан артефакт: {artifact_info['name']} - {artifact_info['status']}")
                    status = artifact_info['status'].upper()
                    
                    if 'НАЙДЕН' in status and 'НЕ НАЙДЕН' not in status:
                        if 'ЧАСТИЧНО' in status:
                            result['partially_found_artifacts'].append(artifact_info)
                            result['summary']['partially_found_count'] += 1
                        else:
                            result['found_artifacts'].append(artifact_info)
                            result['summary']['found_count'] += 1
                    else:
                        result['not_found_artifacts'].append(artifact_info)
                        result['summary']['not_found_count'] += 1
                    
                    result['summary']['total_artifacts'] += 1
                else:
                    print(f"   ❌ Не удалось распознать артефакт в блоке {i}")
            
            print(f"📊 Результат парсинга: {result['summary']['total_artifacts']} артефактов обработано")
            
        except Exception as e:
            print(f"❌ Ошибка при парсинге ответа LLM: {str(e)}")
            
        return result
    
    def _parse_artifact_block(self, block: str) -> Dict[str, str]:
        """Парсит блок информации об артефакте"""
        try:
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            
            artifact_info = {
                'name': '',
                'status': '',
                'source': '',
                'description': ''
            }
            
            for line in lines:
                if line.startswith('СТАТУС:'):
                    artifact_info['status'] = line.replace('СТАТУС:', '').strip()
                elif line.startswith('ИСТОЧНИК:'):
                    artifact_info['source'] = line.replace('ИСТОЧНИК:', '').strip()
                elif line.startswith('ОПИСАНИЕ:'):
                    artifact_info['description'] = line.replace('ОПИСАНИЕ:', '').strip()
                elif line.startswith('---'):
                    break
                elif not artifact_info['name'] and not any(line.startswith(prefix) for prefix in ['СТАТУС:', 'ИСТОЧНИК:', 'ОПИСАНИЕ:']):
                    # Извлекаем название артефакта из строк вида "1: Название" или "Название"
                    name_line = line.strip()
                    if ':' in name_line and name_line.split(':')[0].strip().isdigit():
                        # Формат "1: Название"
                        artifact_info['name'] = ':'.join(name_line.split(':')[1:]).strip()
                    else:
                        # Обычная строка
                        artifact_info['name'] = name_line
            
            return artifact_info if artifact_info['name'] else None
            
        except Exception as e:
            print(f"Ошибка при парсинге блока артефакта: {str(e)}")
            return None
    
    def _prepare_documents_info(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Подготавливает информацию о проанализированных документах"""
        documents_info = []
        
        for doc in documents:
            doc_info = {
                'name': doc.get('name', 'Неизвестный документ'),
                'type': doc.get('type', 'unknown'),
                'pages': doc.get('pages', 0),
                'text_length': len(doc.get('text', ''))
            }
            
            # Добавляем специфичные поля в зависимости от типа документа
            if doc['type'] == 'file':
                doc_info['format'] = doc.get('format', '')
                doc_info['size_bytes'] = doc.get('size', 0)
            elif doc['type'] == 'confluence':
                doc_info['url'] = doc.get('url', '')
                doc_info['last_modified'] = doc.get('last_modified', '')
            
            documents_info.append(doc_info)
        
        return documents_info
    
    def _create_empty_result(self, project_types: List[str], documents: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Создает пустой результат в случае ошибки"""
        result = {
            'found_artifacts': [],
            'not_found_artifacts': [],
            'partially_found_artifacts': [],
            'summary': {
                'total_artifacts': 0,
                'found_count': 0,
                'not_found_count': 0,
                'partially_found_count': 0
            },
            'error': 'Не удалось проанализировать документы'
        }
        
        # Добавляем информацию о документах, даже если анализ не удался
        if documents:
            result['analyzed_documents'] = self._prepare_documents_info(documents)
        else:
            result['analyzed_documents'] = []
        
        return result 