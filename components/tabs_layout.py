"""
Модуль с компонентами для каждой страницы приложения
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
from components.upload import create_upload_component
from components.filters import create_filters_component
from components.tables import create_tables_component
from components.charts import create_charts_component
from components.audit import create_audit_component


def get_upload_page_content():
    """Контент страницы «Загрузка файлов» (лаконичный вариант)."""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                create_upload_component()
            ], width=12)
        ]),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Загруженные данные", className="bg-success text-white"),
                    dbc.CardBody([
                        html.P(
                            "Загруженные наборы данных.",
                            className="text-muted small mb-3"
                        ),
                        html.Div(id='collections-info'),
                                dbc.Row([
                            dbc.Col([
                                dbc.Button("Обновить список", id='refresh-btn', color="info", className="mt-2", size="sm")
                            ], width=6),
                            dbc.Col([
                                dbc.Button("Удалить все данные", id='clear-all-btn', color="danger", className="mt-2", size="sm"),
                                dbc.Tooltip("Удаляет все загруженные логи из базы. Действие необратимо.", target="clear-all-btn", placement="top")
                            ], width=6)
                        ]),
                        dcc.Interval(id='collections-refresh-interval', interval=5 * 1000, n_intervals=0)
                    ])
                ], className="mb-4")
            ], width=12)
        ])
    ], fluid=True, className="mt-3")


def get_data_page_content():
    """Контент страницы «Просмотр данных»"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Выбор коллекции", className="bg-primary text-white"),
                    dbc.CardBody([
                        dcc.Dropdown(
                            id='collection-selector',
                            placeholder="Выберите коллекцию для просмотра...",
                            className="mb-3"
                        ),
                        dbc.Row([
                            dbc.Col([
                                dbc.Input(
                                    id='table-limit-input',
                                    type='number',
                                    placeholder="Лимит записей",
                                    value=1000,
                                    min=1,
                                    max=57000,
                                    className="mb-3"
                                )
                            ], width=6),
                            dbc.Col([
                                dbc.Button(
                                    "Загрузить данные",
                                    id='load-data-btn',
                                    color="primary",
                                    className="mb-3 w-100"
                                )
                            ], width=6)
                        ])
                    ])
                ], className="mb-4")
            ], width=12)
        ]),
        dbc.Row([
            dbc.Col([
                create_tables_component()
            ], width=12)
        ])
    ], fluid=True, className="mt-3")


def get_analysis_page_content():
    """Контент страницы «Анализ и фильтры». Фильтр не скроллится вместе с таблицей — прокрутка только у правой колонки."""
    right_content = [
        dbc.Card([
            dbc.CardHeader("Статистика", className="bg-info text-white"),
            dbc.CardBody([html.Div(id='statistics-display')])
        ], className="mb-4"),
        dbc.Card([
            dbc.CardHeader("Отфильтрованные данные", className="bg-success text-white"),
            dbc.CardBody([html.Div(id='filtered-data-preview', className="mt-3")])
        ], className="mb-4"),
        dbc.Card([
            dbc.CardHeader("Экспорт данных", className="bg-secondary text-white"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("Экспортировать:", className="form-label", style={'fontSize': '0.9rem'}),
                        dbc.RadioItems(
                            id='export-data-type',
                            options=[
                                {'label': 'Отфильтрованные данные', 'value': 'filtered'},
                                {'label': 'Все данные', 'value': 'all'}
                            ],
                            value='filtered',
                            inline=True,
                            className="mb-3"
                        )
                    ], width=12)
                ]),
                dbc.Row([
                    dbc.Col([dbc.Button("Экспорт в CSV", id='export-filtered-csv-btn', color="success", className="me-2 mb-2")], width=3),
                    dbc.Col([dbc.Button("Экспорт в PDF", id='export-filtered-pdf-btn', color="danger", className="me-2 mb-2")], width=3),
                    dbc.Col([dbc.Button("Экспорт в JSON", id='export-filtered-json-btn', color="info", className="mb-2")], width=3)
                ]),
                html.Div(id='export-filtered-status', className="mt-3")
            ])
        ], className="mb-4")
    ]
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Фильтры данных", className="bg-warning text-dark", style={'fontSize': '0.9rem'}),
                    dbc.CardBody([
                        create_filters_component()
                    ], style={'maxHeight': 'calc(100vh - 160px)', 'overflowY': 'auto', 'padding': '0.75rem'})
                ], className="mb-4", style={'maxHeight': 'calc(100vh - 100px)'})
            ], width=3),
            dbc.Col([
                html.Div(right_content, style={'maxHeight': 'calc(100vh - 100px)', 'overflowY': 'auto'})
            ], width=9)
        ], style={'maxHeight': 'calc(100vh - 100px)'})
    ], fluid=True, className="mt-3")


