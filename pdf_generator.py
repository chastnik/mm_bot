"""
Модуль для генерации PDF отчетов с результатами анализа
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
from typing import Dict, Any, List
import os
import io

class PDFGenerator:
    """Класс для генерации PDF отчетов"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.font_name = 'DejaVuSans'
        self.bold_font_name = 'DejaVuSans-Bold'
        self._setup_fonts()
        self._setup_styles()
    
    def _setup_fonts(self):
        """Настройка шрифтов с поддержкой русского языка"""
        # Пути к возможным местам расположения шрифтов DejaVu
        possible_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            '/System/Library/Fonts/DejaVuSans.ttf',
            '/usr/local/share/fonts/DejaVuSans.ttf',
            'DejaVuSans.ttf'  # если шрифт в локальной директории
        ]
        
        bold_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
            '/System/Library/Fonts/DejaVuSans-Bold.ttf',
            '/usr/local/share/fonts/DejaVuSans-Bold.ttf',
            'DejaVuSans-Bold.ttf'
        ]
        
        # Пытаемся зарегистрировать DejaVu Sans
        font_registered = False
        bold_font_registered = False
        
        for path in possible_paths:
            try:
                if os.path.exists(path):
                    pdfmetrics.registerFont(TTFont('DejaVuSans', path))
                    font_registered = True
                    print(f"Успешно зарегистрирован шрифт: {path}")
                    break
            except Exception as e:
                print(f"Не удалось зарегистрировать шрифт {path}: {e}")
                continue
        
        for path in bold_paths:
            try:
                if os.path.exists(path):
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', path))
                    bold_font_registered = True
                    print(f"Успешно зарегистрирован жирный шрифт: {path}")
                    break
            except Exception as e:
                print(f"Не удалось зарегистрировать жирный шрифт {path}: {e}")
                continue
        
        # Если DejaVu не найден, пытаемся установить через системные пакеты
        if not font_registered:
            print("ВНИМАНИЕ: Шрифт DejaVu Sans не найден.")
            print("Для корректного отображения русских символов в PDF рекомендуется установить:")
            print("Ubuntu/Debian: sudo apt-get install fonts-dejavu")
            print("CentOS/RHEL: sudo yum install dejavu-sans-fonts")
            print("Используется резервный шрифт с ограниченной поддержкой кириллицы.")
            
            # Используем встроенный шрифт с поддержкой Unicode
            self.font_name = 'Times-Roman'
            self.bold_font_name = 'Times-Bold'
        
        if not bold_font_registered and font_registered:
            # Если обычный шрифт найден, но жирный нет
            self.bold_font_name = 'DejaVuSans'  # Используем обычный вместо жирного
    
    def _setup_styles(self):
        """Настройка стилей для PDF"""
        # Создаем кастомные стили с правильными шрифтами
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontName=self.bold_font_name,
            fontSize=18,
            textColor=colors.HexColor('#2E4057'),
            spaceAfter=20,
            alignment=1  # Центрирование
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading1',
            parent=self.styles['Heading1'],
            fontName=self.bold_font_name,
            fontSize=14,
            textColor=colors.HexColor('#2E4057'),
            spaceBefore=15,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontName=self.bold_font_name,
            fontSize=12,
            textColor=colors.HexColor('#5A6C7D'),
            spaceBefore=12,
            spaceAfter=8
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomNormal',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            textColor=colors.black,
            spaceBefore=3,
            spaceAfter=3
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomFound',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            textColor=colors.HexColor('#28A745'),
            spaceBefore=2,
            spaceAfter=2
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomNotFound',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            textColor=colors.HexColor('#DC3545'),
            spaceBefore=2,
            spaceAfter=2
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomPartial',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            textColor=colors.HexColor('#FFC107'),
            spaceBefore=2,
            spaceAfter=2
        ))
    
    def generate_report(self, analysis_result: Dict[str, Any], project_types: List[str], 
                       documents: List[Dict[str, Any]] = None) -> bytes:
        """
        Генерирует PDF отчет с результатами анализа
        
        Args:
            analysis_result: Результат анализа документов
            project_types: Выбранные типы проектов
            documents: Список обработанных документов (deprecated, используется analyzed_documents из result)
            
        Returns:
            PDF файл в виде байтов
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
        
        # Получаем информацию о документах из результата анализа или из параметра (для обратной совместимости)
        analyzed_documents = analysis_result.get('analyzed_documents', documents or [])
        
        # Создаем содержимое отчета
        story = []
        
        # Заголовок
        story.append(Paragraph("Отчет по анализу документации ИТ проекта", self.styles['CustomTitle']))
        story.append(Spacer(1, 12))
        
        # Информация о анализе
        story.extend(self._create_analysis_info(project_types, analyzed_documents))
        
        # Сводка результатов
        story.extend(self._create_summary_section(analysis_result))
        
        # Детальные результаты
        story.extend(self._create_detailed_results(analysis_result))
        
        # Список документов
        story.extend(self._create_documents_section(analyzed_documents))
        
        # Генерируем PDF
        doc.build(story)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_analysis_info(self, project_types: List[str], documents: List[Dict[str, Any]]) -> List:
        """Создает секцию с информацией об анализе"""
        elements = []
        
        elements.append(Paragraph("Информация об анализе", self.styles['CustomHeading1']))
        
        # Дата анализа
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        elements.append(Paragraph(f"<b>Дата анализа:</b> {current_date}", self.styles['CustomNormal']))
        
        # Типы проектов
        types_str = ", ".join(project_types)
        elements.append(Paragraph(f"<b>Типы проектов:</b> {types_str}", self.styles['CustomNormal']))
        
        # Количество документов
        elements.append(Paragraph(f"<b>Количество документов:</b> {len(documents)}", self.styles['CustomNormal']))
        
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_summary_section(self, analysis_result: Dict[str, Any]) -> List:
        """Создает секцию со сводкой результатов"""
        elements = []
        
        elements.append(Paragraph("Сводка результатов", self.styles['CustomHeading1']))
        
        summary = analysis_result.get('summary', {})
        
        # Создаем таблицу с результатами
        data = [
            ['Показатель', 'Количество'],
            ['Всего артефактов', str(summary.get('total_artifacts', 0))],
            ['Найдено', str(summary.get('found_count', 0))],
            ['Найдено частично', str(summary.get('partially_found_count', 0))],
            ['Не найдено', str(summary.get('not_found_count', 0))]
        ]
        
        table = Table(data, colWidths=[8*cm, 4*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E4057')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), self.bold_font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_detailed_results(self, analysis_result: Dict[str, Any]) -> List:
        """Создает секцию с детальными результатами"""
        elements = []
        
        elements.append(Paragraph("Детальные результаты", self.styles['CustomHeading1']))
        
        # Найденные артефакты
        found_artifacts = analysis_result.get('found_artifacts', [])
        if found_artifacts:
            elements.append(Paragraph("Найденные артефакты", self.styles['CustomHeading2']))
            for artifact in found_artifacts:
                elements.extend(self._create_artifact_entry(artifact, 'found'))
        
        # Частично найденные артефакты
        partial_artifacts = analysis_result.get('partially_found_artifacts', [])
        if partial_artifacts:
            elements.append(Paragraph("Частично найденные артефакты", self.styles['CustomHeading2']))
            for artifact in partial_artifacts:
                elements.extend(self._create_artifact_entry(artifact, 'partial'))
        
        # Не найденные артефакты
        not_found_artifacts = analysis_result.get('not_found_artifacts', [])
        if not_found_artifacts:
            elements.append(Paragraph("Не найденные артефакты", self.styles['CustomHeading2']))
            for artifact in not_found_artifacts:
                elements.extend(self._create_artifact_entry(artifact, 'not_found'))
        
        return elements
    
    def _create_artifact_entry(self, artifact: Dict[str, str], status_type: str) -> List:
        """Создает запись об артефакте"""
        elements = []
        
        # Выбираем стиль в зависимости от статуса
        if status_type == 'found':
            status_style = 'CustomFound'
            status_text = "✓ НАЙДЕН"
        elif status_type == 'partial':
            status_style = 'CustomPartial'
            status_text = "◐ ЧАСТИЧНО НАЙДЕН"
        else:
            status_style = 'CustomNotFound'
            status_text = "✗ НЕ НАЙДЕН"
        
        # Название артефакта
        elements.append(Paragraph(f"<b>{artifact.get('name', 'Неизвестный артефакт')}</b>", 
                                self.styles['CustomNormal']))
        
        # Статус
        elements.append(Paragraph(f"<b>Статус:</b> {status_text}", 
                                self.styles[status_style]))
        
        # Источник (если есть)
        source = artifact.get('source', '').strip()
        if source and source != 'Не указан':
            elements.append(Paragraph(f"<b>Источник:</b> {source}", 
                                    self.styles['CustomNormal']))
        
        # Описание (если есть)
        description = artifact.get('description', '').strip()
        if description and description != 'Описание отсутствует':
            elements.append(Paragraph(f"<b>Описание:</b> {description}", 
                                    self.styles['CustomNormal']))
        
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _create_documents_section(self, documents: List[Dict[str, Any]]) -> List:
        """Создает секцию со списком проанализированных документов"""
        elements = []
        
        elements.append(PageBreak())
        elements.append(Paragraph("Проанализированные документы", self.styles['CustomHeading1']))
        
        if not documents:
            elements.append(Paragraph("Документы для анализа не найдены.", 
                                    self.styles['CustomNormal']))
            return elements
        
        for i, doc in enumerate(documents, 1):
            elements.append(Paragraph(f"<b>Документ {i}:</b> {doc.get('name', 'Неизвестный документ')}", 
                                    self.styles['CustomNormal']))
            
            doc_type = doc.get('type', 'unknown')
            
            if doc_type == 'file':
                format_info = doc.get('format', 'неизвестный формат')
                elements.append(Paragraph(f"<b>Тип:</b> Файл ({format_info})", 
                                        self.styles['CustomNormal']))
                
                # Размер файла (если есть)
                size_bytes = doc.get('size_bytes', 0)
                if size_bytes > 0:
                    # Конвертируем байты в более читаемый формат
                    if size_bytes >= 1024*1024:
                        size_str = f"{size_bytes / (1024*1024):.1f} МБ"
                    elif size_bytes >= 1024:
                        size_str = f"{size_bytes / 1024:.1f} КБ"
                    else:
                        size_str = f"{size_bytes} байт"
                    
                    elements.append(Paragraph(f"<b>Размер файла:</b> {size_str}", 
                                            self.styles['CustomNormal']))
                
            elif doc_type == 'confluence':
                elements.append(Paragraph(f"<b>Тип:</b> Confluence страница", 
                                        self.styles['CustomNormal']))
                
                url = doc.get('url', '')
                if url:
                    elements.append(Paragraph(f"<b>URL:</b> {url}", 
                                            self.styles['CustomNormal']))
                
                last_modified = doc.get('last_modified', '')
                if last_modified:
                    elements.append(Paragraph(f"<b>Последнее изменение:</b> {last_modified}", 
                                            self.styles['CustomNormal']))
            
            # Количество страниц
            pages = doc.get('pages', 0)
            if pages > 0:
                elements.append(Paragraph(f"<b>Количество страниц:</b> {pages}", 
                                        self.styles['CustomNormal']))
            
            # Длина текста
            text_length = doc.get('text_length', 0)
            if text_length > 0:
                elements.append(Paragraph(f"<b>Объем текста:</b> {text_length:,} символов", 
                                        self.styles['CustomNormal']))
            
            elements.append(Spacer(1, 15))
        
        return elements 