"""
Callbacks для загрузки файлов
"""
import base64
import threading
import time
from dash import Input, Output, State, html
import dash_bootstrap_components as dbc
from flask import session
from utils.database import DatabaseManager
from utils.parsers import LogParser
import config
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

# Глобальные переменные для отслеживания прогресса
processing_state = {
    'is_processing': False,
    'progress': 0,
    'current_file': '',
    'total_records': 0,
    'current_records': 0,
    'status': '',
    'last_update': time.time(),
    'files_queue': Queue(),
    'active_files': {},
    'completed_files': []
}

# Пул потоков для параллельной обработки файлов
executor = ThreadPoolExecutor(max_workers=3)  # Максимум 3 файла одновременно

db_manager = DatabaseManager()
audit_logger = None
try:
    from utils.audit_logger import AuditLogger
    audit_logger = AuditLogger()
except Exception:
    audit_logger = None


def background_file_processing(contents, filename, owner_email: str):
    """Фоновая обработка файла в отдельном потоке"""
    global processing_state
    
    def update_progress(progress, records, status):
        if filename in processing_state.get('active_files', {}):
            processing_state['active_files'][filename]['progress'] = progress
            processing_state['active_files'][filename]['records'] = records
            processing_state['active_files'][filename]['status'] = status
        processing_state['last_update'] = time.time()
    
    def fail(msg):
        update_progress(0, 0, f"Ошибка: {msg}")
        processing_state['status'] = f"Ошибка: {msg}"
        processing_state.setdefault('completed_files', []).append({
            'filename': filename, 'records': 0, 'status': 'error', 'error': msg
        })
        if audit_logger:
            audit_logger.log(
                action="upload_file",
                user_email=owner_email,
                status="error",
                metadata={"filename": filename, "error": msg},
            )
        if filename in processing_state.get('active_files', {}):
            del processing_state['active_files'][filename]
        processing_state['is_processing'] = not bool(processing_state.get('active_files'))
        print(f"❌ {filename}: {msg}")
    
    try:
        if not db_manager.is_connected():
            fail("Нет подключения к MongoDB. Запустите MongoDB и нажмите «Обновить список».")
            return
        
        if filename not in processing_state.get('active_files', {}):
            processing_state.setdefault('active_files', {})[filename] = {
                'status': 'Начата обработка...',
                'progress': 0,
                'records': 0
            }
        
        processing_state['is_processing'] = True
        processing_state['current_file'] = filename
        processing_state['progress'] = 0
        processing_state['current_records'] = 0
        processing_state['status'] = f'Обработка {filename}...'
        processing_state['last_update'] = time.time()
        
        print(f"🎬 Запуск фоновой обработки для: {filename}")
        
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Обработка Excel (.xlsx)
        if filename.lower().endswith('.xlsx'):
            update_progress(10, 0, "Чтение Excel...")
            normalized_list = LogParser.parse_xlsx_file(decoded, filename)
            total = len(normalized_list)
            if total == 0:
                update_progress(0, 0, "Не удалось прочитать данные из Excel или файл пуст")
                processing_state.setdefault('completed_files', []).append({
                    'filename': filename, 'records': 0, 'status': 'error', 'error': 'Нет данных'
                })
                if audit_logger:
                    audit_logger.log(
                        action="upload_file",
                        user_email=owner_email,
                        status="error",
                        metadata={"filename": filename, "error": "No xlsx data"},
                    )
                if filename in processing_state.get('active_files', {}):
                    del processing_state['active_files'][filename]
                return
            batch_size = config.BATCH_SIZE
            for i in range(0, total, batch_size):
                batch = normalized_list[i:i + batch_size]
                raw_lines = [r.get('raw_message') or str(r) for r in batch]
                db_manager.save_logs_batch(
                    filename=filename,
                    log_format='xlsx',
                    raw_lines=raw_lines,
                    normalized_records=batch,
                    owner_email=owner_email,
                )
                progress = 10 + int((i + len(batch)) / total * 85)
                update_progress(min(progress, 95), i + len(batch), f"Обработано {i + len(batch)} из {total} записей")
            update_progress(100, total, f"Успешно загружено {total} записей")
            processing_state['status'] = f"Успешно загружено {total} записей из файла {filename}"
            processing_state.setdefault('completed_files', []).append({
                'filename': filename, 'records': total, 'status': 'success'
            })
            if filename in processing_state.get('active_files', {}):
                del processing_state['active_files'][filename]
            processing_state['is_processing'] = not bool(processing_state.get('active_files'))
            print(f"✅ Excel загружен: {filename}, записей: {total}")
            if audit_logger:
                audit_logger.log(
                    action="upload_file",
                    user_email=owner_email,
                    status="success",
                    metadata={"filename": filename, "records": total},
                )
            return
        
        # Определение типа файла (текст/лог)
        text_content = decoded.decode('utf-8', errors='ignore')
        lines = text_content.split('\n')
        total_lines = len([l for l in lines if l.strip()])
        
        update_progress(5, 0, f"Определение типа файла...")
        
        # Определение типа лога
        log_type = None
        csv_headers = None
        if filename.endswith('.csv') and lines:
            try:
                import csv as csv_module
                reader = csv_module.reader([lines[0]])
                csv_headers = next(reader)
                log_type = 'csv'
            except:
                pass
        
        if log_type is None and lines:
            log_type = LogParser.detect_log_type(lines[0])
        
        update_progress(10, 0, f"Тип файла: {log_type}, строк: {total_lines}")
        
        # Обработка файла с сохранением на всех трех уровнях
        raw_lines_batch = []
        normalized_batch = []
        batch_size = config.BATCH_SIZE
        processed = 0
        
        for line_num, line in enumerate(lines, 1):
            if line.strip():
                # Сохраняем сырую строку
                raw_lines_batch.append(line)
                
                # Парсим и нормализуем
                parsed = LogParser.parse_line(line, filename, log_type, csv_headers)
                if parsed:
                    normalized_batch.append(parsed)
                    processed += 1
                    
                    # Сохраняем батчами на всех уровнях
                    if len(normalized_batch) >= batch_size:
                        db_manager.save_logs_batch(
                            filename=filename,
                            log_format=log_type,
                            raw_lines=raw_lines_batch,
                            normalized_records=normalized_batch,
                            owner_email=owner_email,
                        )
                        raw_lines_batch = []
                        normalized_batch = []
                        
                        progress = 10 + int((processed / total_lines) * 85) if total_lines > 0 else 10
                        update_progress(
                            min(progress, 95),
                            processed,
                            f"Обработано {processed} из {total_lines} строк"
                        )
        
        # Последний батч
        if normalized_batch:
            db_manager.save_logs_batch(
                filename=filename,
                log_format=log_type,
                raw_lines=raw_lines_batch,
                normalized_records=normalized_batch,
                owner_email=owner_email,
            )
        
        update_progress(100, processed, f"Успешно загружено {processed} записей")
        processing_state['status'] = f"Успешно загружено {processed} записей из файла {filename}"
        if audit_logger:
            audit_logger.log(
                action="upload_file",
                user_email=owner_email,
                status="success",
                metadata={"filename": filename, "records": processed},
            )
        
        # Добавляем в список завершенных
        processing_state.setdefault('completed_files', []).append({
            'filename': filename,
            'records': processed,
            'status': 'success'
        })
        
        print(f"✅ Фоновая обработка завершена для: {filename}")
        
    except Exception as e:
        import traceback
        error_msg = f"Ошибка при обработке {filename}: {str(e)}"
        update_progress(0, 0, error_msg)
        processing_state['status'] = error_msg
        processing_state.setdefault('completed_files', []).append({
            'filename': filename, 'records': 0, 'status': 'error', 'error': str(e)
        })
        print(f"❌ {error_msg}")
        traceback.print_exc()
        if audit_logger:
            audit_logger.log(
                action="upload_file",
                user_email=owner_email,
                status="error",
                metadata={"filename": filename, "error": str(e)},
            )
    finally:
        # Удаляем из активных файлов
        if filename in processing_state.get('active_files', {}):
            del processing_state['active_files'][filename]
        
        # Если больше нет активных файлов, сбрасываем флаг обработки
        if not processing_state.get('active_files', {}):
            processing_state['is_processing'] = False
            processing_state['progress'] = 100


