"""
Модуль компонентов фильтров
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta


def create_filters_component():
    """Создание компонента фильтров (компактная версия сбоку). Каждая пара «подпись + поле» в своём блоке — без съезжания."""
    def row_filter(label_text, control):
        return html.Div([
            html.Label(label_text, className="form-label", style={'fontSize': '0.85rem', 'marginBottom': '2px'}),
            control
        ], className="mb-2")
    # Нативный календарь (type="date"): в браузере можно кликнуть по году/месяцу для быстрого выбора
    return html.Div([
        row_filter("Дата от:", dbc.Input(
            id='filter-date-from',
            type='date',
            size="sm",
            min='2000-01-01',
            max='2030-12-31',
            style={'minWidth': '140px'}
        )),
        row_filter("Дата до:", dbc.Input(
            id='filter-date-to',
            type='date',
            size="sm",
            min='2000-01-01',
            max='2030-12-31',
            style={'minWidth': '140px'}
        )),
        row_filter("Время от:", dbc.Input(id='filter-time-from', type='time', size="sm")),
        row_filter("Время до:", dbc.Input(id='filter-time-to', type='time', size="sm")),
        row_filter("IP-адрес:", dbc.Input(id='filter-ip', type='text', placeholder="IP", size="sm")),
        row_filter("Статус-код:", dbc.Input(id='filter-status', type='number', placeholder="HTTP статус", size="sm")),
        row_filter("Уровень:", dcc.Dropdown(
            id='filter-level',
            options=[
                {'label': 'INFO', 'value': 'INFO'},
                {'label': 'WARNING', 'value': 'WARNING'},
                {'label': 'ERROR', 'value': 'ERROR'},
                {'label': 'DEBUG', 'value': 'DEBUG'}
            ],
            placeholder="Уровень",
            style={'fontSize': '0.9rem'}
        )),
        row_filter("Поиск по тексту:", dbc.Input(id='filter-search', type='text', placeholder="Текст...", size="sm")),
        html.Div([
            dbc.Button("Применить", id='apply-filters-btn', color="primary", className="w-100 mb-2", size="sm"),
            dbc.Button("Сбросить", id='reset-filters-btn', color="secondary", outline=True, className="w-100", size="sm")
        ], className="mt-1")
    ])

