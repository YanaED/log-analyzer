"""
Callbacks для работы с данными
"""
from dash import Input, Output, State, html, ctx, no_update
from time import perf_counter
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dash_table
from utils.database import DatabaseManager
from utils.analyzers import LogAnalyzer
from utils.anomaly_detection import detect_anomalies
from components.tables import create_data_table
import config
from flask import session

try:
    from utils.audit_logger import AuditLogger
    audit_logger = AuditLogger()
except Exception:
    audit_logger = None

db_manager = DatabaseManager()


def register_data_callbacks(app):
    """Регистрация callbacks для работы с данными"""
    
    def _upload_page_collections_display(collections_info):
        """Отображение только загруженных наборов (нормализованные) с понятными подписями."""
        normalized = [c for c in collections_info if c.get('type') == 'normalized' and c.get('count', 0) > 0]
        if not normalized:
            return dbc.Alert("Загруженных данных пока нет. Загрузите лог-файл выше.", color="info")
        items = []
        for info in normalized:
            fmt = info.get('file_source', 'unknown')
            count = info.get('count', 0)
            items.append(
                html.Div([
                    html.Span(f"Логи ({fmt})", className="fw-bold"),
                    html.Span(f" — {count} записей", className="text-muted")
                ], className="py-1 border-bottom border-light")
            )
        return html.Div(items, className="small")
    
    @app.callback(
        Output('collections-info', 'children'),
        [Input('refresh-btn', 'n_clicks'),
         Input('upload-data', 'contents'),
         Input('collections-refresh-interval', 'n_intervals')],
        prevent_initial_call=False
    )
    def update_collections_info(n_clicks, contents, n_intervals):
        owner_email = session.get("user_email")
        collections_info = db_manager.get_collections_info(owner_email=owner_email)
        
        if not db_manager.is_connected():
            return dbc.Alert("Нет подключения к базе данных", color="danger")
        
        if not collections_info:
            return dbc.Alert("В базе данных нет коллекций с логами", color="warning")
        
        return _upload_page_collections_display(collections_info)
    
    @app.callback(
        Output('collection-selector', 'options'),
        [Input('refresh-btn', 'n_clicks'),
         Input('upload-data', 'contents'),
         Input('collections-refresh-interval', 'n_intervals')],
        prevent_initial_call=False
    )
    def update_collection_options(n_clicks, contents, n_intervals):
        owner_email = session.get("user_email")
        collections_info = db_manager.get_collections_info(owner_email=owner_email)
        options = []
        for col in collections_info:
            # Показываем только нормализованные коллекции для выбора
            if col['type'] == 'normalized' and col.get('count', 0) > 0:
                display_name = col.get('file_source', col['name'])
                options.append({
                    'label': f"{display_name} ({col['count']} записей)",
                    'value': col['name']
                })
        return options
    
    @app.callback(
        Output('collection-selector', 'value', allow_duplicate=True),
        Input('collection-selector', 'options'),
        State('collection-selector', 'value'),
        prevent_initial_call=True
    )
    def preserve_collection_selection(options, current_value):
        """Сохранение выбранного значения коллекции при обновлении опций"""
        if current_value and options:
            option_values = [opt['value'] for opt in options]
            if current_value in option_values:
                return current_value
        if not options:
            return current_value
        return None
    
    @app.callback(
        [Output('clear-all-btn', 'children'),
         Output('collections-info', 'children', allow_duplicate=True),
         Output('collection-selector', 'options', allow_duplicate=True),
         Output('collection-selector', 'value', allow_duplicate=True)],
        Input('clear-all-btn', 'n_clicks'),
        prevent_initial_call=True
    )
    def clear_all_collections(n_clicks):
        if n_clicks and db_manager.is_connected():
            try:
                owner_email = session.get("user_email")
                collections_deleted = db_manager.clear_all_logs(owner_email=owner_email)
                if audit_logger:
                    audit_logger.log(
                        action="clear_all_logs",
                        user_email=owner_email,
                        status="success",
                        metadata={"collections_deleted": collections_deleted},
                    )
                # Автоматически обновляем информацию о коллекциях
                collections_info = db_manager.get_collections_info(owner_email=owner_email)
                
                if not collections_info:
                    collections_display = dbc.Alert("Загруженных данных пока нет.", color="info")
                else:
                    collections_display = _upload_page_collections_display(collections_info)
                
                # Обновляем опции селектора
                options = []
                for col in collections_info:
                    if col['type'] == 'normalized':
                        options.append({
                            'label': f"{col.get('file_source', col['name'])} ({col['count']} записей)",
                            'value': col['name']
                        })
                
                # Сбрасываем выбранное значение после очистки
                return "Удалить все данные", collections_display, options, None
            except Exception as e:
                if audit_logger:
                    audit_logger.log(
                        action="clear_all_logs",
                        user_email=session.get("user_email"),
                        status="error",
                        metadata={"error": str(e)},
                    )
                return f"Ошибка: {str(e)}", html.Div(), [], None
        return "Удалить все данные", html.Div(), [], None
    
    @app.callback(
        [Output('data-preview', 'children'),
         Output('data-store', 'data')],
        Input('load-data-btn', 'n_clicks'),
        [State('collection-selector', 'value'),
         State('table-limit-input', 'value')],
        prevent_initial_call=True
    )
    def load_and_display_data(n_clicks, selected_collection, limit):
        t0 = perf_counter()
        records_count = 0
        effective_limit = limit
        try:
            print(f"DEBUG: load_and_display_data called - n_clicks={n_clicks}, selected_collection={selected_collection}, limit={limit}")
            
            # Проверка выбора коллекции (это главная проверка)
            if not selected_collection:
                print("DEBUG: No collection selected")
                return (
                    dbc.Alert("Выберите коллекцию для просмотра данных", color="warning"),
                    None,
                )
            
            # Проверка подключения к БД
            if not db_manager.is_connected():
                print("DEBUG: Not connected to database")
                return (
                    dbc.Alert("Нет подключения к базе данных", color="danger"),
                    None,
                )
            
            # Загрузка данных: лимит из поля ввода (может прийти строкой от Dash)
            try:
                limit = int(limit) if limit is not None and str(limit).strip() != '' else config.DEFAULT_LOAD_LIMIT
            except (TypeError, ValueError):
                limit = config.DEFAULT_LOAD_LIMIT
            effective_limit = limit
            # Раньше по умолчанию было 100 — если пришло 100, считаем устаревшим и берём из конфига
            if limit == 100:
                limit = config.DEFAULT_LOAD_LIMIT
            limit = max(1, min(limit, config.MAX_TABLE_ROWS))
            print(f"DEBUG: Loading {limit} records from collection {selected_collection}")
            owner_email = session.get("user_email")
            logs = db_manager.get_logs_from_collection(selected_collection, limit, owner_email=owner_email)
            print(f"DEBUG: Loaded {len(logs) if logs else 0} records")
            records_count = len(logs) if logs else 0
            
            if not logs:
                print("DEBUG: No logs found")
                return (
                    dbc.Alert("В коллекции нет данных", color="warning"),
                    None,
                )
            
            # Создание таблицы
            df = pd.DataFrame(logs)
            print(f"DEBUG: Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
            table = create_data_table(df, page_size=10)
            print("DEBUG: Created table")
            
            # Сохранение данных в store
            data_dict = df.to_dict('records')
            print(f"DEBUG: Prepared data_dict with {len(data_dict)} records")
            
            # Возвращаем данные
            print("DEBUG: Returning results")
            return table, data_dict
            
        except Exception as e:
            print(f"Ошибка при загрузке данных: {e}")
            import traceback
            traceback.print_exc()
            return (
                dbc.Alert(f"Ошибка при загрузке данных: {str(e)}", color="danger"),
                None,
            )
        finally:
            dt_ms = (perf_counter() - t0) * 1000
            print(
                f"PERF load_and_display_data duration_ms={dt_ms:.1f} "
                f"limit={effective_limit} records={records_count}"
            )
    
    @app.callback(
        [Output('filter-date-to', 'min'),
         Output('filter-date-to', 'value')],
        Input('filter-date-from', 'value'),
        State('filter-date-to', 'value'),
        prevent_initial_call=False
    )
    def constrain_date_to(date_from, date_to):
        """«Дата до» не может быть раньше «Дата от»: задаём min и при необходимости поправляем значение."""
        min_to = date_from if date_from else '2000-01-01'
        if date_from and date_to and date_to < date_from:
            return min_to, date_from
        return min_to, no_update

    @app.callback(
        [Output('filter-date-from', 'max'),
         Output('filter-date-from', 'value')],
        Input('filter-date-to', 'value'),
        State('filter-date-from', 'value'),
        prevent_initial_call=False
    )
    def constrain_date_from(date_to, date_from):
        """«Дата от» не может быть позже «Дата до»: задаём max и при необходимости поправляем значение."""
        max_from = date_to if date_to else '2030-12-31'
        if date_to and date_from and date_from > date_to:
            return max_from, date_to
        return max_from, no_update

    @app.callback(
        [Output('filtered-data-store', 'data'),
         Output('statistics-display', 'children'),
         Output('filtered-data-preview', 'children')],
        [Input('apply-filters-btn', 'n_clicks'),
         Input('reset-filters-btn', 'n_clicks')],
        [State('data-store', 'data'),
         State('filter-date-from', 'value'),
         State('filter-date-to', 'value'),
         State('filter-time-from', 'value'),
         State('filter-time-to', 'value'),
         State('filter-ip', 'value'),
         State('filter-status', 'value'),
         State('filter-level', 'value'),
         State('filter-search', 'value')],
        prevent_initial_call=True
    )
    def apply_filters(apply_clicks, reset_clicks, data_store, date_from, date_to,
                      time_from, time_to, ip_address, status_code, level, search_text):
        t0 = perf_counter()
        records_count = len(data_store) if data_store else 0
        filtered_records_count = None
        from datetime import datetime, time as dt_time
        
        if data_store is None or len(data_store) == 0:
            empty_table = dbc.Alert("Загрузите данные для применения фильтров", color="warning")
            dt_ms = (perf_counter() - t0) * 1000
            print(
                f"PERF apply_filters duration_ms={dt_ms:.1f} "
                f"action=empty records={records_count}"
            )
            return None, empty_table, empty_table
        
        df = pd.DataFrame(data_store)
        
        # Определяем, какая именно кнопка была нажата последней.
        # Иначе после первого нажатия "Сбросить" значение reset_clicks становится >0
        # и "Применить" больше никогда не попадает в ветку фильтрации.
        triggered_id = ctx.triggered_id

        # Сброс фильтров
        if triggered_id == "reset-filters-btn":
            stats = LogAnalyzer.get_statistics(df)
            table = create_data_table(df, page_size=10)
            filtered_records_count = len(df)
            dt_ms = (perf_counter() - t0) * 1000
            print(
                f"PERF apply_filters duration_ms={dt_ms:.1f} "
                f"action=reset records={records_count} filtered_records={filtered_records_count}"
            )
            return df.to_dict('records'), create_statistics_display(stats), table
        
        # Применение фильтров
        if triggered_id == "apply-filters-btn":
            # Обработка даты и времени
            date_from_dt = None
            date_to_dt = None
            time_from_obj = None
            time_to_obj = None
            
            if date_from:
                date_from_dt = datetime.fromisoformat(date_from)
                if time_from:
                    time_parts = time_from.split(':')
                    date_from_dt = date_from_dt.replace(hour=int(time_parts[0]), minute=int(time_parts[1]))
            
            if date_to:
                date_to_dt = datetime.fromisoformat(date_to)
                if time_to:
                    time_parts = time_to.split(':')
                    date_to_dt = date_to_dt.replace(hour=int(time_parts[0]), minute=int(time_parts[1]))
                else:
                    # Если время не указано, устанавливаем конец дня
                    date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)

            # Важно: если пользователь задал только время (без дат),
            # применяем фильтр по времени суток отдельно.
            if time_from and not date_from:
                try:
                    h, m = time_from.split(':')
                    time_from_obj = dt_time(hour=int(h), minute=int(m))
                except Exception:
                    time_from_obj = None
            if time_to and not date_to:
                try:
                    h, m = time_to.split(':')
                    time_to_obj = dt_time(hour=int(h), minute=int(m))
                except Exception:
                    time_to_obj = None
            
            filtered_df = LogAnalyzer.filter_logs(
                df,
                date_from=date_from_dt,
                date_to=date_to_dt,
                ip_address=ip_address,
                status_code=status_code,
                level=level,
                search_text=search_text
            )

            # Если фильтр по времени задан без дат — фильтруем по времени в timestamp.
            if (time_from_obj or time_to_obj) and 'timestamp' in filtered_df.columns and not filtered_df.empty:
                ts = pd.to_datetime(filtered_df['timestamp'], errors='coerce')
                valid_mask = ts.notna()
                time_values = ts.dt.time

                if time_from_obj and time_to_obj:
                    if time_from_obj <= time_to_obj:
                        time_mask = (time_values >= time_from_obj) & (time_values <= time_to_obj)
                    else:
                        # Период через полночь, например 23:00-06:00
                        time_mask = (time_values >= time_from_obj) | (time_values <= time_to_obj)
                elif time_from_obj:
                    time_mask = time_values >= time_from_obj
                else:
                    time_mask = time_values <= time_to_obj

                filtered_df = filtered_df.loc[valid_mask & time_mask].copy()
            
            stats = LogAnalyzer.get_statistics(filtered_df)
            table = create_data_table(filtered_df, page_size=10)
            filtered_records_count = len(filtered_df)
            dt_ms = (perf_counter() - t0) * 1000
            print(
                f"PERF apply_filters duration_ms={dt_ms:.1f} "
                f"action=apply records={records_count} filtered_records={filtered_records_count}"
            )
            return filtered_df.to_dict('records'), create_statistics_display(stats), table
        
        # По умолчанию возвращаем исходные данные
        stats = LogAnalyzer.get_statistics(df)
        table = create_data_table(df, page_size=10)
        filtered_records_count = len(df)
        dt_ms = (perf_counter() - t0) * 1000
        print(
            f"PERF apply_filters duration_ms={dt_ms:.1f} "
            f"action=default records={records_count} filtered_records={filtered_records_count}"
        )
        return df.to_dict('records'), create_statistics_display(stats), table
    
    @app.callback(
        Output('anomaly-results', 'children'),
        Input('detect-anomalies-btn', 'n_clicks'),
        [State('filtered-data-store', 'data'),
         State('data-store', 'data'),
         State('anomaly-offhours-weekend-only', 'value')],
        prevent_initial_call=True
    )
    def run_anomaly_detection(n_clicks, filtered_data, data_store, anomaly_mode):
        """Запуск обнаружения аномалий по данным из текущей выборки."""
        t0 = perf_counter()
        n_total = 0
        n_anom = 0
        if not n_clicks:
            return ""
        data = filtered_data if (filtered_data and len(filtered_data) > 0) else data_store
        if not data or len(data) == 0:
            return dbc.Alert("Нет данных для анализа. Загрузите данные на вкладке «Просмотр данных».", color="warning")
        try:
            df = pd.DataFrame(data)
            n_total = len(df)
            mode_enabled = isinstance(anomaly_mode, list) and 'on' in anomaly_mode
            if mode_enabled:
                if 'timestamp' not in df.columns:
                    return dbc.Alert(
                        "Для режима «только выходные и вне рабочего времени» нужны данные с колонкой timestamp.",
                        color="warning"
                    )
                ts = pd.to_datetime(df['timestamp'], errors='coerce')
                df = df.loc[ts.notna()].copy()
                if df.empty:
                    return dbc.Alert("Не найдено корректных временных меток для анализа.", color="warning")
                ts = pd.to_datetime(df['timestamp'], errors='coerce')
                weekend_mask = ts.dt.dayofweek.isin([5, 6])  # Сб/Вс
                offhours_mask = (ts.dt.hour < 9) | (ts.dt.hour >= 18)
                # По требованию: анализируем записи, которые удовлетворяют ИЛИ:
                # (выходной) OR (вне рабочего времени до 09:00 и после 18:00)
                df = df.loc[weekend_mask | offhours_mask].copy()
                if df.empty:
                    return dbc.Alert(
                        "Нет записей, соответствующих условиям: выходные ИЛИ время до 09:00 / после 18:00.",
                        color="warning"
                    )

            # В режиме "выходные ИЛИ вне рабочего времени" исключаем признак длины сообщения.
            result = detect_anomalies(
                df,
                contamination=0.1,
                include_msg_len=not mode_enabled
            )
            if result.get('error'):
                if audit_logger:
                    audit_logger.log(
                        action="detect_anomalies",
                        user_email=session.get("user_email"),
                        status="error",
                        metadata={"error": result.get("error")},
                    )
                return dbc.Alert(f"Ошибка: {result['error']}", color="danger")
            n_anom = result['n_anomalies']
            n_total = result['n_total']
            if audit_logger:
                audit_logger.log(
                    action="detect_anomalies",
                    user_email=session.get("user_email"),
                    status="success",
                    metadata={
                        "n_anomalies": n_anom,
                        "n_total": n_total,
                        "mode_enabled": isinstance(anomaly_mode, list) and "on" in anomaly_mode,
                    },
                )
            summary = html.Div([
                dbc.Alert(f"Найдено аномалий: {n_anom} из {n_total} записей ({100 * n_anom / n_total:.1f}%).", color="info" if n_anom else "success", className="mb-2"),
            ])
            if n_anom == 0:
                return summary
            df_flagged = result['df_flagged']
            anomaly_df = df_flagged[df_flagged['_anomaly'] == 1].head(50).copy()
            anomaly_df['anomaly_score'] = anomaly_df['_anomaly_score'].round(4)
            # Минимальный набор колонок: №, 2–3 ключевых поля, Почему аномалия (последний столбец читаемый)
            # Показываем только «безопасные» поля: без IP и без HTTP-статусов (только время/уровень и, при наличии, URL)
            key_cols = [c for c in ['timestamp', 'level', 'url'] if c in anomaly_df.columns][:3]
            display_cols = key_cols + (['_anomaly_reasons'] if '_anomaly_reasons' in anomaly_df.columns else [])
            display_df = anomaly_df[display_cols].copy()
            display_df.insert(0, '№', range(1, len(display_df) + 1))
            if '_anomaly_reasons' in display_df.columns:
                display_df = display_df.rename(columns={'_anomaly_reasons': 'Почему аномалия'})
            for c in display_df.columns:
                if c == 'Почему аномалия':
                    continue
                if pd.api.types.is_datetime64_any_dtype(display_df[c]):
                    display_df[c] = display_df[c].astype(str)
                else:
                    s = display_df[c].astype(str)
                    display_df[c] = s.str[:20] + s.str.len().gt(20).map({True: '…', False: ''})
            # Последняя колонка — шире и с переносом строк, чтобы было читаемо
            columns = [{"name": c, "id": c} for c in display_df.columns]
            style_cell_conditional = [
                {'if': {'column_id': 'Почему аномалия'}, 'minWidth': '280px', 'maxWidth': '400px', 'whiteSpace': 'normal', 'overflow': 'visible'},
                {'if': {'column_id': '№'}, 'width': '40px'},
            ]
            table = dash_table.DataTable(
                data=display_df.to_dict('records'),
                columns=columns,
                page_size=10,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'padding': '6px', 'maxWidth': '120px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'},
                style_cell_conditional=style_cell_conditional,
            )
            return html.Div([summary, html.Div("Записи с аномалиями (до 50):", className="small fw-bold mt-2"), table])
        except Exception as e:
            return dbc.Alert(f"Ошибка при анализе: {str(e)}", color="danger")
        finally:
            dt_ms = (perf_counter() - t0) * 1000
            if n_clicks:
                print(
                    f"PERF run_anomaly_detection duration_ms={dt_ms:.1f} "
                    f"n_total={n_total} n_anom={n_anom} mode_enabled={isinstance(anomaly_mode, list) and 'on' in anomaly_mode}"
                )
    
    @app.callback(
        [Output('main-tabs', 'children', allow_duplicate=True),
         Output('main-tabs', 'active_tab', allow_duplicate=True)],
        Input('data-store', 'data'),
        State('main-tabs', 'children'),
        State('main-tabs', 'active_tab'),
        prevent_initial_call=True
    )
    def update_tabs_enabled_state(data_store, current_tabs, active_tab):
        """Включает вкладки «Анализ» и «Визуализация» после загрузки данных"""
        try:
            from components.tabs_layout import create_analysis_tab, create_visualization_tab
            has_data = data_store is not None and len(data_store) > 0
            updated_tabs = []
            for idx, tab in enumerate(current_tabs):
                if idx == 2:
                    updated_tabs.append(create_analysis_tab(
                        disabled=not has_data,
                        tab_style={"cursor": "not-allowed"} if not has_data else {}
                    ))
                elif idx == 3:
                    updated_tabs.append(create_visualization_tab(
                        disabled=not has_data,
                        tab_style={"cursor": "not-allowed"} if not has_data else {}
                    ))
                else:
                    updated_tabs.append(tab)
            if active_tab in ['tab-analysis', 'tab-visualization'] and not has_data:
                new_active_tab = 'tab-data'
            else:
                new_active_tab = active_tab if active_tab else 'tab-upload'
            return updated_tabs, new_active_tab
        except Exception as e:
            return current_tabs, active_tab or 'tab-upload'


