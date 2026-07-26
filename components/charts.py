"""
Модуль компонентов графиков и визуализаций
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import config


def create_charts_component():
    """Создание компонента графиков"""
    return dbc.Card([
        dbc.CardHeader("Визуализация данных", className="bg-info text-white"),
        dbc.CardBody([
            dbc.Tabs(id="chart-tabs", active_tab="tab-time-series"),
            html.Div(id='charts-container', className="mt-3", style={'width': '100%', 'overflow': 'visible'})
        ], style={'padding': '1rem'})
    ], className="mb-4")


def _has_column_with_data(df, col):
    """Есть ли в DataFrame колонка с хотя бы одним значением (для визуализации)."""
    if df is None or df.empty or col not in df.columns:
        return False
    s = df[col].dropna()
    if s.empty:
        return False
    # Для строк/объектов: считаем, что данные есть, если после strip() остаётся хоть одно непустое значение
    if s.dtype == object or str(s.dtype) == 'object' or (hasattr(s.dtype, 'name') and s.dtype.name == 'string'):
        return (s.astype(str).str.strip() != '').any()
    return True


def _col_with_data(df, *candidates):
    """Возвращает имя колонки из candidates, которая есть в df и в которой есть данные, или None."""
    for col in candidates:
        if _has_column_with_data(df, col):
            return col
    # Проверка по реальным колонкам (на случай других имён в данных)
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols_lower and _has_column_with_data(df, cols_lower[cand.lower()]):
            return cols_lower[cand.lower()]
    return None


def create_chart_tabs(df):
    """Вкладки только по имеющимся данным; для Excel — класс/тип события, пользователи, IP и т.д."""
    tabs = []
    if df is None or df.empty:
        return tabs
    
    available = []
    if _has_column_with_data(df, 'timestamp'):
        tabs.append(dbc.Tab(label="Временной ряд", tab_id="tab-time-series"))
        available.append('tab-time-series')
    if _has_column_with_data(df, 'level'):
        tabs.append(dbc.Tab(label="Распределение по уровням", tab_id="tab-levels"))
        available.append('tab-levels')
    if _has_column_with_data(df, 'http_status'):
        tabs.append(dbc.Tab(label="HTTP статусы", tab_id="tab-status"))
        available.append('tab-status')
    if _has_column_with_data(df, 'ip_address'):
        tabs.append(dbc.Tab(label="Топ IP-адресов", tab_id="tab-ip-top"))
        available.append('tab-ip-top')
        tabs.append(dbc.Tab(label="География запросов", tab_id="tab-geography"))
        available.append('tab-geography')
    if _has_column_with_data(df, 'url'):
        tabs.append(dbc.Tab(label="Частые запросы", tab_id="tab-urls"))
        available.append('tab-urls')
    if _col_with_data(df, 'event_class'):
        tabs.append(dbc.Tab(label="Класс события", tab_id="tab-event-class"))
        available.append('tab-event-class')
    if _col_with_data(df, 'event_type'):
        tabs.append(dbc.Tab(label="Тип события", tab_id="tab-event-type"))
        available.append('tab-event-type')
    if _col_with_data(df, 'node'):
        tabs.append(dbc.Tab(label="Узлы (node)", tab_id="tab-node"))
        available.append('tab-node')
    if _col_with_data(df, 'category'):
        tabs.append(dbc.Tab(label="Категория", tab_id="tab-category"))
        available.append('tab-category')
    if _col_with_data(df, 'user'):
        tabs.append(dbc.Tab(label="Пользователи", tab_id="tab-user"))
        available.append('tab-user')
    if _col_with_data(df, 'importance'):
        tabs.append(dbc.Tab(label="Важность", tab_id="tab-importance"))
        available.append('tab-importance')
    
    # Если ни одна стандартная вкладка не подошла — пробуем любой категориальный столбец
    if not available and len(df.columns) > 0:
        for col in df.columns:
            if _has_column_with_data(df, col):
                tabs.append(dbc.Tab(label=f"По полю «{col}»", tab_id="tab-fallback"))
                available.append("tab-fallback")
                break
    if available:
        tabs.insert(0, dbc.Tab(label="Все графики", tab_id="tab-all"))
    return tabs


def _chart_height(height=None):
    """Высота графика: переданная или из конфига."""
    return height if height is not None else config.CHART_HEIGHT


def get_time_series_figure(df, height=None):
    """
    Общая логика временного ряда. Возвращает Plotly figure или None.
    Используется и на вкладке, и в PDF-отчёте — графики совпадают.
    """
    if 'timestamp' not in df.columns or df.empty:
        return None
    try:
        df_copy = df.copy()
        ts = df_copy['timestamp']
        if ts.dtype == object or str(ts.dtype).startswith('object'):
            df_copy['timestamp'] = pd.to_datetime(ts, format='mixed', errors='coerce')
        else:
            df_copy['timestamp'] = pd.to_datetime(ts, errors='coerce')
        try:
            if hasattr(df_copy['timestamp'].dtype, 'tz') and df_copy['timestamp'].dtype.tz is not None:
                df_copy['timestamp'] = df_copy['timestamp'].dt.tz_localize(None, ambiguous='infer')
        except Exception:
            pass
        df_copy = df_copy.dropna(subset=['timestamp'])
        if df_copy.empty:
            return None
        df_copy = df_copy.sort_values('timestamp').set_index('timestamp')
        t_min, t_max = df_copy.index.min(), df_copy.index.max()
        span_seconds = (t_max - t_min).total_seconds()
        n_records = len(df_copy)
        if span_seconds <= 120:
            interval = '1s'
        elif span_seconds <= 3600:
            interval = '10s' if n_records > 300 else '1s'
        elif span_seconds < 86400:
            interval = '1min' if n_records <= 2000 else ('5min' if n_records <= 10000 else '1h')
        else:
            interval = '1D'
        time_series = df_copy.resample(interval).size().reset_index(name='count')
        time_series = time_series[time_series['count'] > 0]
        if len(time_series) > 400:
            interval = '1D'
            time_series = df_copy.resample(interval).size().reset_index(name='count')
            time_series = time_series[time_series['count'] > 0]
        if time_series.empty:
            return None
        n_points = len(time_series)
        fig = px.line(
            time_series,
            x='timestamp',
            y='count',
            title=f"Временной ряд запросов (интервал: {interval})",
            labels={'timestamp': 'Время', 'count': 'Количество запросов'}
        )
        fig.update_traces(mode='lines+markers', marker=dict(size=12 if n_points <= 50 else 8))
        if interval in ('1s', '10s') and span_seconds <= 3600:
            tick_fmt = '%H:%M:%S'
        elif interval == '1D':
            tick_fmt = '%d.%m.%Y'
        else:
            tick_fmt = '%d.%m %H:%M'
        fig.update_layout(
            height=_chart_height(height),
            xaxis=dict(tickformat=tick_fmt, dtick=None),
            xaxis_tickangle=-45 if n_points > 8 else 0
        )
        return fig
    except Exception as e:
        print(f"ERROR in get_time_series_figure: {e}")
        return None


def create_time_series_chart(df, height=None):
    """Создание графика временного ряда для вкладки (та же логика, что и в PDF)."""
    fig = get_time_series_figure(df, height=height)
    if fig is None:
        return create_empty_chart("Нет данных о временных метках или не удалось их обработать")
    return dcc.Graph(figure=fig)


def create_level_distribution_chart(df, height=None):
    """Создание графика распределения по уровням"""
    if 'level' not in df.columns or df.empty:
        return create_empty_chart("Нет данных об уровнях логирования")
    
    try:
        level_counts = df['level'].value_counts()
        fig = px.pie(
            values=level_counts.values,
            names=level_counts.index,
            title="Распределение по уровням логирования"
        )
        fig.update_layout(height=_chart_height(height))
        return dcc.Graph(figure=fig)
    except Exception as e:
        print(f"ERROR in create_level_distribution_chart: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_chart(f"Ошибка создания графика: {str(e)}")


def create_status_distribution_chart(df, height=None):
    """Создание графика распределения HTTP статусов"""
    if 'http_status' not in df.columns or df.empty:
        return create_empty_chart("Нет данных о HTTP статусах")
    
    try:
        status_counts = df['http_status'].value_counts().sort_index()
        fig = px.bar(
            x=status_counts.index.astype(str),
            y=status_counts.values,
            title="Распределение HTTP статус-кодов",
            labels={'x': 'Статус-код', 'y': 'Количество'}
        )
        fig.update_layout(height=_chart_height(height))
        return dcc.Graph(figure=fig)
    except Exception as e:
        print(f"ERROR in create_status_distribution_chart: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_chart(f"Ошибка создания графика: {str(e)}")


def _is_private_ip(ip) -> bool:
    """Проверка: локальный или частный IP (RFC 1918, localhost). Для таких геолокация невозможна."""
    if not ip or str(ip) in ('nan', 'None'):
        return True
    s = str(ip).strip()
    if s.startswith('127.'):
        return True
    if s.startswith('10.'):
        return True
    if s.startswith('192.168.'):
        return True
    if s.startswith('172.'):
        parts = s.split('.')
        if len(parts) >= 2:
            try:
                second = int(parts[1])
                if 16 <= second <= 31:
                    return True
            except ValueError:
                pass
    return False


def create_geography_chart(df, height=None):
    """Создание карты географии запросов. Публичные IP — по API, частные и при ошибке API — страна/город «Неизвестно», координаты приблизительные."""
    try:
        if 'ip_address' not in df.columns or df.empty:
            return create_empty_chart("Нет данных об IP-адресах")
        
        ip_counts = df['ip_address'].value_counts().head(20)
        ip_counts = ip_counts[[ip for ip in ip_counts.index if ip and str(ip) not in ('nan', 'None')]]
        
        if ip_counts.empty:
            return create_empty_chart("Нет данных об IP-адресах")
        
        print(f"DEBUG: Processing {len(ip_counts)} IPs for geography chart")
        
        locations = []
        ip_location_cache = {}
        api_timeout = 2
        
        for ip, count in ip_counts.items():
            try:
                if not _is_private_ip(ip) and ip not in ip_location_cache:
                    import requests
                    try:
                        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=api_timeout)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('status') == 'success':
                                ip_location_cache[ip] = {
                                    'lat': data.get('lat', 0),
                                    'lon': data.get('lon', 0),
                                    'city': data.get('city', 'Неизвестно'),
                                    'country': data.get('country', 'Неизвестно'),
                                    'region': data.get('regionName', '')
                                }
                            else:
                                ip_location_cache[ip] = None
                        else:
                            ip_location_cache[ip] = None
                    except Exception:
                        ip_location_cache[ip] = None
                
                location = ip_location_cache.get(ip) if not _is_private_ip(ip) else None
                if location:
                    locations.append({
                        'lat': location['lat'],
                        'lon': location['lon'],
                        'ip': ip,
                        'count': count,
                        'city': location['city'],
                        'country': location['country'],
                        'region': location['region']
                    })
                else:
                    # Частный IP или API не вернул данные — показываем как «Неизвестно» с приблизительными координатами
                    parts = str(ip).split('.')
                    if len(parts) == 4:
                        try:
                            lat = 55.7558 + (int(parts[0]) % 20 - 10) * 2
                            lon = 37.6173 + (int(parts[1]) % 20 - 10) * 2
                        except (ValueError, TypeError):
                            lat, lon = 55.7558, 37.6173
                    else:
                        lat, lon = 55.7558, 37.6173
                    locations.append({
                        'lat': lat,
                        'lon': lon,
                        'ip': ip,
                        'count': count,
                        'city': 'Неизвестно',
                        'country': 'Неизвестно',
                        'region': ''
                    })
            except Exception as e:
                print(f"Ошибка при получении геолокации для {ip}: {e}")
                continue
        
        if not locations:
            return create_empty_chart("Не удалось определить геолокацию IP-адресов")
        
        # Сортируем по количеству запросов (от большего к меньшему)
        locations.sort(key=lambda x: x['count'], reverse=True)
        
        # Создаем карту с помощью scatter_geo
        fig = go.Figure()
        
        lats = [loc['lat'] for loc in locations]
        lons = [loc['lon'] for loc in locations]
        ips = [loc['ip'] for loc in locations]
        counts = [loc['count'] for loc in locations]
        cities = [loc['city'] for loc in locations]
        countries = [loc['country'] for loc in locations]
        regions = [loc['region'] for loc in locations]
        
        # Находим точку с максимальным количеством запросов
        max_count = max(counts) if counts else 0
        max_count_idx = counts.index(max_count) if max_count > 0 else 0
        
        # Формируем текст для подсказок
        hover_texts = [
            f"<b>IP:</b> {ip}<br>"
            f"<b>Город:</b> {city}<br>"
            f"<b>Регион:</b> {region}<br>"
            f"<b>Страна:</b> {country}<br>"
            f"<b>Запросов:</b> {count}"
            + ("<br><b>⭐ Наибольшее количество подключений</b>" if idx == max_count_idx else "")
            for idx, (ip, city, region, country, count) in enumerate(zip(ips, cities, regions, countries, counts))
        ]
        
        # Создаем два набора точек: обычные и точка с максимальным количеством
        # Обычные точки
        normal_lats = [lats[i] for i in range(len(lats)) if i != max_count_idx]
        normal_lons = [lons[i] for i in range(len(lons)) if i != max_count_idx]
        normal_counts = [counts[i] for i in range(len(counts)) if i != max_count_idx]
        normal_hover = [hover_texts[i] for i in range(len(hover_texts)) if i != max_count_idx]
        
        if normal_lats:
            fig.add_trace(go.Scattergeo(
                lat=normal_lats,
                lon=normal_lons,
                text=normal_hover,
                mode='markers',
                marker=dict(
                    size=[min(c * 2 + 5, 40) for c in normal_counts],
                    color=normal_counts,
                    colorscale='Viridis',
                    showscale=True,  # Показываем colorbar для обычных точек
                    colorbar=dict(
                        title="Количество запросов",
                        x=0.99,  # Держим ближе к карте, чтобы не съедать ширину
                        len=0.55,
                        thickness=12,
                        xpad=2
                    ),
                    line=dict(width=1, color='white'),
                    opacity=0.6
                ),
                hovertemplate='%{text}<extra></extra>',
                name='Запросы',
                legendgroup='requests'
            ))
        
        # Точка с максимальным количеством запросов (выделяем её)
        if max_count > 0:
            # Объединяем hover текст с числом для отображения
            max_hover_text = hover_texts[max_count_idx] + f"<br><b>Отображается: {max_count}</b>"
            fig.add_trace(go.Scattergeo(
                lat=[lats[max_count_idx]],
                lon=[lons[max_count_idx]],
                text=[f"{max_count}"],
                mode='markers+text',
                marker=dict(
                    # Уменьшаем «звезду», чтобы не перекрывала карту
                    size=min(max_count * 0.6 + 12, 34),
                    color='red',
                    line=dict(width=2, color='darkred'),
                    opacity=0.9,
                    symbol='star'
                ),
                textposition="middle center",
                textfont=dict(size=10, color='white', family='Arial Black'),
                hovertemplate=max_hover_text + '<extra></extra>',
                name='Наибольшее количество',
                legendgroup='max',
                showlegend=True
            ))
        
        # Добавляем цветовую шкалу для обычных точек (если есть обычные точки)
        # Colorbar будет добавлен автоматически к первому trace с colorscale
        
        # Определяем центр карты (центр масс всех точек или точка с максимальным количеством)
        if locations:
            center_lat = lats[max_count_idx] if max_count > 0 else sum(lats) / len(lats)
            center_lon = lons[max_count_idx] if max_count > 0 else sum(lons) / len(lons)
        else:
            center_lat = 0
            center_lon = 0
        
        # Автоподгонка области карты под точки решает проблему "узкого столбика".
        projection_type = 'natural earth'
        geo_center = dict(lat=center_lat, lon=center_lon)
        
        map_height = height if height is not None else 560
        map_width = 1100
        n_shown = len(locations)
        fig.update_layout(
            title=f"География запросов по IP-адресам (показано {n_shown} точек; ⭐ — наибольшее количество)",
            height=map_height,
            width=map_width,
            geo=dict(
                projection_type=projection_type,
                showland=True,
                landcolor='rgb(243, 243, 243)',
                countrycolor='rgb(204, 204, 204)',
                showcountries=True,
                showocean=True,
                oceancolor='rgb(230, 245, 255)',
                center=geo_center,
                fitbounds="locations",
                domain=dict(x=[0.02, 0.97], y=[0.02, 0.98])  # Больше места под карту
            ),
            margin=dict(l=10, r=30, t=70, b=10),
            legend=dict(
                yanchor="top",
                y=1.02,
                xanchor="left",
                x=0.01,
                orientation="h"
            )
        )
        
        # Обновляем colorbar после создания layout
        if normal_lats and len(fig.data) > 0:
            # Обновляем colorbar для первого trace
            if hasattr(fig.data[0], 'marker') and hasattr(fig.data[0].marker, 'colorbar'):
                fig.data[0].marker.colorbar.update(
                    x=0.99,
                    len=0.55,
                    thickness=12,
                    xpad=2
                )
        
        # Отключаем некоторые интерактивные функции, которые могут вызывать проблемы
        # Устанавливаем dragmode в 'pan' для панорамирования
        fig.update_layout(
            dragmode='pan',  # Режим панорамирования
            hovermode='closest'  # Показывать подсказки только при наведении
        )
    
        return html.Div(
            dcc.Graph(
                figure=fig,
                style={
                    'width': '100%',
                    'minWidth': f'{map_width}px',
                    'height': f'{map_height}px',
                    'display': 'block'
                },
                config={
                    'displayModeBar': True,
                    'responsive': True,
                    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                    'doubleClick': 'reset',
                    'scrollZoom': True
                }
            ),
            style={
                'width': '100%',
                'minWidth': f'{map_width}px',
                'minHeight': f'{map_height}px',
                'overflow': 'visible',
                'display': 'block'
            }
        )
    except Exception as e:
        print(f"ERROR in create_geography_chart: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_chart(f"Ошибка создания карты географии: {str(e)}")


def create_top_urls_chart(df, height=None):
    """Создание графика частых запросов (URL)"""
    if 'url' not in df.columns or df.empty:
        return create_empty_chart("Нет данных об URL")
    
    try:
        all_urls = df['url'].value_counts()
        total = len(all_urls)
        url_counts = all_urls.head(10)
        top_n = 10
        if total > top_n:
            title = f"Частые запросы (топ-{top_n} из {total})"
        else:
            title = f"Частые запросы (всего {total})"
        fig = px.bar(
            x=url_counts.values,
            y=url_counts.index,
            orientation='h',
            title=title,
            labels={'x': 'Количество', 'y': 'URL'}
        )
        fig.update_layout(height=_chart_height(height))
        return dcc.Graph(figure=fig)
    except Exception as e:
        print(f"ERROR in create_top_urls_chart: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_chart(f"Ошибка создания графика: {str(e)}")


def _create_categorical_chart(df, column: str, title: str, top_n: int = 15, height=None):
    """Общий график по категориальному столбцу (столбчатый, топ N). В заголовке — количество выводимых записей."""
    if column not in df.columns or df.empty:
        return create_empty_chart(f"Нет данных: {column}")
    s = df[column].dropna().astype(str).str.strip()
    s = s[s != '']
    if s.empty:
        return create_empty_chart(f"Нет данных в столбце «{title}»")
    value_counts = s.value_counts()
    total_categories = len(value_counts)
    counts = value_counts.head(top_n)
    if total_categories > top_n:
        title_with_count = f"{title} (топ-{top_n} из {total_categories})"
    else:
        title_with_count = f"{title} (всего {total_categories})"
    fig = px.bar(
        x=counts.values,
        y=counts.index,
        orientation='h',
        title=title_with_count,
        labels={'x': 'Количество', 'y': ''}
    )
    fig.update_layout(height=_chart_height(height))
    return dcc.Graph(figure=fig)


def create_event_class_chart(df, height=None):
    """Распределение по классу события (Excel)."""
    col = _col_with_data(df, 'event_class')
    return _create_categorical_chart(df, col, "Распределение по классу события", 15, height) if col else create_empty_chart("Нет данных: класс события")


def create_event_type_chart(df, height=None):
    """Распределение по типу события (Excel / BGL)."""
    col = _col_with_data(df, 'event_type')
    return _create_categorical_chart(df, col, "Распределение по типу события", 15, height) if col else create_empty_chart("Нет данных: тип события")


def create_node_chart(df, height=None):
    """Распределение по узлам (BGL HPC)."""
    col = _col_with_data(df, 'node')
    return _create_categorical_chart(df, col, "Распределение по узлам (node)", 20, height) if col else create_empty_chart("Нет данных: узлы")


def create_category_chart(df, height=None):
    """Распределение по категории (BGL HPC)."""
    col = _col_with_data(df, 'category')
    return _create_categorical_chart(df, col, "Распределение по категории", 15, height) if col else create_empty_chart("Нет данных: категория")


def create_user_chart(df, height=None):
    """По пользователям (Excel)."""
    col = _col_with_data(df, 'user')
    return _create_categorical_chart(df, col, "Количество записей по пользователям", 15, height) if col else create_empty_chart("Нет данных: пользователи")


def create_importance_chart(df, height=None):
    """По важности (Excel)."""
    col = _col_with_data(df, 'importance')
    return _create_categorical_chart(df, col, "Распределение по важности", 15, height) if col else create_empty_chart("Нет данных: важность")


def create_ip_top_chart(df, height=None):
    """Топ IP-адресов (столбчатая диаграмма)."""
    col = _col_with_data(df, 'ip_address')
    return _create_categorical_chart(df, col, "Топ IP-адресов", 20, height) if col else create_empty_chart("Нет данных: IP-адреса")


def create_fallback_chart(df, height=None):
    """График по первому столбцу с данными (если нет стандартных полей)."""
    for col in df.columns:
        if _has_column_with_data(df, col):
            return _create_categorical_chart(df, col, f"Распределение по полю «{col}»", 15, height)
    return create_empty_chart("Нет данных для визуализации")


def create_all_charts_layout(df):
    """Страница «Все графики» — только те типы, для которых есть данные."""
    h = getattr(config, 'CHART_HEIGHT_ALL_PAGE', 320)
    sections = []
    if _has_column_with_data(df, 'timestamp'):
        sections.append(html.H5("Временной ряд", className="mt-4 mb-2 text-secondary"))
        sections.append(create_time_series_chart(df, height=h))
    if _has_column_with_data(df, 'level'):
        sections.append(html.H5("Распределение по уровням", className="mt-4 mb-2 text-secondary"))
        sections.append(create_level_distribution_chart(df, height=h))
    if _has_column_with_data(df, 'http_status'):
        sections.append(html.H5("HTTP статусы", className="mt-4 mb-2 text-secondary"))
        sections.append(create_status_distribution_chart(df, height=h))
    if _has_column_with_data(df, 'ip_address'):
        sections.append(html.H5("Топ IP-адресов", className="mt-4 mb-2 text-secondary"))
        sections.append(create_ip_top_chart(df, height=h))
        sections.append(html.H5("География запросов", className="mt-4 mb-2 text-secondary"))
        sections.append(create_geography_chart(df, height=400))
    if _has_column_with_data(df, 'url'):
        sections.append(html.H5("Частые запросы", className="mt-4 mb-2 text-secondary"))
        sections.append(create_top_urls_chart(df, height=h))
    if _col_with_data(df, 'event_class'):
        sections.append(html.H5("Класс события", className="mt-4 mb-2 text-secondary"))
        sections.append(create_event_class_chart(df, height=h))
    if _col_with_data(df, 'event_type'):
        sections.append(html.H5("Тип события", className="mt-4 mb-2 text-secondary"))
        sections.append(create_event_type_chart(df, height=h))
    if _col_with_data(df, 'node'):
        sections.append(html.H5("Узлы (node)", className="mt-4 mb-2 text-secondary"))
        sections.append(create_node_chart(df, height=h))
    if _col_with_data(df, 'category'):
        sections.append(html.H5("Категория", className="mt-4 mb-2 text-secondary"))
        sections.append(create_category_chart(df, height=h))
    if _col_with_data(df, 'user'):
        sections.append(html.H5("Пользователи", className="mt-4 mb-2 text-secondary"))
        sections.append(create_user_chart(df, height=h))
    if _col_with_data(df, 'importance'):
        sections.append(html.H5("Важность", className="mt-4 mb-2 text-secondary"))
        sections.append(create_importance_chart(df, height=h))
    if not sections:
        return create_fallback_chart(df, height=h)
    return html.Div(sections, style={'paddingBottom': '2rem'})


def create_empty_chart(message):
    """Создание пустого графика с сообщением"""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, xanchor='center', yanchor='middle',
        showarrow=False, font=dict(size=14)
    )
    fig.update_layout(
        title="Информация",
        xaxis=dict(showticklabels=False, showgrid=False),
        yaxis=dict(showticklabels=False, showgrid=False),
        height=config.CHART_HEIGHT
    )
    return dcc.Graph(figure=fig)

