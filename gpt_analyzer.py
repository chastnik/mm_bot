"""
Модуль для анализа документов с помощью GPT API
"""
import openai
from typing import List, Dict, Any
from config import ARTIFACTS_STRUCTURE

class GPTAnalyzer:
    """Класс для анализа документов с помощью GPT"""
    
    def __init__(self, gpt_config):
        self.config = gpt_config
        self.client = openai.OpenAI(
            api_key=gpt_config.api_key,
            base_url=gpt_config.base_url
        )
    
    def analyze_documents(self, documents: List[Dict[str, Any]], project_types: List[str]) -> Dict[str, Any]:
        """
        Анализирует документы и находит артефакты
        
        Args:
            documents: Список обработанных документов
            project_types: Выбранные типы проектов
            
        Returns:
            Результат анализа с найденными артефактами
        """
        # Формируем контекст для анализа
        context = self._build_analysis_context(documents, project_types)
        
        # Создаем промпт для GPT
        prompt = self._create_analysis_prompt(context, project_types)
        
        try:
            # Отправляем запрос к GPT
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты эксперт по анализу ИТ документации. Твоя задача - найти и сопоставить артефакты проекта с предоставленными документами."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.config.max_tokens,
                temperature=0.1
            )
            
            # Обрабатываем ответ
            analysis_result = self._parse_gpt_response(response.choices[0].message.content)
            
            return analysis_result
            
        except Exception as e:
            print(f"Ошибка при анализе документов через GPT: {str(e)}")
            return self._create_empty_result(project_types)
    
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
        """Создает промпт для анализа GPT"""
        
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
Проанализируй предоставленные документы и найди следующие артефакты проекта.

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
    
    def _parse_gpt_response(self, response_text: str) -> Dict[str, Any]:
        """Парсит ответ GPT и структурирует результат"""
        result = {
            'found_artifacts': [],
            'not_found_artifacts': [],
            'partially_found_artifacts': [],
            'summary': {
                'total_artifacts': 0,
                'found_count': 0,
                'not_found_count': 0,
                'partially_found_count': 0
            }
        }
        
        # Разбираем ответ GPT
        try:
            # Ищем блоки с артефактами
            blocks = response_text.split('АРТЕФАКТ:')
            
            for block in blocks[1:]:  # Пропускаем первый пустой блок
                artifact_info = self._parse_artifact_block(block)
                if artifact_info:
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
            
        except Exception as e:
            print(f"Ошибка при парсинге ответа GPT: {str(e)}")
            
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
            
            current_field = None
            
            for line in lines:
                if line.startswith('---'):
                    break
                    
                if ':' in line and line.count(':') == 1:
                    field, value = line.split(':', 1)
                    field = field.strip().upper()
                    value = value.strip()
                    
                    if not artifact_info['name'] and field != 'СТАТУС' and field != 'ИСТОЧНИК' and field != 'ОПИСАНИЕ':
                        artifact_info['name'] = value
                        current_field = 'name'
                    elif field == 'СТАТУС':
                        artifact_info['status'] = value
                        current_field = 'status'
                    elif field == 'ИСТОЧНИК':
                        artifact_info['source'] = value
                        current_field = 'source'
                    elif field == 'ОПИСАНИЕ':
                        artifact_info['description'] = value
                        current_field = 'description'
                else:
                    # Продолжение предыдущего поля
                    if current_field and line:
                        artifact_info[current_field] += ' ' + line
            
            # Если имя не задано, используем первую строку
            if not artifact_info['name'] and lines:
                artifact_info['name'] = lines[0]
            
            return artifact_info if artifact_info['name'] else None
            
        except Exception as e:
            print(f"Ошибка при парсинге блока артефакта: {str(e)}")
            return None
    
    def _create_empty_result(self, project_types: List[str]) -> Dict[str, Any]:
        """Создает пустой результат в случае ошибки"""
        return {
            'found_artifacts': [],
            'not_found_artifacts': [],
            'partially_found_artifacts': [],
            'summary': {
                'total_artifacts': 0,
                'found_count': 0,
                'not_found_count': 0,
                'partially_found_count': 0
            },
            'error': True
        } 