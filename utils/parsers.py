"""
Модуль для парсинга различных форматов лог-файлов
"""
import re
import json
import csv
import io
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pandas as pd
import config


# Допустимые HTTP статус-коды по спецификации (все остальные считаются несуществующими)
VALID_HTTP_STATUS_CODES = frozenset({
    100, 101, 102, 103,  # 1xx Informational
    200, 201, 202, 203, 204, 205, 206, 207, 208, 226,  # 2xx Success
    300, 301, 302, 303, 304, 305, 306, 307, 308,  # 3xx Redirection
    400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415,
    416, 417, 418, 419, 421, 422, 423, 424, 425, 426, 428, 429, 431, 449, 451, 499,  # 4xx Client Error
    500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511,  # 5xx Server Error
    520, 521, 522, 523, 524, 525, 526,  # Cloudflare / расширения
})


class LogParser:
    """Класс для парсинга различных форматов логов"""
    
    # Шаблоны для определения типа лога
    APACHE_PATTERN = re.compile(r'(\d+\.\d+\.\d+\.\d+) - - \[([^\]]+)\] "([^"]+)" (\d+)')
    NGINX_PATTERN = re.compile(r'(\d+\.\d+\.\d+\.\d+) - - \[([^\]]+)\] "([^"]+)" (\d+)')
    JSON_PATTERN = re.compile(r'\{.*\}')
    # BGL (Blue Gene/L) HPC: RecordID node-N category event_type unix_timestamp severity [message]
    BGL_PATTERN = re.compile(r'^\d+\s+node-\d+\s+\S+\s+\S+\s+\d+\s+\d+\s')
    
    # Шаблоны для timestamp
    TIMESTAMP_PATTERNS = [
        (r'\[(\w+\s+\w+\s+\d+\s+\d+:\d+:\d+\s+\d+)\]', '%a %b %d %H:%M:%S %Y'),
        (r'\[(\d{2}/\w+/\d{4}:\d{2}:\d{2}:\d{2})', '%d/%b/%Y:%H:%M:%S'),
        (r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', '%Y-%m-%d %H:%M:%S'),
        (r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})', '%d/%m/%Y %H:%M:%S'),
        (r'(\w+\s+\d+\s+\d+:\d+:\d+)', '%b %d %H:%M:%S'),
    ]
    
    # Шаблоны для уровней логирования
    LEVEL_PATTERNS = {
        'ERROR': r'error|ERROR|Error|ERROR|FATAL|Fatal|fatal',
        'WARNING': r'warning|WARNING|Warning|WARN|Warn|warn',
        'DEBUG': r'debug|DEBUG|Debug',
        'INFO': r'info|INFO|Info'
    }
    
    @staticmethod
    def detect_log_type(line: str) -> str:
        """Определение типа лога по строке"""
        line = line.strip()
        
        # Проверка на JSON
        if line.startswith('{') or line.startswith('['):
            try:
                json.loads(line)
                return 'json'
            except:
                pass
        
        # Проверка на Apache/Nginx
        if LogParser.APACHE_PATTERN.match(line):
            return 'apache'
        
        # Проверка на BGL (Blue Gene/L) HPC: RecordID node-N category event_type unix_ts severity message
        if LogParser.BGL_PATTERN.match(line):
            return 'bgl'
        
        # Проверка на CSV
        if ',' in line and len(line.split(',')) > 2:
            return 'csv'
        
        # По умолчанию - текстовый лог
        return 'text'
    
    @staticmethod
    def parse_timestamp(line: str) -> Optional[datetime]:
        """Извлечение временной метки из строки"""
        for pattern, fmt in LogParser.TIMESTAMP_PATTERNS:
            match = re.search(pattern, line)
            if match:
                try:
                    date_str = match.group(1)
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        return None
    
    @staticmethod
    def parse_level(line: str) -> str:
        """Извлечение уровня логирования"""
        for level, pattern in LogParser.LEVEL_PATTERNS.items():
            if re.search(pattern, line, re.IGNORECASE):
                return level
        return 'INFO'
    
    @staticmethod
    def parse_ip_address(line: str) -> Optional[str]:
        """Извлечение IP-адреса"""
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        match = re.search(ip_pattern, line)
        return match.group(0) if match else None
    
    @staticmethod
    def parse_http_status(line: str) -> Optional[int]:
        """Извлечение HTTP статус-кода. Учитываются только реально существующие коды."""
        # Важно: в "текстовых" логах встречаются любые числа (например, PID/slot/child id),
        # которые по формату похожи на HTTP-коды (например, 308). Поэтому сначала проверяем,
        # что строка действительно содержит признаки HTTP-контекста.
        has_http_context = bool(
            re.search(r'\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\b', line, re.IGNORECASE)
            or re.search(r'\bHTTP/', line, re.IGNORECASE)
            or re.search(r'\bstatus\b', line, re.IGNORECASE)
            or re.search(r'\bstatus[_\-\s]*code\b', line, re.IGNORECASE)
            or re.search(r'\bcode\b\s*=?\s*\d{3}\b', line, re.IGNORECASE)
            or re.search(r'response\s+status', line, re.IGNORECASE)
        )

        if not has_http_context:
            return None

        status_pattern = r'\b(?:1\d{2}|2\d{2}|3\d{2}|4\d{2}|5\d{2})\b'
        match = re.search(status_pattern, line)
        if not match:
            return None

        try:
            code = int(match.group(0))
        except (ValueError, TypeError):
            return None

        return code if code in VALID_HTTP_STATUS_CODES else None
    
    @staticmethod
    def parse_url(line: str) -> Optional[str]:
        """Извлечение URL из строки"""
        url_patterns = [
            r'"(GET|POST|PUT|DELETE|PATCH)\s+([^\s"]+)"',
            r'https?://[^\s"]+',
            r'/[^\s"]+',
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, line)
            if match:
                if len(match.groups()) > 1:
                    return match.group(2)
                return match.group(0)
        return None
    
    @staticmethod
    def parse_apache_log(line: str, filename: str) -> Optional[Dict]:
        """Парсинг Apache/Nginx лога"""
        match = LogParser.APACHE_PATTERN.match(line)
        if not match:
            return None
        
        ip = match.group(1)
        timestamp_str = match.group(2)
        request = match.group(3)
        status = int(match.group(4))
        
        # Парсинг timestamp
        timestamp = None
        try:
            timestamp = datetime.strptime(timestamp_str, '%d/%b/%Y:%H:%M:%S %z')
        except:
            try:
                timestamp = datetime.strptime(timestamp_str, '%d/%b/%Y:%H:%M:%S')
            except:
                pass
        
        # Парсинг метода и URL из request
        method = None
        url = None
        if request:
            parts = request.split()
            if len(parts) >= 2:
                method = parts[0]
                url = parts[1]
        
        result = {
            'raw_message': line,
            'file_source': filename,
            'uploaded_at': datetime.now(),
            'timestamp': timestamp,
            'ip_address': ip,
            'http_method': method,
            'url': url,
            'level': 'ERROR' if (status is not None and status >= 400) else 'INFO',
            'message': line
        }
        if status is not None:
            result['http_status'] = status
        return result
    
    # Уровень серьёзности BGL: 1 — Fatal/Error, 2 — Warning, иначе Info
    BGL_SEVERITY_TO_LEVEL = {1: 'ERROR', 2: 'WARNING'}
    
    @staticmethod
    def parse_bgl_log(line: str, filename: str) -> Optional[Dict]:
        """Парсинг лога BGL (Blue Gene/L) HPC: RecordID node-N category event_type unix_ts severity message"""
        parts = line.strip().split(None, 6)
        if len(parts) < 6:
            return None
        try:
            record_id = int(parts[0])
            unix_ts = int(parts[4])
            severity = int(parts[5])
        except (ValueError, IndexError):
            return None
        node = parts[1]
        category = parts[2]
        event_type = parts[3]
        message = (parts[6].strip() if len(parts) > 6 else "") or line.strip()
        timestamp = datetime.utcfromtimestamp(unix_ts)
        level = LogParser.BGL_SEVERITY_TO_LEVEL.get(severity, 'INFO')
        return {
            'raw_message': line,
            'file_source': filename,
            'uploaded_at': datetime.now(),
            'timestamp': timestamp,
            'record_id': record_id,
            'node': node,
            'category': category,
            'event_type': event_type,
            'severity': severity,
            'level': level,
            'message': message or line.strip(),
        }
    
    @staticmethod
    def parse_json_log(line: str, filename: str) -> Optional[Dict]:
        """Парсинг JSON лога"""
        try:
            data = json.loads(line)
            log_entry = {
                'raw_message': line,
                'file_source': filename,
                'uploaded_at': datetime.now(),
                'message': line
            }
            
            # Извлечение стандартных полей
            if 'timestamp' in data:
                try:
                    log_entry['timestamp'] = datetime.fromisoformat(str(data['timestamp']).replace('Z', '+00:00'))
                except:
                    pass
            
            if 'time' in data:
                try:
                    log_entry['timestamp'] = datetime.fromisoformat(str(data['time']).replace('Z', '+00:00'))
                except:
                    pass
            
            if 'level' in data:
                log_entry['level'] = str(data['level']).upper()
            else:
                log_entry['level'] = LogParser.parse_level(line)
            
            if 'ip' in data or 'ip_address' in data:
                log_entry['ip_address'] = str(data.get('ip') or data.get('ip_address'))
            
            if 'status' in data or 'status_code' in data:
                log_entry['http_status'] = int(data.get('status') or data.get('status_code'))
            
            if 'url' in data or 'path' in data:
                log_entry['url'] = str(data.get('url') or data.get('path'))
            
            # Добавляем все остальные поля
            for key, value in data.items():
                if key not in log_entry:
                    log_entry[key] = value
            
            return log_entry
        except json.JSONDecodeError:
            return None
    
    @staticmethod
    def parse_csv_log(line: str, filename: str, headers: Optional[List[str]] = None) -> Optional[Dict]:
        """Парсинг CSV лога"""
        try:
            reader = csv.reader([line])
            row = next(reader)
            
            if not headers:
                return None
            
            log_entry = {
                'raw_message': line,
                'file_source': filename,
                'uploaded_at': datetime.now(),
                'message': line
            }
            
            for i, header in enumerate(headers):
                if i < len(row):
                    value = row[i]
                    
                    # Специальная обработка для известных полей
                    if header.lower() in ['timestamp', 'time', 'date']:
                        try:
                            log_entry['timestamp'] = pd.to_datetime(value)
                        except:
                            pass
                    elif header.lower() in ['ip', 'ip_address']:
                        log_entry['ip_address'] = value
                    elif header.lower() in ['status', 'status_code']:
                        try:
                            code = int(value)
                            if code in VALID_HTTP_STATUS_CODES:
                                log_entry['http_status'] = code
                        except (ValueError, TypeError):
                            pass
                    elif header.lower() in ['level', 'log_level']:
                        log_entry['level'] = value.upper()
                    else:
                        log_entry[header] = value
            
            if 'level' not in log_entry:
                log_entry['level'] = LogParser.parse_level(line)
            
            return log_entry
        except:
            return None
    
    @staticmethod
    def parse_text_log(line: str, filename: str) -> Dict:
        """Парсинг обычного текстового лога"""
        line = line.strip()
        if not line:
            return None
        
        log_entry = {
            'raw_message': line,
            'file_source': filename,
            'uploaded_at': datetime.now(),
            'timestamp': LogParser.parse_timestamp(line),
            'level': LogParser.parse_level(line),
            'message': line
        }
        
        # Попытка извлечь дополнительные данные
        ip = LogParser.parse_ip_address(line)
        if ip:
            log_entry['ip_address'] = ip
        
        status = LogParser.parse_http_status(line)
        if status:
            log_entry['http_status'] = status
        
        url = LogParser.parse_url(line)
        if url:
            log_entry['url'] = url
        
        return log_entry
    
    @staticmethod
    def parse_line(line: str, filename: str, log_type: Optional[str] = None, csv_headers: Optional[List[str]] = None) -> Optional[Dict]:
        """Универсальный метод парсинга строки лога"""
        if not line.strip():
            return None
        
        if log_type is None:
            log_type = LogParser.detect_log_type(line)
        
        if log_type == 'apache':
            return LogParser.parse_apache_log(line, filename)
        elif log_type == 'bgl':
            return LogParser.parse_bgl_log(line, filename)
        elif log_type == 'json':
            return LogParser.parse_json_log(line, filename)
        elif log_type == 'csv':
            return LogParser.parse_csv_log(line, filename, csv_headers)
        else:
            return LogParser.parse_text_log(line, filename)
    
    # Маппинг колонок Excel (типичные имена + колонки из файлов компании) -> наша схема
    XLSX_COLUMN_MAP = {
        'timestamp': ['timegenerated', 'time_generated', 'timecreated', 'time_created', 'eventtime', 'event_time', 'date', 'time', 'timestamp', 'datetime', 'created', 'modified', 'createdate', 'время', 'дата'],
        'message': ['message', 'description', 'text', 'details', 'summary', 'comment', 'logmessage', 'log_message', 'content', 'сообщение', 'описание'],
        'level': ['level', 'leveldisplayname', 'level_display_name', 'severity', 'type', 'eventtype', 'event_type', 'levelname', 'уровень', 'тип'],
        'ip_address': ['computer', 'sourceip', 'source_ip', 'ip', 'host', 'clientip', 'client_ip', 'sourcecomputer', 'hostname', 'source', 'компьютер', 'источник', 'ip-адрес_пользователя', 'ip_адрес_пользователя'],
        'http_status': ['status', 'statuscode', 'status_code', 'httpstatus', 'code', 'статус'],
        'url': ['url', 'path', 'requestpath', 'request_path', 'uri', 'address', 'путь'],
        # Доп. колонки из файлов компании (сохраняются и отображаются в таблице)
        'user': ['user', 'username', 'пользователь'],
        'server': ['server', 'сервер', 'host', 'computer'],
        'event_class': ['eventclass', 'event_class', 'класс_события'],
        'event_type': ['eventtype', 'event_type', 'тип_события'],
        'importance': ['importance', 'важность'],
        'protection_object': ['protectionobject', 'protection_object', 'объект_защиты'],
        'protection_object_address': ['protectionobjectaddress', 'protection_object_address', 'адрес_объекта_защиты'],
    }
    
    @staticmethod
    def parse_xlsx_file(contents_bytes: bytes, filename: str) -> List[Dict]:
        """Чтение Excel (.xlsx) и преобразование в список нормализованных записей логов.
        Поддерживаются типичные колонки экспортов (TimeGenerated, Message, Computer, Level и т.д.).
        """
        import io
        records = []
        try:
            df = pd.read_excel(io.BytesIO(contents_bytes), sheet_name=0, engine='openpyxl')
        except Exception as e:
            print(f"Ошибка чтения Excel {filename}: {e}")
            return records
        if df.empty:
            return records
        # Нормализуем имена колонок: lowercase, пробелы -> подчёркивание
        col_map = {str(c).strip().lower().replace(' ', '_'): c for c in df.columns}
        # Определяем, какая колонка куда маппится
        target_to_col = {}
        for target, candidates in LogParser.XLSX_COLUMN_MAP.items():
            for cand in candidates:
                if cand in col_map:
                    target_to_col[target] = col_map[cand]
                    break
        # Конвертируем даты в первом столбце, если он похож на время
        for target, orig_name in target_to_col.items():
            if target == 'timestamp' and orig_name in df.columns:
                df[orig_name] = pd.to_datetime(df[orig_name], errors='coerce')
                break
        for idx, row in df.iterrows():
            # Только обязательные служебные поля; остальные — только из колонок файла (ничего не добавляем от себя)
            rec = {
                'file_source': filename,
                'uploaded_at': datetime.now(),
            }
            # Заполняем только те поля, для которых есть колонка в файле (маппинг)
            for target, orig_name in target_to_col.items():
                val = row.get(orig_name)
                if pd.isna(val):
                    continue
                if target == 'timestamp':
                    if isinstance(val, datetime):
                        rec['timestamp'] = val
                    elif hasattr(val, 'to_pydatetime'):
                        rec['timestamp'] = val.to_pydatetime()
                    else:
                        try:
                            rec['timestamp'] = pd.to_datetime(val).to_pydatetime()
                        except Exception:
                            pass
                elif target == 'http_status':
                    try:
                        code = int(val)
                        if code in VALID_HTTP_STATUS_CODES:
                            rec['http_status'] = code
                    except (ValueError, TypeError):
                        pass
                elif target == 'level':
                    rec['level'] = str(val).strip().upper()[:20] or 'INFO'
                else:
                    rec[target] = str(val).strip() if val is not None else None
            # Описание — только содержимое столбца «Сообщение» (message), без дублирования остальных полей
            rec['description'] = (rec.get('message') or "").strip()
            records.append(rec)
        return records
    
    @staticmethod
    def parse_file_preview(contents: str, filename: str, max_lines: int = None) -> Tuple[List[Dict], str]:
        """Парсинг превью файла (первые N строк)"""
        if max_lines is None:
            max_lines = config.PREVIEW_LINES
        
        lines = contents.split('\n')[:max_lines]
        log_type = None
        csv_headers = None
        
        # Определение типа для CSV
        if filename.endswith('.csv') and lines:
            try:
                reader = csv.reader([lines[0]])
                csv_headers = next(reader)
                log_type = 'csv'
            except:
                pass
        
        # Определение типа по первой строке
        if log_type is None and lines:
            log_type = LogParser.detect_log_type(lines[0])
        
        parsed_lines = []
        for line in lines:
            if line.strip():
                parsed = LogParser.parse_line(line, filename, log_type, csv_headers)
                if parsed:
                    parsed_lines.append(parsed)
        
        return parsed_lines, log_type

