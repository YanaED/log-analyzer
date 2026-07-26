"""
Модуль с основной структурой интерфейса приложения
"""
from typing import Optional

from dash import html, dcc
import dash_bootstrap_components as dbc
from components.tabs_layout import create_main_tabs


def create_app_layout(include_audit_tab: bool = False, user_email: Optional[str] = None):
    """Создание основного макета приложения с вкладками."""
    user_bar_children = []
    if user_email:
        user_bar_children.append(
            html.Span(
                f"Вы вошли как: {user_email}",
                className="text-muted small me-3",
            )
        )
    user_bar_children.append(
        dbc.Button(
            "Выйти",
            id="logout-button",
            color="outline-secondary",
            size="sm",
        )
    )
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div(
                    user_bar_children,
                    style={
                        "display": "flex",
                        "justifyContent": "flex-end",
                        "alignItems": "center",
                        "flexWrap": "wrap",
                    },
                    className="mb-2",
                ),
            ], width=12),
        ]),
        dbc.Row([
            dbc.Col([
                html.H1(
                    "Анализатор лог-файлов",
                    className="text-center mb-4",
                    style={'color': '#687864', 'fontWeight': 'bold'}
                ),
                html.Div(id="connection-status", className="text-center mb-3")
            ], width=12)
        ]),
        dbc.Row([
            dbc.Col([
                create_main_tabs(include_audit_tab=include_audit_tab),
                dbc.Tooltip(
                    "Сначала загрузите данные на вкладке «Просмотр данных»",
                    target="tab-analysis",
                    placement="top"
                ),
                dbc.Tooltip(
                    "Сначала загрузите данные на вкладке «Просмотр данных»",
                    target="tab-visualization",
                    placement="top"
                )
            ], width=12)
        ]),
        dcc.Interval(
            id='progress-interval',
            interval=1000,
            n_intervals=0,
            disabled=False
        ),
        dcc.Interval(
            id='collections-refresh-interval',
            interval=5 * 1000,
            n_intervals=0
        ),
        dcc.Store(id='data-store'),
        dcc.Store(id='filtered-data-store'),
        dcc.Download(id='download-pdf'),
        dcc.Location(id="logout-redirect", refresh=True),
    ], fluid=True)

