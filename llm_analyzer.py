"""
Модуль для анализа документов с помощью корпоративной LLM
"""
from typing import List, Dict, Any, Optional
from openai import OpenAI, APITimeoutError
from config import ARTIFACTS_STRUCTURE

class LLMAnalyzer:
    """Класс для анализа документов с помощью корпоративной LLM"""
    
    def __init__(self, llm_config):
        self.config = llm_config
        self.base_url = llm_config.base_url.rstrip('/')
        self.client = OpenAI(
            api_key=llm_config.proxy_token,
            base_url=self.base_url,
            timeout=300.0
        )
    
    def analyze_documents(self, documents: List[Dict[str, Any]], project_types: List[str]) -> Dict[str, Any]:
        """
        Анализирует документы и находит артефакты поэтапно
        
        Args:
            documents: Список обработанных документов
            project_types: Выбранные типы проектов
            
        Returns:
            Результат анализа с найденными артефактами
        """
        print("🤖 Начинаю поэтапный анализ документов с помощью корпоративной LLM...")
        
        # Получаем полный список артефактов
        all_artifacts = self._get_all_required_artifacts(project_types)
        print(f"📋 Всего артефактов для анализа: {len(all_artifacts)}")
        
        # Формируем контекст для анализа (один раз для всех этапов)
        context = self._build_analysis_context(documents, project_types)
        
        # С 64K контекстом можем обрабатывать больше артефактов за раз
        batch_size = 15  # Увеличиваем размер батча
        artifact_batches = []
        for i in range(0, len(all_artifacts), batch_size):
            artifact_batches.append(all_artifacts[i:i + batch_size])
        
        print(f"🔄 Анализ будет проведен в {len(artifact_batches)} этапов")
        
        # Объединенный результат
        combined_result = {
            'found_artifacts': [],
            'not_found_artifacts': [],
            'partially_found_artifacts': [],
            'analyzed_documents': [],
            'summary': {
                'total_artifacts': 0,
                'found_count': 0,
                'not_found_count': 0,
                'partially_found_count': 0
            }
        }
        
        try:
            # Обрабатываем каждый батч
            for batch_num, artifacts_batch in enumerate(artifact_batches, 1):
                print(f"🔍 Этап {batch_num}/{len(artifact_batches)}: анализирую {len(artifacts_batch)} артефактов...")
                
                # Создаем промпт для текущего батча
                prompt = self._create_analysis_prompt(context, artifacts_batch, batch_num, len(artifacts_batch))
                
                # Отправляем запрос к LLM
                response = self._send_llm_request(prompt)
                
                if response:
                    # Обрабатываем ответ для текущего батча
                    batch_result = self._parse_llm_response(response, artifacts_batch)
                    
                    # Объединяем результаты
                    combined_result['found_artifacts'].extend(batch_result['found_artifacts'])
                    combined_result['not_found_artifacts'].extend(batch_result['not_found_artifacts'])
                    combined_result['partially_found_artifacts'].extend(batch_result['partially_found_artifacts'])
                    
                    # Обновляем счетчики
                    combined_result['summary']['found_count'] += batch_result['summary']['found_count']
                    combined_result['summary']['not_found_count'] += batch_result['summary']['not_found_count']
                    combined_result['summary']['partially_found_count'] += batch_result['summary']['partially_found_count']
                    combined_result['summary']['total_artifacts'] += batch_result['summary']['total_artifacts']
                    
                    print(f"✅ Этап {batch_num} завершен: найдено {batch_result['summary']['found_count']} артефактов")
                else:
                    print(f"❌ Ошибка на этапе {batch_num}")
                    # Добавляем артефакты текущего батча как не найденные
                    for artifact in artifacts_batch:
                        combined_result['not_found_artifacts'].append({
                            'name': artifact,
                            'status': 'НЕ НАЙДЕН',
                            'source': 'Ошибка анализа',
                            'description': 'Не удалось проанализировать из-за ошибки LLM'
                        })
                        combined_result['summary']['not_found_count'] += 1
                        combined_result['summary']['total_artifacts'] += 1
            
            # Добавляем информацию о проанализированных документах
            combined_result['analyzed_documents'] = self._prepare_documents_info(documents or [])
            
            print(f"🎉 Поэтапный анализ завершен: {combined_result['summary']['found_count']}/{combined_result['summary']['total_artifacts']} артефактов найдено")
            return combined_result
            
        except Exception as e:
            print(f"❌ Ошибка при поэтапном анализе документов: {str(e)}")
            return self._create_empty_result(project_types, documents or [])
    
    def _send_llm_request(self, prompt: str) -> str:
        """Отправляет запрос к корпоративной LLM"""
        try:
            print(f"📡 Отправляю запрос к LLM через OpenAI Responses API: {self.base_url}")
            print(f"🤖 Модель: {self.config.model}")

            response = self.client.responses.create(
                model=self.config.model,
                input=[
                    {
                        "role": "system",
                        "content": "/no_think"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            content = self._extract_response_text(response)
            if content:
                print(f"✅ Получен ответ от LLM ({len(content)} символов)")
                return content

            print("⚠️ Получен пустой ответ от LLM")
            return ""
        except APITimeoutError:
            print("⏱️ Таймаут при обращении к LLM")
            return ""
        except Exception as e:
            print(f"❌ Ошибка при запросе к LLM: {str(e)}")
            return ""
    
    def get_available_models(self) -> List[str]:
        """Получает список доступных моделей"""
        try:
            models_response = self.client.models.list()
            models = [model.id for model in models_response.data if getattr(model, 'id', '')]
            print(f"📋 Доступные модели: {', '.join(models)}")
            return models
        except Exception as e:
            print(f"❌ Ошибка при получении списка моделей: {str(e)}")
            return []

    def _extract_response_text(self, response: Any) -> str:
        """Извлекает текст из ответа OpenAI Responses API."""
        output_text = getattr(response, 'output_text', '')
        if output_text:
            return output_text.strip()

        text_parts = []
        for item in getattr(response, 'output', []) or []:
            if getattr(item, 'type', '') != 'message':
                continue
            for content in getattr(item, 'content', []) or []:
                content_type = getattr(content, 'type', '')
                if content_type in ['output_text', 'text']:
                    text = getattr(content, 'text', '')
                    if text:
                        text_parts.append(text.strip())

        return "\n".join(part for part in text_parts if part)
    
    def _build_analysis_context(self, documents: List[Dict[str, Any]], project_types: List[str]) -> str:
        """Строит контекст для анализа из документов с детальной структурой источников"""
        context = "ДОКУМЕНТЫ ДЛЯ АНАЛИЗА:\n\n"
        
        for i, doc in enumerate(documents, 1):
            context += f"ДОКУМЕНТ {i}: {doc['name']}\n"
            context += f"Тип: {doc['type']}\n"
            
            if doc['type'] == 'file':
                context += f"Формат: {doc['format']}\n"
                context += f"ИСТОЧНИК: Файл '{doc['name']}'\n"
            elif doc['type'] == 'confluence':
                context += f"ПОЛНЫЙ URL: {doc['url']}\n"
                # Для Confluence документов с множественными источниками
                if 'child_pages_count' in doc and doc['child_pages_count'] > 0:
                    context += f"СТРУКТУРА: Главная страница + {doc['child_pages_count']} дочерних страниц\n"
                    if 'main_attachments_count' in doc:
                        context += f"ФАЙЛЫ: {doc['main_attachments_count']} на главной, {doc.get('child_attachments_count', 0)} на дочерних\n"
                context += f"ИСТОЧНИК: Confluence страница '{doc['url']}' и все вложенные файлы\n"
                
            context += f"Количество страниц: {doc['pages']}\n"
            context += "\nСОДЕРЖИМОЕ (с разметкой источников):\n"
            
            # Добавляем разметку источников в содержимое
            content = doc['text']
            
            # Ищем разделители файлов и добавляем разметку источников
            lines = content.split('\n')
            enhanced_content = []
            current_source = ""
            
            for line in lines:
                if line.startswith('--- ВЛОЖЕННЫЙ ФАЙЛ'):
                    if 'главная страница' in line:
                        file_name = line.split(':')[1].split('---')[0].strip()
                        current_source = f"[ФАЙЛ: {file_name}, CONFLUENCE: Главная страница, URL: {doc.get('url', 'нет URL')}]"
                    elif 'со страницы' in line:
                        # Извлекаем название файла и страницы
                        parts = line.split("'")
                        if len(parts) >= 4:
                            confluence_page = parts[1]
                            file_name = parts[3].replace('):', '').strip()
                            current_source = f"[ФАЙЛ: {file_name}, CONFLUENCE: {confluence_page}, BASE URL: {doc.get('url', 'нет URL')}]"
                    enhanced_content.append(f"\n{current_source}")
                    enhanced_content.append(line)
                elif line.startswith('--- ДОЧЕРНЯЯ СТРАНИЦА'):
                    # Извлекаем название страницы Confluence
                    page_title = line.split(':')[1].split('---')[0].strip()
                    current_source = f"[CONFLUENCE: {page_title}, BASE URL: {doc.get('url', 'нет URL')}]"
                    enhanced_content.append(f"\n{current_source}")
                    enhanced_content.append(line)
                elif line.startswith('--- ГЛАВНАЯ СТРАНИЦА'):
                    page_title = line.split(':')[1].split('---')[0].strip()
                    current_source = f"[CONFLUENCE: {page_title} (главная), ПОЛНЫЙ URL: {doc.get('url', 'нет URL')}]"
                    enhanced_content.append(f"\n{current_source}")
                    enhanced_content.append(line)
                else:
                    enhanced_content.append(line)
            
            enhanced_text = '\n'.join(enhanced_content)
            
            # С увеличенным контекстом LLM можем обрабатывать значительно больше
            max_doc_length = 100000  # 100K символов на документ с 64K контекстом
            if len(enhanced_text) > max_doc_length:
                # Для больших документов берем больше начала (содержание, введение) 
                # и меньше конца (обычно менее важные детали)
                start_part = enhanced_text[:int(max_doc_length * 0.7)]  # 70% в начале
                end_part = enhanced_text[-int(max_doc_length * 0.3):]    # 30% в конце
                context += start_part
                context += f"\n... (средняя часть обрезана, показано {int(max_doc_length * 0.7)} симв. начала и {int(max_doc_length * 0.3)} симв. конца) ...\n"
                context += end_part
                print(f"📄 Документ '{doc['name']}' обрезан: {len(enhanced_text)} → {max_doc_length} символов")
            else:
                context += enhanced_text
                print(f"📄 Документ '{doc['name']}': {len(enhanced_text)} символов (без обрезки)")
                
            context += "\n" + "="*80 + "\n\n"
        
        # Контролируем общий размер контекста
        print(f"📊 Итоговый размер контекста: {len(context)} символов")
        
        # Если контекст слишком большой даже после обрезки документов - дополнительная оптимизация  
        max_total_context = 300000  # 300К символов с 64K контекстом LLM
        if len(context) > max_total_context:
            print(f"⚠️ Контекст превышает лимит ({len(context)} > {max_total_context}), применяю дополнительную оптимизацию...")
            
            # Обрезаем только если действительно критично
            context = context[:max_total_context]
            context += "\n\n... (контекст обрезан из-за ограничений размера) ..."
            print(f"✂️ Контекст обрезан до {len(context)} символов")
        
        return context
    
    def _get_all_required_artifacts(self, project_types: List[str]) -> List[str]:
        """Получает полный список всех необходимых артефактов"""
        artifacts_to_find = []
        
        # Всегда добавляем все базовые категории
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
        
        return artifacts_to_find

    def _create_analysis_prompt(self, context: str, artifacts_batch: List[str], batch_number: int, total_batches: int) -> str:
        """Создает промпт для анализа LLM для конкретного батча артефактов"""
        
        print(f"📝 Создаю промпт для батча {batch_number}:")
        print(f"   Артефакты в батче: {artifacts_batch}")
        
        prompt = f"""
АНАЛИЗ ДОКУМЕНТОВ - ЭТАП {batch_number} из {total_batches}

ВАЖНО: 
- Анализируй ТОЛЬКО заданные артефакты из списка ниже
- НЕ добавляй собственные артефакты
- НЕ изменяй названия артефактов
- Отвечай СТРОГО по заданному формату

ДОКУМЕНТЫ ДЛЯ АНАЛИЗА:
{context}

НАЙДИ В ДОКУМЕНТАХ СЛЕДУЮЩИЕ {len(artifacts_batch)} АРТЕФАКТОВ:

"""
        
        # Даем готовый шаблон для каждого артефакта в батче
        for i, artifact in enumerate(artifacts_batch, 1):
            prompt += f"""**АРТЕФАКТ: {artifact}**
* СТАТУС: [НАЙДЕН / НЕ НАЙДЕН / ЧАСТИЧНО НАЙДЕН]
* ИСТОЧНИК: [Укажи ПОЛНОЕ название документа/файла И номер страницы/раздела ИЛИ полный URL Confluence страницы]
* ОПИСАНИЕ: [Краткое описание найденной информации]

"""
        
        prompt += f"""
ТРЕБОВАНИЯ К ОТВЕТУ:
1. Ответь для КАЖДОГО из {len(artifacts_batch)} артефактов выше
2. Используй ТОЧНО тот же формат с **АРТЕФАКТ:** и звездочками *
3. НЕ меняй названия артефактов - копируй их точно
4. Заполни только СТАТУС, ИСТОЧНИК и ОПИСАНИЕ
5. Если артефакт не найден, напиши СТАТУС: НЕ НАЙДЕН

ТРЕБОВАНИЯ К ИСТОЧНИКАМ:
• Для файлов: укажи ПОЛНОЕ название файла + номер страницы/раздела
• Для Confluence: укажи ПОЛНЫЙ URL страницы ИЛИ название страницы
• НЕ сокращай названия - используй полные имена
• Примеры хороших источников:
  - "Техническое задание v2.1.docx, стр. 15"
  - "https://confluence.1solution.ru/display/PROJECT/Architecture"
  - "Confluence: Архитектурное решение системы (главная страница)"

НАЧИНАЙ АНАЛИЗ:
"""
        
        return prompt
    
    def _parse_llm_response(self, response_text: str, expected_artifacts: Optional[List[str]] = None) -> Dict[str, Any]:
        """Парсит ответ LLM и структурирует результат"""
        if expected_artifacts is None:
            expected_artifacts = []
        result = {
            'found_artifacts': [],
            'not_found_artifacts': [],
            'partially_found_artifacts': [],
            'analyzed_documents': [],
            'summary': {
                'total_artifacts': 0,
                'found_count': 0,
                'not_found_count': 0,
                'partially_found_count': 0
            }
        }
        
        try:
            if not expected_artifacts:
                print(f"⚠️ expected_artifacts не передан или пуст - нельзя выполнить анализ")
                return result
            # ВСЕГДА используем принудительную логику, если есть ожидаемые артефакты
            print(f"🔧 Принудительный режим: создаю результаты для {len(expected_artifacts)} ожидаемых артефактов")
            import re
            blocks = []
            if '**АРТЕФАКТ:' in response_text:
                blocks = response_text.split('**АРТЕФАКТ:')[1:]
            elif '**' in response_text:
                artifact_pattern = r'\*\*\s*([^*\n]+?)\s*\*\*'
                matches = re.finditer(artifact_pattern, response_text, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    start_pos = match.start()
                    remaining_text = response_text[match.end():]
                    next_match = re.search(artifact_pattern, remaining_text)
                    if next_match:
                        end_pos = match.end() + next_match.start()
                    else:
                        end_pos = len(response_text)
                    blocks.append(response_text[start_pos:end_pos])
            print(f"   Найдено {len(blocks)} блоков в ответе")
            for i, artifact_name in enumerate(expected_artifacts):
                print(f"   📋 Обрабатываю артефакт {i+1}: '{artifact_name}'")
                status = 'НЕ НАЙДЕН'
                source = 'Не указан'
                description = 'Информация не найдена'
                if i < len(blocks):
                    block = blocks[i]
                    artifact_info = self._parse_artifact_block(block)
                    if artifact_info and artifact_info.get('status'):
                        status = artifact_info['status']
                        source = artifact_info.get('source', 'Из ответа LLM')
                        description = artifact_info.get('description', 'Найдено в анализе')
                        print(f"      ✅ Информация найдена в блоке {i+1}")
                final_artifact_info = {
                    'name': artifact_name,
                    'status': status,
                    'source': source,
                    'description': description,
                    'unique_key': artifact_name
                }
                print(f"   ✅ Создан артефакт: {final_artifact_info['name']} - {final_artifact_info['status']}")
                print(f"      📂 Источник: {final_artifact_info.get('source', 'не указан')}")
                status_upper = final_artifact_info['status'].upper()
                if 'НАЙДЕН' in status_upper:
                    if 'НЕ НАЙДЕН' in status_upper:
                        result['not_found_artifacts'].append(final_artifact_info)
                        result['summary']['not_found_count'] += 1
                    elif 'ЧАСТИЧНО' in status_upper or 'PARTIAL' in status_upper:
                        result['partially_found_artifacts'].append(final_artifact_info)
                        result['summary']['partially_found_count'] += 1
                    else:
                        result['found_artifacts'].append(final_artifact_info)
                        result['summary']['found_count'] += 1
                elif any(keyword in status_upper for keyword in ['FOUND', 'ЕСТЬ', 'ПРИСУТСТВУЕТ']):
                    result['found_artifacts'].append(final_artifact_info)
                    result['summary']['found_count'] += 1
                elif any(keyword in status_upper for keyword in ['PARTIAL', 'ЧАСТИЧН']):
                    result['partially_found_artifacts'].append(final_artifact_info)
                    result['summary']['partially_found_count'] += 1
                else:
                    result['not_found_artifacts'].append(final_artifact_info)
                    result['summary']['not_found_count'] += 1
                result['summary']['total_artifacts'] += 1
            print(f"📊 Результат парсинга: {result['summary']['total_artifacts']} артефактов обработано")
        except Exception as e:
            print(f"❌ Ошибка при парсинге ответа LLM: {str(e)}")
            print(f"📋 Полный ответ LLM для отладки:")
            print(f"─" * 80)
            print(response_text[:2000] + ("..." if len(response_text) > 2000 else ""))
            print(f"─" * 80)
        return result
    
    def _parse_artifact_block(self, block: str) -> Dict[str, str]:
        """Парсит блок информации об артефакте"""
        try:
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            
            artifact_info = {
                'name': '',
                'status': '',
                'source': '',
                'description': '',
                'instance_id': ''  # Для различения экземпляров одного артефакта
            }
            
            # Сначала пытаемся найти название артефакта в первой строке или в тексте
            first_line = lines[0] if lines else ""
            
            # Извлекаем название артефакта из первой строки блока
            if first_line:
                # Убираем все форматирование и ищем название
                clean_line = first_line.replace('**', '').replace('*', '').strip()
                
                # Если это не служебное поле, то это название артефакта
                if not any(keyword in clean_line.lower() for keyword in ['статус:', 'источник:', 'описание:']):
                    # Если есть "АРТЕФАКТ:" - берем часть после двоеточия
                    if 'артефакт:' in clean_line.lower():
                        parts = clean_line.split(':', 1)
                        if len(parts) > 1:
                            artifact_info['name'] = parts[1].strip()
                        else:
                            artifact_info['name'] = clean_line
                    else:
                        artifact_info['name'] = clean_line
            
            # Если не нашли в первой строке, ищем в блоке название после "АРТЕФАКТ:"
            if not artifact_info['name']:
                for line in lines:
                    if 'артефакт' in line.lower() and ':' in line:
                        # Извлекаем название после двоеточия
                        name_part = line.split(':', 1)[1].strip()
                        artifact_info['name'] = name_part.replace('**', '').replace('*', '').strip()
                        break
            
            # Обрабатываем остальные поля
            for line in lines:
                line = line.strip()
                line_lower = line.lower()
                
                if 'статус:' in line_lower:
                    status_pos = line_lower.find('статус:')
                    if status_pos != -1:
                        status_text = line[status_pos + 7:].strip()
                        artifact_info['status'] = status_text.replace('*', '').strip()
                        
                elif 'источник:' in line_lower:
                    source_pos = line_lower.find('источник:')
                    if source_pos != -1:
                        source_text = line[source_pos + 9:].strip()
                        source_text = source_text.replace('*', '').replace('+', '').strip()
                        if source_text:
                            artifact_info['source'] = source_text
                        
                elif 'описание:' in line_lower:
                    desc_pos = line_lower.find('описание:')
                    if desc_pos != -1:
                        desc_text = line[desc_pos + 9:].strip()
                        artifact_info['description'] = desc_text.replace('*', '').strip()
            
            # Если все еще нет названия, используем заглушку из содержимого
            if not artifact_info['name'] and artifact_info['description']:
                # Берем первые слова из описания как название
                desc_words = artifact_info['description'].split()[:3]
                artifact_info['name'] = ' '.join(desc_words) + '...'
            
            # Дополнительная логика для случаев, когда статус не найден явно
            if not artifact_info['status'] and artifact_info['name']:
                # Попробуем определить статус из контекста
                block_lower = block.lower()
                if any(word in block_lower for word in ['найден', 'есть', 'присутствует', 'содержит']):
                    artifact_info['status'] = 'НАЙДЕН'
                elif any(word in block_lower for word in ['не найден', 'отсутствует', 'нет']):
                    artifact_info['status'] = 'НЕ НАЙДЕН'
                elif any(word in block_lower for word in ['частично', 'неполный', 'частичн']):
                    artifact_info['status'] = 'ЧАСТИЧНО НАЙДЕН'
                else:
                    # Если есть упоминание файлов/документов, считаем что найден
                    if any(word in block_lower for word in ['файл:', 'документ', 'страниц', 'confluence']):
                        artifact_info['status'] = 'НАЙДЕН'
                    else:
                        artifact_info['status'] = 'НЕ НАЙДЕН'
                
                print(f"   🔍 Статус определен автоматически: '{artifact_info['status']}'")
            
            # Если описание пустое, используем весь блок
            if not artifact_info['description'] and artifact_info['name']:
                # Извлекаем описание из всего блока, исключая служебные строки
                desc_lines = []
                for line in lines:
                    if not any(keyword in line.lower() for keyword in ['статус:', 'источник:', 'описание:']):
                        clean_line = line.replace('**', '').replace('*', '').strip()
                        if clean_line and clean_line != artifact_info['name']:
                            desc_lines.append(clean_line)
                
                if desc_lines:
                    artifact_info['description'] = ' '.join(desc_lines[:3])  # Первые 3 строки
            
            # Проверяем что у нас есть минимально необходимые данные
            if artifact_info['name'] and artifact_info['status']:
                # Создаем уникальный ключ
                artifact_info['unique_key'] = artifact_info['name']
                print(f"   ✅ Успешно распознан: '{artifact_info['name']}' - {artifact_info['status']}")
                return artifact_info
            else:
                print(f"   ❌ Недостаточно данных: name='{artifact_info['name']}', status='{artifact_info['status']}'")
                print(f"   📄 Блок содержимого: {block[:200]}...")
                return {}
            
        except Exception as e:
            print(f"❌ Ошибка при парсинге блока артефакта: {str(e)}")
            return {}
    
    def _prepare_documents_info(self, documents: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        if documents is None:
            documents = []
        documents_info = []
        for doc in documents:
            doc_info = {
                'name': doc.get('name', 'Неизвестный документ'),
                'type': doc.get('type', 'unknown'),
                'pages': doc.get('pages', 0),
                'text_length': len(doc.get('text', ''))
            }
            if doc['type'] == 'file':
                doc_info['format'] = doc.get('format', '')
                doc_info['size_bytes'] = doc.get('size', 0)
            elif doc['type'] == 'confluence':
                doc_info['url'] = doc.get('url', '')
                doc_info['last_modified'] = doc.get('last_modified', '')
            documents_info.append(doc_info)
        return documents_info
    
    def _create_empty_result(self, project_types: List[str], documents: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
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
        result['analyzed_documents'] = self._prepare_documents_info(documents or [])
        return result 