def register_upload_callbacks(app):
    """Регистрация callbacks для загрузки"""
    
    @app.callback(
        Output('upload-status', 'children', allow_duplicate=True),
        Input('upload-data', 'contents'),
        State('upload-data', 'filename'),
        prevent_initial_call=True
    )
    def handle_file_upload(contents_list, filename_list):
        owner_email = session.get("user_email")
        if not owner_email:
            return dbc.Alert("Необходимо войти в систему", color="danger")

        if contents_list is None or filename_list is None:
            return dbc.Alert("Файл не выбран", color="warning")
        
        # Поддержка как одного файла, так и списка файлов
        if not isinstance(contents_list, list):
            contents_list = [contents_list]
            filename_list = [filename_list]
        
        valid_files = []
        invalid_files = []
        
        # Проверка всех файлов
        for contents, filename in zip(contents_list, filename_list):
            if contents is None or filename is None:
                continue
                
            # Проверка формата файла
            file_ext = '.' + filename.split('.')[-1] if '.' in filename else ''
            if file_ext not in config.SUPPORTED_FORMATS:
                invalid_files.append(filename)
            else:
                valid_files.append((contents, filename))
        
        if not valid_files:
            return dbc.Alert(
                f"Нет валидных файлов для обработки. Неподдерживаемые: {', '.join(invalid_files)}" if invalid_files else "Файл не выбран",
                color="warning"
            )
        
        if not db_manager.is_connected():
            return dbc.Alert(
                "Нет подключения к MongoDB. Запустите MongoDB (например: mongod), затем нажмите «Обновить список» на этой странице.",
                color="danger"
            )
        
        alerts = []
        if invalid_files:
            alerts.append(dbc.Alert(
                f"Пропущены файлы с неподдерживаемым форматом: {', '.join(invalid_files)}",
                color="warning",
                className="mb-2"
            ))
        
        for contents, filename in valid_files:
            print(f"📥 Получен файл для обработки: {filename}")
            if audit_logger:
                audit_logger.log(
                    action="upload_file_started",
                    user_email=owner_email,
                    status="success",
                    metadata={"filename": filename},
                )
            
            # Добавляем файл в очередь обработки
            processing_state['files_queue'].put((contents, filename))
            processing_state['active_files'][filename] = {
                'status': 'В очереди',
                'progress': 0,
                'records': 0
            }
            
            # Запускаем обработку через пул потоков
            future = executor.submit(background_file_processing, contents, filename, owner_email)
            future.add_done_callback(lambda f, fn=filename: processing_state['active_files'].pop(fn, None))
        
        # Сообщение "Запущена обработка..." убираем из `upload-status`,
        # чтобы оно не оставалось на экране после завершения фоновой обработки.
        # Ход обработки отображается через progress bar и `processing-status`.
        return html.Div(alerts) if len(alerts) > 1 else (alerts[0] if alerts else "")
    
    @app.callback(
        [
            Output('progress-bar', 'value'),
            Output('progress-bar', 'label'),
            Output('progress-text', 'children'),
            Output('processing-status', 'children'),
        ],
        Input('progress-interval', 'n_intervals'),
    )
    def update_progress_display(n):
        global processing_state
        
        # Проверяем активные файлы
        active_files = processing_state.get('active_files', {})
        completed_files = processing_state.get('completed_files', [])

        if active_files or processing_state.get('is_processing', False):
            # Если обрабатывается несколько файлов, показываем общий прогресс
            if len(active_files) > 1:
                total_progress = sum(f.get('progress', 0) for f in active_files.values())
                avg_progress = total_progress / len(active_files) if active_files else 0
                total_records = sum(f.get('records', 0) for f in active_files.values())
                
                files_info = []
                for filename, info in active_files.items():
                    status_color = "success" if "успешно" in info.get('status', '').lower() else "info"
                    files_info.append(
                        dbc.Alert(
                            f"{filename}: {info.get('status', 'Обработка...')} ({info.get('progress', 0):.0f}%)",
                            color=status_color,
                            className="mb-1"
                        )
                    )
                
                progress_text = f"Обрабатывается {len(active_files)} файл(ов) | Всего записей: {total_records}"
                status_display = html.Div(files_info)
                return avg_progress, f"{avg_progress:.1f}%", progress_text, status_display
            else:
                # Один файл - показываем как раньше
                if processing_state.get('is_processing', False):
                    progress = processing_state.get('progress', 0)
                    records = processing_state.get('current_records', 0)
                    status = processing_state.get('status', '')
                    current_file = processing_state.get('current_file', '')
                    
                    progress_text = f"Файл: {current_file} | Записей: {records}"
                    
                    if "Успешно" in status or "успешно" in status.lower():
                        status_display = dbc.Alert(status, color="success")
                    elif "Ошибка" in status or "ошибка" in status.lower():
                        status_display = dbc.Alert(status, color="danger")
                    else:
                        status_display = dbc.Alert(status, color="info")
                    return progress, f"{progress:.1f}%", progress_text, status_display
        
        return 0, "0%", "", ""
    
    @app.callback(
        Output('connection-status', 'children'),
        Input('refresh-btn', 'n_clicks'),
        Input('upload-data', 'contents')
    )
    def update_connection_status(n_clicks, contents):
        # Скрываем статус подключения от пользователей
        return html.Div(style={'display': 'none'})

