"""
Callbacks для экспорта данных
"""
import base64
import os
from time import perf_counter
from dash import Input, Output, State, ctx, html
import dash_bootstrap_components as dbc
import pandas as pd
from flask import session
from utils.export import DataExporter
from utils.analyzers import LogAnalyzer
from components.charts import _has_column_with_data, _col_with_data, get_time_series_figure
import plotly.graph_objects as go
import plotly.express as px

try:
    from utils.audit_logger import AuditLogger
    audit_logger = AuditLogger()
except Exception:
    audit_logger = None


def register_export_callbacks(app):
    """Регистрация callbacks для экспорта"""
    
    @app.callback(
        [Output('export-filtered-status', 'children'),
         Output('download-pdf', 'data')],
        [Input('export-filtered-csv-btn', 'n_clicks'),
         Input('export-filtered-pdf-btn', 'n_clicks'),
         Input('export-filtered-json-btn', 'n_clicks')],
        [State('filtered-data-store', 'data'),
         State('data-store', 'data'),
         State('export-data-type', 'value')]
    )
    def handle_filtered_export(csv_clicks, pdf_clicks, json_clicks,
                               filtered_data, original_data, export_type):
        t0 = perf_counter()
        button_id = None
        data_label = None
        records_count = 0
        no_download = None

        try:
            # Два выхода: статус и данные для скачивания
            if not ctx.triggered:
                return "", None

            button_id = ctx.triggered[0]['prop_id'].split('.')[0]

            # Выбираем данные в зависимости от выбора пользователя
            if export_type == 'all':
                data = original_data
                data_label = "Все данные"
            else:
                data = filtered_data
                data_label = "Отфильтрованные данные"

            if data is None or len(data) == 0:
                if export_type == 'all':
                    return (
                        dbc.Alert(
                            "Нет данных для экспорта. Загрузите данные на вкладке 'Просмотр данных'.",
                            color="warning",
                        ),
                        None,
                    )
                return (
                    dbc.Alert(
                        "Нет отфильтрованных данных для экспорта. Примените фильтры.",
                        color="warning",
                    ),
                    None,
                )

            df = pd.DataFrame(data)
            records_count = len(df)

            if button_id == 'export-filtered-csv-btn':
                filepath = DataExporter.export_to_csv(df)
                full_path = os.path.abspath(filepath)
                if audit_logger:
                    audit_logger.log(
                        action="export_csv",
                        user_email=session.get("user_email"),
                        status="success",
                        metadata={
                            "export_scope": data_label,
                            "records": len(df),
                            "path": full_path,
                        },
                    )
                return (
                    dbc.Alert(
                        [
                            html.Strong(f"{data_label} экспортированы в CSV!"),
                            html.Br(),
                            f"Путь: {full_path}",
                        ],
                        color="success",
                    ),
                    no_download,
                )

            if button_id == 'export-filtered-pdf-btn':
                stats = LogAnalyzer.get_statistics(df)
                charts = _create_charts_for_export(df)
                if export_type == 'filtered':
                    title = "Отчет по отфильтрованным данным."
                else:
                    title = "Отчет по всем данным."
                filepath = DataExporter.export_to_pdf(df, title=title, stats=stats, charts=charts)
                full_path = os.path.abspath(filepath)
                # Запускаем загрузку PDF в браузере
                try:
                    with open(filepath, 'rb') as f:
                        pdf_bytes = f.read()
                    filename = os.path.basename(filepath)
                    download_data = dict(
                        filename=filename,
                        content=base64.b64encode(pdf_bytes).decode(),
                        base64=True,
                    )
                except Exception as e:
                    download_data = None
                    print(f"Не удалось прочитать PDF для загрузки: {e}")
                if audit_logger:
                    audit_logger.log(
                        action="export_pdf",
                        user_email=session.get("user_email"),
                        status="success",
                        metadata={
                            "export_scope": data_label,
                            "records": len(df),
                            "path": full_path,
                        },
                    )
                return (
                    dbc.Alert(
                        [
                            html.Strong(f"Отчет по {data_label.lower()} создан в PDF!"),
                            html.Br(),
                            "Файл должен автоматически загрузиться. Если нет — сохранён по пути:",
                            html.Br(),
                            full_path,
                        ],
                        color="success",
                    ),
                    download_data,
                )

            if button_id == 'export-filtered-json-btn':
                filepath = DataExporter.export_to_json(df)
                full_path = os.path.abspath(filepath)
                if audit_logger:
                    audit_logger.log(
                        action="export_json",
                        user_email=session.get("user_email"),
                        status="success",
                        metadata={
                            "export_scope": data_label,
                            "records": len(df),
                            "path": full_path,
                        },
                    )
                return (
                    dbc.Alert(
                        [
                            html.Strong(f"{data_label} экспортированы в JSON!"),
                            html.Br(),
                            f"Путь: {full_path}",
                        ],
                        color="success",
                    ),
                    no_download,
                )

        except Exception as e:
            if audit_logger:
                audit_logger.log(
                    action="export",
                    user_email=session.get("user_email"),
                    status="error",
                    metadata={"error": str(e)},
                )
            return dbc.Alert(f"Ошибка при экспорте: {str(e)}", color="danger"), no_download

        finally:
            dt_ms = (perf_counter() - t0) * 1000
            print(
                f"PERF export duration_ms={dt_ms:.1f} button_id={button_id} "
                f"export_type={export_type} data_label={data_label} records={records_count}"
            )

        return "", no_download


