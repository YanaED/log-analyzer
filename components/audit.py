from dash import html, dcc
import dash_bootstrap_components as dbc
from dash import dash_table


def create_audit_component():
    """Компонент страницы аудита действий (минималистично)."""
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Button(
                                "Обновить аудит",
                                id="audit-refresh-btn",
                                color="primary",
                                className="mb-2",
                                n_clicks=0,
                            ),
                            html.Div(
                                id="audit-results",
                            ),
                        ],
                        width=12,
                    )
                ]
            ),
        ],
        fluid=True,
        className="mt-3",
    )

