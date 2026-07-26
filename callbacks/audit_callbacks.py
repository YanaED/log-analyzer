"""
Callbacks для страницы аудита действий пользователей.
"""

from dash import Input, Output, html, dash_table
import dash_bootstrap_components as dbc
from flask import session

import config
from utils.audit_logger import AuditLogger


def register_audit_callbacks(app):
    """Регистрация callback для загрузки аудита."""

    audit_logger = None
    try:
        audit_logger = AuditLogger()
    except Exception:
        audit_logger = None

    def is_admin() -> bool:
        admin_email = (config.ADMIN_EMAIL or "").strip().lower()
        user_email = (session.get("user_email") or "").strip().lower()
        return bool(admin_email) and user_email == admin_email

    @app.callback(
        Output("audit-results", "children"),
        Input("audit-refresh-btn", "n_clicks"),
    )
    def load_audit(n_clicks):
        if not is_admin():
            return dbc.Alert(
                "Доступ к аудиту разрешён только администратору.",
                color="danger",
            )

        if audit_logger is None:
            return dbc.Alert("Ошибка инициализации аудита.", color="danger")

        records = audit_logger.get_recent(limit=80)
        if not records:
            return dbc.Alert("Записей аудита пока нет.", color="info")

        rows = []
        for r in records:
            rows.append(
                {
                    "created_at": r.get("created_at", ""),
                    "action": r.get("action", ""),
                    "user_email": r.get("user_email", ""),
                    "status": r.get("status", ""),
                    "metadata": str(r.get("metadata", {}))[:1500],
                }
            )

        columns = [
            {"name": "Дата", "id": "created_at"},
            {"name": "Действие", "id": "action"},
            {"name": "Пользователь", "id": "user_email"},
            {"name": "Статус", "id": "status"},
            {"name": "Метаданные (кратко)", "id": "metadata"},
        ]

        table = dash_table.DataTable(
            data=rows,
            columns=columns,
            page_size=10,
            style_table={"overflowX": "auto", "width": "100%"},
            style_cell={
                "textAlign": "left",
                "padding": "6px",
                "maxWidth": "220px",
                "overflow": "hidden",
                "textOverflow": "ellipsis",
                "whiteSpace": "nowrap",
            },
            style_header={"fontWeight": "bold"},
            style_cell_conditional=[
                {
                    "if": {"column_id": "metadata"},
                    "maxWidth": "900px",
                    "whiteSpace": "normal",
                    "overflow": "visible",
                    "textOverflow": "clip",
                }
            ],
        )

        return html.Div(
            [
                dbc.Alert(f"Показано записей: {len(rows)}", color="info", className="mb-2"),
                html.Div(style={"overflowX": "auto", "width": "100%"}, children=[table]),
            ]
        )