def _categorical_fig_for_pdf(df, column, title, top_n=15):
    """Строит столбчатый график для PDF (топ-N с подписью количества). Возвращает fig или None."""
    if column not in df.columns or df[column].dropna().empty:
        return None
    s = df[column].dropna().astype(str).str.strip()
    s = s[s != '']
    if s.empty:
        return None
    value_counts = s.value_counts()
    total = len(value_counts)
    counts = value_counts.head(top_n)
    if total > top_n:
        title_with_count = f"{title} (топ-{top_n} из {total})"
    else:
        title_with_count = f"{title} (всего {total})"
    fig = px.bar(
        x=counts.values,
        y=counts.index,
        orientation='h',
        title=title_with_count,
        labels={'x': 'Количество', 'y': ''}
    )
    fig.update_layout(height=500, width=800)
    return fig


def _create_charts_for_export(df: pd.DataFrame) -> list:
    """Создание графиков для экспорта в PDF (включая новые: класс/тип события, пользователи, важность, топ IP)."""
    charts = []
    
    try:
        # Временной ряд — та же логика, что на вкладке (интервал по длине периода)
        fig = get_time_series_figure(df, height=500)
        if fig is not None:
            fig.update_layout(width=800)
            charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика временного ряда: {e}")
    
    try:
        if _has_column_with_data(df, 'level'):
            level_counts = df['level'].value_counts()
            fig = px.pie(
                values=level_counts.values,
                names=level_counts.index,
                title="Распределение по уровням логирования"
            )
            fig.update_layout(height=500, width=800)
            charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика распределения по уровням: {e}")
    
    try:
        if _has_column_with_data(df, 'http_status'):
            status_counts = df['http_status'].value_counts().sort_index()
            fig = px.bar(
                x=status_counts.index.astype(str),
                y=status_counts.values,
                title="Распределение HTTP статус-кодов",
                labels={'x': 'Статус-код', 'y': 'Количество'}
            )
            fig.update_layout(height=500, width=800)
            charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика HTTP статусов: {e}")
    
    try:
        if _has_column_with_data(df, 'url'):
            all_urls = df['url'].value_counts()
            total = len(all_urls)
            url_counts = all_urls.head(10)
            top_n = 10
            title = f"Частые запросы (топ-{top_n} из {total})" if total > top_n else f"Частые запросы (всего {total})"
            fig = px.bar(
                x=url_counts.values,
                y=url_counts.index,
                orientation='h',
                title=title,
                labels={'x': 'Количество', 'y': 'URL'}
            )
            fig.update_layout(height=500, width=800)
            charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика частых запросов: {e}")
    
    # Топ IP-адресов
    try:
        col = _col_with_data(df, 'ip_address')
        if col:
            fig = _categorical_fig_for_pdf(df, col, "Топ IP-адресов", top_n=20)
            if fig is not None:
                charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика топ IP: {e}")
    
    # Класс события
    try:
        col = _col_with_data(df, 'event_class')
        if col:
            fig = _categorical_fig_for_pdf(df, col, "Распределение по классу события", 15)
            if fig is not None:
                charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика класс события: {e}")
    
    # Тип события
    try:
        col = _col_with_data(df, 'event_type')
        if col:
            fig = _categorical_fig_for_pdf(df, col, "Распределение по типу события", 15)
            if fig is not None:
                charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика тип события: {e}")
    
    # Узлы (BGL)
    try:
        col = _col_with_data(df, 'node')
        if col:
            fig = _categorical_fig_for_pdf(df, col, "Распределение по узлам (node)", 20)
            if fig is not None:
                charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика узлы: {e}")
    
    # Категория (BGL)
    try:
        col = _col_with_data(df, 'category')
        if col:
            fig = _categorical_fig_for_pdf(df, col, "Распределение по категории", 15)
            if fig is not None:
                charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика категория: {e}")
    
    # Пользователи
    try:
        col = _col_with_data(df, 'user')
        if col:
            fig = _categorical_fig_for_pdf(df, col, "Количество записей по пользователям", 15)
            if fig is not None:
                charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика пользователи: {e}")
    
    # Важность
    try:
        col = _col_with_data(df, 'importance')
        if col:
            fig = _categorical_fig_for_pdf(df, col, "Распределение по важности", 15)
            if fig is not None:
                charts.append(fig)
    except Exception as e:
        print(f"Ошибка создания графика важность: {e}")
    
    return charts

