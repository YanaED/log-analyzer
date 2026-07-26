"""
Модуль для экспорта данных в различные форматы
"""
import pandas as pd
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from xml.sax.saxutils import escape
import config


class DataExporter:
    """Класс для экспорта данных"""
    
    @staticmethod
    def get_downloads_dir():
        """Получение пути к папке Загрузки пользователя"""
        home = Path.home()
        downloads = home / 'Downloads'
        
        # Создаем папку, если её нет
        downloads.mkdir(exist_ok=True)
        
        return str(downloads)
    
    @staticmethod
    def ensure_export_dir():
        """Создание директории для экспорта, если её нет"""
        # Используем папку Downloads вместо config.EXPORT_DIR
        export_dir = DataExporter.get_downloads_dir()
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        return export_dir
    
    @staticmethod
    def export_to_csv(df: pd.DataFrame, filename: Optional[str] = None) -> str:
        """Экспорт данных в CSV"""
        export_dir = DataExporter.ensure_export_dir()
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'log_export_{timestamp}.csv'
        
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        filepath = os.path.join(export_dir, filename)
        
        # Очищаем данные от проблемных символов перед экспортом
        df_clean = df.copy()
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                # Заменяем переносы строк на пробелы, чтобы не ломать CSV
                df_clean[col] = df_clean[col].astype(str).str.replace('\n', ' ', regex=False).str.replace('\r', ' ', regex=False)
        
        # Используем точку с запятой как разделитель для лучшей совместимости с Excel
        # QUOTE_ALL - все поля в кавычках гарантирует правильное разделение колонок
        import csv
        df_clean.to_csv(
            filepath, 
            index=False, 
            encoding='utf-8-sig',  # UTF-8 с BOM для Excel
            sep=';',  # Точка с запятой для лучшей совместимости
            quoting=csv.QUOTE_ALL,  # Все поля в кавычках
            lineterminator='\n',  # Правильное имя параметра
            escapechar=None  # Не используем escape-символы
        )
        
        return filepath
    
    @staticmethod
    def export_to_json(df: pd.DataFrame, filename: Optional[str] = None) -> str:
        """Экспорт данных в JSON"""
        export_dir = DataExporter.ensure_export_dir()
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'log_export_{timestamp}.json'
        
        if not filename.endswith('.json'):
            filename += '.json'
        
        filepath = os.path.join(export_dir, filename)
        df.to_json(filepath, orient='records', date_format='iso', indent=2)
        
        return filepath
    
    @staticmethod
    def export_to_pdf(df: pd.DataFrame, filename: Optional[str] = None, title: str = "Отчет по логам", 
                      stats: Optional[dict] = None, charts: Optional[list] = None) -> str:
        """Экспорт данных в PDF с графиками, таблицами и статистикой"""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import plotly.graph_objects as go
            import plotly.express as px
            import tempfile
            import io
            from PIL import Image as PILImage
            
            # Регистрация шрифтов с поддержкой кириллицы
            font_name = 'Helvetica'  # По умолчанию (fallback)
            
            try:
                import platform
                font_paths = []
                if platform.system() == 'Windows':
                    font_paths = [
                        r'C:\Windows\Fonts\arial.ttf',
                        r'C:\Windows\Fonts\calibri.ttf',
                        r'C:\Windows\Fonts\times.ttf',
                        r'C:\Windows\Fonts\arialuni.ttf',
                    ]
                elif platform.system() == 'Darwin':  # macOS
                    font_paths = [
                        '/System/Library/Fonts/Supplemental/Arial.ttf',
                        '/Library/Fonts/Arial.ttf',
                        '/System/Library/Fonts/Helvetica.ttc',
                    ]
                else:
                    # Linux: типичные пути к шрифтам с кириллицей
                    font_paths = [
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                        '/usr/share/fonts/TTF/DejaVuSans.ttf',
                    ]
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        try:
                            pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
                            font_name = 'CyrillicFont'
                            print(f"✓ Зарегистрирован шрифт с поддержкой кириллицы: {os.path.basename(font_path)}")
                            break
                        except Exception as e:
                            print(f"Не удалось зарегистрировать {os.path.basename(font_path)}: {e}")
                            continue
                if font_name == 'Helvetica':
                    print("⚠ Предупреждение: не удалось зарегистрировать шрифт с кириллицей")
                    print("  Кириллица может отображаться как квадраты в PDF")
                    print("  Рекомендуется установить шрифты с поддержкой Unicode")
                        
            except Exception as e:
                print(f"Ошибка при регистрации шрифта: {e}")
                print("Используется стандартный шрифт (кириллица может отображаться как квадраты)")
            
            export_dir = DataExporter.ensure_export_dir()
            
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'log_report_{timestamp}.pdf'
            
            if not filename.endswith('.pdf'):
                filename += '.pdf'
            
            filepath = os.path.join(export_dir, filename)
            
            # Создание PDF документа
            doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
            elements = []
            styles = getSampleStyleSheet()
            # Все текстовые стили должны использовать шрифт с кириллицей, иначе символы отображаются кубиками
            normal_cyrillic = ParagraphStyle(
                'NormalCyrillic',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=10,
                leading=12,
            )
            heading_cyrillic = ParagraphStyle(
                'HeadingCyrillic',
                parent=styles['Heading1'],
                fontName=font_name,
                fontSize=14,
            )

            # Заголовок
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName=font_name,
                fontSize=18,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 0.2*inch))
            
            # Информация о дате создания
            date_style = ParagraphStyle(
                'CustomDate',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=10,
                textColor=colors.grey,
                alignment=TA_CENTER
            )
            elements.append(Paragraph(
                f"Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                date_style
            ))
            elements.append(Spacer(1, 0.3*inch))
            
            # Статистика
            stats_style = ParagraphStyle(
                'Stats',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=12,
                spaceAfter=12,
                alignment=TA_LEFT
            )
            
            elements.append(Paragraph("<b>Статистическая информация:</b>", stats_style))
            elements.append(Paragraph(f"Всего записей: {len(df)}", stats_style))
            
            if stats:
                if 'by_level' in stats and stats['by_level']:
                    level_text = ", ".join([f"{level}: {count}" for level, count in stats['by_level'].items()])
                    elements.append(Paragraph(f"По уровням логирования: {level_text}", stats_style))
                
                if 'by_status' in stats and stats['by_status']:
                    status_text = ", ".join([f"{status}: {count}" for status, count in list(stats['by_status'].items())[:10]])
                    elements.append(Paragraph(f"По HTTP статусам: {status_text}", stats_style))
                
                if 'by_ip' in stats and stats['by_ip']:
                    top_ips = list(stats['by_ip'].items())[:5]
                    ip_text = ", ".join([f"{ip}: {count}" for ip, count in top_ips])
                    elements.append(Paragraph(f"Топ-5 IP-адресов: {ip_text}", stats_style))
                
                if 'by_url' in stats and stats['by_url']:
                    top_urls = list(stats['by_url'].items())[:5]
                    url_text = ", ".join([f"{url[:30]}...: {count}" if len(url) > 30 else f"{url}: {count}" for url, count in top_urls])
                    elements.append(Paragraph(f"Частые запросы (топ-5): {url_text}", stats_style))
            else:
                # Базовая статистика из DataFrame
                if 'level' in df.columns:
                    level_counts = df['level'].value_counts()
                    level_text = ", ".join([f"{level}: {count}" for level, count in level_counts.items()])
                    elements.append(Paragraph(f"По уровням: {level_text}", stats_style))
            
            elements.append(Spacer(1, 0.3*inch))
            
            # Добавление графиков, если они предоставлены
            temp_files_to_cleanup = []  # Список временных файлов для удаления после сборки PDF
            if charts:
                elements.append(Paragraph("<b>Графики и визуализации:</b>", stats_style))
                elements.append(Spacer(1, 0.2*inch))
                
                charts_added = 0
                for chart in charts:
                    try:
                        # Если это plotly figure
                        if hasattr(chart, 'to_image'):
                            # Сохраняем график во временный файл (kaleido может зависнуть — ограничиваем по времени не делаем, просто пропускаем при ошибке)
                            try:
                                img_bytes = chart.to_image(format="png", width=800, height=500)
                            except Exception as img_error:
                                print(f"Не удалось создать изображение графика (kaleido): {img_error}")
                                continue
                            
                            img_io = io.BytesIO(img_bytes)
                            img = PILImage.open(img_io)
                            
                            # Сохраняем во временный файл
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                            temp_file_path = temp_file.name
                            temp_file.close()
                            
                            # Сохраняем изображение
                            img.save(temp_file_path, 'PNG')
                            
                            # Используем абсолютный путь для надежности
                            abs_temp_file_path = os.path.abspath(temp_file_path)
                            
                            # Добавляем путь в список для последующей очистки
                            temp_files_to_cleanup.append(abs_temp_file_path)
                            
                            # Добавляем изображение в PDF (используем абсолютный путь)
                            pdf_img = Image(abs_temp_file_path, width=7*inch, height=4.4*inch)
                            elements.append(pdf_img)
                            elements.append(Spacer(1, 0.2*inch))
                            charts_added += 1
                    except Exception as e:
                        print(f"Ошибка при добавлении графика в PDF: {e}")
                        # Не добавляем сообщение об ошибке в PDF, просто пропускаем график
                
                if charts_added > 0:
                    elements.append(PageBreak())
            
            # Анализ аномалий (машинное обучение)
            try:
                from utils.anomaly_detection import detect_anomalies
                if len(df) >= 10:
                    anomaly_result = detect_anomalies(df, contamination=0.1)
                    if anomaly_result.get('success'):
                        n_anom = anomaly_result['n_anomalies']
                        n_total = anomaly_result['n_total']
                        elements.append(Paragraph("<b>Анализ аномалий (МО)</b>", stats_style))
                        elements.append(Spacer(1, 0.15*inch))
                        pct = (100 * n_anom / n_total) if n_total else 0
                        elements.append(Paragraph(
                            f"По методу Isolation Forest выявлено аномалий: <b>{n_anom}</b> из <b>{n_total}</b> записей ({pct:.1f}%).",
                            stats_style
                        ))
                        if n_anom > 0 and anomaly_result.get('df_flagged') is not None:
                            adf = anomaly_result['df_flagged']
                            adf = adf[adf['_anomaly'] == 1].head(5)
                            cols = [c for c in adf.columns if c not in ('_anomaly', '_anomaly_score', 'raw_message', '_anomaly_reasons') and c in adf.columns]
                            if 'timestamp' in adf.columns:
                                cols = ['timestamp'] + [c for c in cols if c != 'timestamp']
                            cols = cols[:5]
                            if '_anomaly_reasons' in adf.columns:
                                cols = cols + ['_anomaly_reasons']
                            if cols:
                                header = [c if c != '_anomaly_reasons' else 'Почему аномалия' for c in cols]
                                elements.append(Paragraph("<i>Примеры аномальных записей (первые 5):</i>", normal_cyrillic))
                                elements.append(Spacer(1, 0.1*inch))
                                anom_data = [header]
                                for _, row in adf[cols].iterrows():
                                    cell_vals = []
                                    for c in cols:
                                        val = row[c]
                                        if c == '_anomaly_reasons':
                                            cell_vals.append(str(val)[:40] + ('...' if len(str(val)) > 40 else ''))
                                        else:
                                            cell_vals.append(str(val)[:25] + ('...' if len(str(val)) > 25 else ''))
                                    anom_data.append(cell_vals)
                                anom_table = Table(anom_data)
                                anom_table.setStyle(TableStyle([
                                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                                    ('FONTSIZE', (0, 0), (-1, -1), 7),
                                    ('FONTNAME', (0, 0), (-1, -1), font_name),
                                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                                ]))
                                elements.append(anom_table)
                        elements.append(Spacer(1, 0.25*inch))
                    elif anomaly_result.get('error'):
                        elements.append(Paragraph(f"<i>Анализ аномалий: {anomaly_result['error']}</i>", normal_cyrillic))
                        elements.append(Spacer(1, 0.2*inch))
            except Exception as e:
                elements.append(Paragraph(f"<i>Анализ аномалий не выполнен: {e}</i>", normal_cyrillic))
                elements.append(Spacer(1, 0.2*inch))
            
            # Таблица данных: только первые 15 строк
            elements.append(Paragraph("<b>Таблица данных (фрагмент)</b>", stats_style))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(
                "<i>В отчёте приведены только первые 15 записей из общего набора данных.</i>",
                normal_cyrillic
            ))
            elements.append(Spacer(1, 0.2*inch))
            
            if len(df) > 0:
                PDF_TABLE_ROWS = 15
                display_df = df.head(PDF_TABLE_ROWS)
                available_width = A4[0] - doc.leftMargin - doc.rightMargin
                num_cols = len(display_df.columns)
                max_cell_width = max(15, min(int(available_width / num_cols / 6), 40))
                bold_font_name = font_name if font_name != 'Helvetica' else 'Helvetica-Bold'
                if font_name == 'CyrillicFont':
                    bold_font_name = font_name

                header_cell_style = ParagraphStyle(
                    'PdfTableHeader',
                    parent=normal_cyrillic,
                    fontName=bold_font_name,
                    fontSize=7,
                    leading=8,
                    textColor=colors.whitesmoke,
                    alignment=TA_LEFT,
                    wordWrap='CJK',
                )
                body_cell_style = ParagraphStyle(
                    'PdfTableBody',
                    parent=normal_cyrillic,
                    fontName=font_name,
                    fontSize=6,
                    leading=7,
                    alignment=TA_LEFT,
                    wordWrap='CJK',
                )

                def _to_pdf_cell_text(value, limit: int) -> str:
                    text = str(value).replace('\n', ' ').replace('\r', ' ')
                    if len(text) > limit:
                        text = text[:limit] + '...'
                    return escape(text)

                table_data = [[
                    Paragraph(_to_pdf_cell_text(col, max(12, int(max_cell_width * 0.8))), header_cell_style)
                    for col in display_df.columns
                ]]
                
                for _, row in display_df.iterrows():
                    table_data.append([
                        Paragraph(_to_pdf_cell_text(val, max_cell_width), body_cell_style)
                        for val in row.values
                    ])

                col_widths = [available_width / num_cols] * num_cols
                table = Table(table_data, colWidths=col_widths, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('TOPPADDING', (0, 0), (-1, 0), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('TOPPADDING', (0, 1), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 0.15*inch))
                elements.append(Paragraph(
                    f"<i>Показаны первые {min(PDF_TABLE_ROWS, len(df))} из {len(df)} записей.</i>",
                    normal_cyrillic
                ))
            
            # Сборка PDF
            try:
                doc.build(elements)
            finally:
                # Удаляем временные файлы после сборки PDF
                for temp_file_path in temp_files_to_cleanup:
                    try:
                        if os.path.exists(temp_file_path):
                            os.unlink(temp_file_path)
                    except Exception as e:
                        print(f"Не удалось удалить временный файл {temp_file_path}: {e}")
            
            return filepath
        except ImportError as e:
            raise ImportError(f"Для экспорта в PDF требуется библиотека reportlab и kaleido. Установите: pip install reportlab kaleido pillow. Ошибка: {e}")
    

