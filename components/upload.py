"""
Модуль компонента загрузки файлов
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
import config


def create_upload_component():
    """Создание компонента загрузки файлов — понятно и без лишнего."""
    return dbc.Card([
        dbc.CardHeader("Загрузка лог-файлов", className="bg-primary text-white"),
        dbc.CardBody([
            html.P("Загрузите один или несколько файлов. Форматы: " + ", ".join(config.SUPPORTED_FORMATS) + ".", className="text-muted small mb-2"),
            dcc.Upload(
                id='upload-data',
                children=html.Div([
                    "Перетащите файл сюда или нажмите для выбора"
                ]),
                style={
                    'width': '100%',
                    'height': '100px',
                    'lineHeight': '100px',
                    'borderWidth': '2px',
                    'borderStyle': 'dashed',
                    'borderRadius': '8px',
                    'textAlign': 'center',
                    'margin': '0 auto',
                    'backgroundColor': '#F7F9FB',
                    'cursor': 'pointer'
                },
                multiple=True
            ),
            html.Div(id='upload-status', className="mt-2"),
            html.Div(id="progress-container", children=[
                dbc.Progress(
                    id="progress-bar",
                    value=0,
                    striped=True,
                    animated=True,
                    className="mt-2",
                    style={"height": "8px"}
                ),
                html.Div(id="progress-text", className="mt-1 text-center small text-muted"),
                html.Div(id="processing-status", className="mt-1")
            ]),
            html.Div(id='file-preview', className="mt-2", style={"minHeight": "0"})
        ])
    ], className="mb-4")