def get_visualization_page_content():
    """Контент страницы «Визуализация»"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                create_charts_component()
            ], width=12)
        ])
    ], fluid=True, className="mt-3")


def create_navbar():
    """Навигационная панель со ссылками на страницы"""
    return dbc.NavbarSimple(
        children=[
            dbc.NavItem(dbc.NavLink("Загрузка файлов", href="/upload", id="nav-upload")),
            dbc.NavItem(dbc.NavLink("Просмотр данных", href="/data", id="nav-data")),
            dbc.NavItem(dbc.NavLink("Анализ и фильтры", href="/analysis", id="nav-analysis")),
            dbc.NavItem(dbc.NavLink("Визуализация", href="/visualization", id="nav-visualization")),
        ],
        brand="Анализатор лог-файлов",
        brand_href="/upload",
        color="primary",
        dark=True,
        className="mb-4"
    )


def create_upload_tab():
    """Вкладка загрузки файлов — лаконичная и понятная."""
    return dbc.Tab(
        label="Загрузка файлов",
        tab_id="tab-upload",
        children=[
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        create_upload_component()
                    ], width=12)
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Загруженные данные", className="bg-success text-white"),
                            dbc.CardBody([
                                html.P(
                                    "Загруженные наборы данных. "
                                    "Для просмотра и анализа перейдите на вкладку «Просмотр данных».",
                                    className="text-muted small mb-3"
                                ),
                                html.Div(id='collections-info'),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Button(
                                            "Обновить список",
                                            id='refresh-btn',
                                            color="info",
                                            className="mt-2",
                                            size="sm"
                                        )
                                    ], width=6),
                                    dbc.Col([
                                        dbc.Button(
                                            "Удалить все данные",
                                            id='clear-all-btn',
                                            color="danger",
                                            className="mt-2",
                                            size="sm"
                                        ),
                                        dbc.Tooltip(
                                            "Удаляет все загруженные логи из базы. Действие необратимо.",
                                            target="clear-all-btn",
                                            placement="top"
                                        )
                                    ], width=6)
                                ])
                            ])
                        ], className="mb-4")
                    ], width=12)
                ])
            ], fluid=True, className="mt-3")
        ]
    )


def create_data_tab():
    """Вкладка просмотра данных"""
    return dbc.Tab(
        label="Просмотр данных",
        tab_id="tab-data",
        children=[
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Выбор коллекции", className="bg-primary text-white"),
                            dbc.CardBody([
                                dcc.Dropdown(
                                    id='collection-selector',
                                    placeholder="Выберите коллекцию для просмотра...",
                                    className="mb-3"
                                ),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Input(
                                            id='table-limit-input',
                                            type='number',
                                            placeholder="Лимит записей",
                                            value=1000,
                                            min=1,
                                            max=57000,
                                            className="mb-3"
                                        )
                                    ], width=6),
                                    dbc.Col([
                                        dbc.Button(
                                            "Загрузить данные",
                                            id='load-data-btn',
                                            color="primary",
                                            className="mb-3 w-100"
                                        )
                                    ], width=6)
                                ])
                            ])
                        ], className="mb-4")
                    ], width=12)
                ]),
                dbc.Row([
                    dbc.Col([
                        create_tables_component()
                    ], width=12)
                ])
            ], fluid=True, className="mt-3")
        ]
    )


def create_analysis_tab(disabled=True, tab_style=None):
    """Вкладка анализа и фильтрации"""
    if tab_style is None:
        tab_style = {"cursor": "not-allowed"} if disabled else {}
    return dbc.Tab(
        label="Анализ и фильтры",
        tab_id="tab-analysis",
        disabled=disabled,
        tab_style=tab_style,
        children=[
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Фильтры данных", className="bg-warning text-dark", style={'fontSize': '0.9rem'}),
                            dbc.CardBody([
                                create_filters_component()
                            ], style={'maxHeight': 'calc(100vh - 160px)', 'overflowY': 'auto', 'padding': '0.75rem'})
                        ], className="mb-4", style={'maxHeight': 'calc(100vh - 100px)'})
                    ], width=3),
                    dbc.Col([
                        html.Div([
                            dbc.Card([
                                dbc.CardHeader("Статистика", className="bg-info text-white"),
                                dbc.CardBody([html.Div(id='statistics-display')])
                            ], className="mb-4"),
                            dbc.Card([
                                dbc.CardHeader("Отфильтрованные данные", className="bg-success text-white"),
                                dbc.CardBody([html.Div(id='filtered-data-preview', className="mt-3")])
                            ], className="mb-4"),
                            dbc.Card([
                                dbc.CardHeader("Обнаружение аномалий (МО)", className="bg-primary text-white", style={'fontSize': '0.9rem'}),
                                dbc.CardBody([
                                    html.P("Выявление аномалий в логах с помощью Isolation Forest (неконтролируемое обучение).", className="small text-muted mb-2"),
                                    dbc.Checklist(
                                        id='anomaly-offhours-weekend-only',
                                        options=[{
                                            'label': 'Выходные ИЛИ вне рабочего времени (до 09:00 и после 18:00)',
                                            'value': 'on'
                                        }],
                                        value=[],
                                        switch=True,
                                        className="mb-2"
                                    ),
                                    dbc.Button("Выявить аномалии", id='detect-anomalies-btn', color="primary", className="mb-2", size="sm"),
                                    html.Div(id='anomaly-results', className="mt-2")
                                ])
                            ], className="mb-4"),
                            dbc.Card([
                                dbc.CardHeader("Экспорт данных", className="bg-secondary text-white"),
                                dbc.CardBody([
                                    dbc.Row([
                                        dbc.Col([
                                            html.Label("Экспортировать:", className="form-label", style={'fontSize': '0.9rem'}),
                                            dbc.RadioItems(
                                                id='export-data-type',
                                                options=[
                                                    {'label': 'Отфильтрованные данные', 'value': 'filtered'},
                                                    {'label': 'Все данные', 'value': 'all'}
                                                ],
                                                value='filtered',
                                                inline=True,
                                                className="mb-3"
                                            )
                                        ], width=12)
                                    ]),
                                    dbc.Row([
                                        dbc.Col([dbc.Button("Экспорт в CSV", id='export-filtered-csv-btn', color="success", className="me-2 mb-2")], width=3),
                                        dbc.Col([dbc.Button("Экспорт в PDF", id='export-filtered-pdf-btn', color="danger", className="me-2 mb-2")], width=3),
                                        dbc.Col([dbc.Button("Экспорт в JSON", id='export-filtered-json-btn', color="info", className="mb-2")], width=3)
                                    ]),
                                    html.Div(id='export-filtered-status', className="mt-3")
                                ])
                            ], className="mb-4")
                        ], style={'maxHeight': 'calc(100vh - 100px)', 'overflowY': 'auto'})
                    ], width=9)
                ], style={'maxHeight': 'calc(100vh - 100px)'})
            ], fluid=True, className="mt-3")
        ]
    )


def create_visualization_tab(disabled=True, tab_style=None):
    """Вкладка визуализации"""
    if tab_style is None:
        tab_style = {"cursor": "not-allowed"} if disabled else {}
    return dbc.Tab(
        label="Визуализация",
        tab_id="tab-visualization",
        disabled=disabled,
        tab_style=tab_style,
        children=[
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        create_charts_component()
                    ], width=12)
                ])
            ], fluid=True, className="mt-3")
        ]
    )

def create_audit_tab(disabled=False, tab_style=None):
    """Вкладка журнала аудита (в список вкладок добавляется только для администратора)."""
    if tab_style is None:
        tab_style = {"cursor": "not-allowed"} if disabled else {}
    return dbc.Tab(
        label="Аудит",
        tab_id="tab-audit",
        disabled=disabled,
        tab_style=tab_style,
        children=[
            create_audit_component(),
        ],
    )


def create_main_tabs(include_audit_tab: bool = False):
    """Создание главных вкладок приложения."""
    tab_list = [
        create_upload_tab(),
        create_data_tab(),
        create_analysis_tab(),
        create_visualization_tab(),
    ]
    if include_audit_tab:
        tab_list.append(create_audit_tab())
    return dbc.Tabs(
        tab_list,
        id="main-tabs",
        active_tab="tab-upload",
        className="mb-4",
    )