def create_statistics_display(stats):
    """Создание отображения статистики"""
    cards = []
    
    # Общая статистика
    cards.append(dbc.Card([
        dbc.CardBody([
            html.H5("Общая статистика", className="card-title"),
            html.P(f"Всего записей: {stats.get('total', 0)}", className="card-text")
        ])
    ], className="mb-2"))
    
    # По уровням
    if stats.get('by_level'):
        level_items = [html.Li(f"{level}: {count}") for level, count in stats['by_level'].items()]
        cards.append(dbc.Card([
            dbc.CardBody([
                html.H5("По уровням", className="card-title"),
                html.Ul(level_items)
            ])
        ], className="mb-2"))
    
    # По статусам
    if stats.get('by_status'):
        status_items = []
        for status, count in list(stats['by_status'].items())[:10]:
            status_display = status
            try:
                status_num = float(status)
                # HTTP-статус всегда целый; убираем ".0" для корректного отображения.
                if status_num.is_integer():
                    status_display = int(status_num)
            except (TypeError, ValueError):
                pass
            status_items.append(html.Li(f"Статус {status_display}: {count}"))
        cards.append(dbc.Card([
            dbc.CardBody([
                html.H5("HTTP статусы", className="card-title"),
                html.Ul(status_items)
            ])
        ], className="mb-2"))
    
    return html.Div(cards)

