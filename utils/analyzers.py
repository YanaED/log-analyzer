"""
Модуль для анализа данных логов
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import Counter
import re


class LogAnalyzer:
    """Класс для анализа данных логов"""
    
    @staticmethod
    def extract_basic_info(df: pd.DataFrame) -> Dict:
        """Извлечение базовой информации из логов"""
        info = {
            'total_records': len(df),
            'unique_ips': 0,
            'unique_urls': 0,
            'error_count': 0,
            'warning_count': 0,
            'date_range': None
        }
        
        if 'ip_address' in df.columns:
            info['unique_ips'] = df['ip_address'].notna().sum()
        
        if 'url' in df.columns:
            info['unique_urls'] = df['url'].notna().nunique()
        
        if 'level' in df.columns:
            level_counts = df['level'].value_counts()
            info['error_count'] = level_counts.get('ERROR', 0)
            info['warning_count'] = level_counts.get('WARNING', 0)
        
        if 'timestamp' in df.columns:
            timestamps = pd.to_datetime(df['timestamp'], errors='coerce')
            valid_timestamps = timestamps.dropna()
            if not valid_timestamps.empty:
                info['date_range'] = {
                    'start': valid_timestamps.min(),
                    'end': valid_timestamps.max()
                }
        
        return info
    
    @staticmethod
    def get_request_frequency(df: pd.DataFrame, interval: str = '1H') -> pd.DataFrame:
        """Определение частоты запросов по времени"""
        if 'timestamp' not in df.columns:
            return pd.DataFrame()
        
        df_copy = df.copy()
        df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], errors='coerce')
        df_copy = df_copy.dropna(subset=['timestamp'])
        
        if df_copy.empty:
            return pd.DataFrame()
        
        df_copy.set_index('timestamp', inplace=True)
        frequency = df_copy.resample(interval).size().reset_index(name='count')
        frequency.columns = ['timestamp', 'count']
        
        return frequency
    
    @staticmethod
    def identify_error_requests(df: pd.DataFrame) -> pd.DataFrame:
        """Выявление ошибочных запросов"""
        error_conditions = []
        
        # По уровню логирования
        if 'level' in df.columns:
            error_conditions.append(df['level'].isin(['ERROR', 'FATAL']))
        
        # По HTTP статус-коду
        if 'http_status' in df.columns:
            error_conditions.append(df['http_status'] >= 400)
        
        if error_conditions:
            error_mask = pd.concat(error_conditions, axis=1).any(axis=1)
            return df[error_mask].copy()
        
        return pd.DataFrame()
    
    @staticmethod
    def get_statistics(df: pd.DataFrame) -> Dict:
        """Получение статистики по логам"""
        stats = {
            'total': len(df),
            'by_level': {},
            'by_status': {},
            'by_ip': {},
            'by_url': {},
            'time_distribution': {}
        }
        
        # Статистика по уровням
        if 'level' in df.columns:
            stats['by_level'] = df['level'].value_counts().to_dict()
        
        # Статистика по HTTP статусам
        if 'http_status' in df.columns:
            stats['by_status'] = df['http_status'].value_counts().to_dict()
        
        # Топ IP-адресов
        if 'ip_address' in df.columns:
            stats['by_ip'] = df['ip_address'].value_counts().head(10).to_dict()
        
        # Топ URL
        if 'url' in df.columns:
            stats['by_url'] = df['url'].value_counts().head(10).to_dict()
        
        # Распределение по времени (часы дня)
        if 'timestamp' in df.columns:
            timestamps = pd.to_datetime(df['timestamp'], errors='coerce')
            valid_timestamps = timestamps.dropna()
            if not valid_timestamps.empty:
                stats['time_distribution'] = valid_timestamps.dt.hour.value_counts().sort_index().to_dict()
        
        return stats
    
    @staticmethod
    def get_geography_by_ip(df: pd.DataFrame) -> Dict:
        """Получение географии запросов по IP-адресам"""
        if 'ip_address' not in df.columns:
            return {}
        
        ip_counts = df['ip_address'].value_counts().head(20)
        
        # Группировка по первым октетам IP (упрощенная география)
        geography = {}
        for ip, count in ip_counts.items():
            if pd.notna(ip):
                # Берем первые два октета как "регион"
                parts = str(ip).split('.')
                if len(parts) >= 2:
                    region = f"{parts[0]}.{parts[1]}.x.x"
                    if region not in geography:
                        geography[region] = 0
                    geography[region] += count
        
        return geography
    
    @staticmethod
    def filter_logs(
        df: pd.DataFrame,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        status_code: Optional[int] = None,
        level: Optional[str] = None,
        search_text: Optional[str] = None
    ) -> pd.DataFrame:
        """Фильтрация логов по различным критериям"""
        filtered_df = df.copy()
        
        # Фильтр по дате
        if date_from or date_to:
            if 'timestamp' in filtered_df.columns:
                timestamps = pd.to_datetime(filtered_df['timestamp'], errors='coerce')
                if date_from:
                    filtered_df = filtered_df[timestamps >= date_from]
                if date_to:
                    filtered_df = filtered_df[timestamps <= date_to]
        
        # Фильтр по IP
        if ip_address:
            if 'ip_address' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['ip_address'] == ip_address]
        
        # Фильтр по статус-коду
        if status_code is not None:
            if 'http_status' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['http_status'] == status_code]
        
        # Фильтр по уровню
        if level:
            if 'level' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['level'] == level]
        
        # Поиск по тексту
        if search_text:
            mask = False
            for col in filtered_df.columns:
                if filtered_df[col].dtype == 'object':
                    mask = mask | filtered_df[col].astype(str).str.contains(
                        search_text, case=False, na=False
                    )
            filtered_df = filtered_df[mask]
        
        return filtered_df
    
    @staticmethod
    def get_top_errors(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
        """Получение топ ошибок"""
        errors = LogAnalyzer.identify_error_requests(df)
        
        if errors.empty:
            return pd.DataFrame()
        
        # Группировка по сообщению
        if 'message' in errors.columns:
            error_summary = errors.groupby('message').size().reset_index(name='count')
            error_summary = error_summary.sort_values('count', ascending=False).head(limit)
            return error_summary
        
        return errors.head(limit)

