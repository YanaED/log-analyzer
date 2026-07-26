"""
Главный файл запуска приложения для анализа лог-файлов
"""
import dash
from dash import html, dcc, Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc
from flask import session

from components.layout import create_app_layout
from callbacks.upload_callbacks import register_upload_callbacks
from callbacks.data_callbacks import register_data_callbacks
from callbacks.chart_callbacks import register_chart_callbacks
from callbacks.export_callbacks import register_export_callbacks
from callbacks.audit_callbacks import register_audit_callbacks
from utils.auth import UserManager
import config
import smtplib
from email.mime.text import MIMEText
from utils.audit_logger import AuditLogger

audit_logger = None
try:
    audit_logger = AuditLogger()
except Exception:
    audit_logger = None


def send_verification_code_email(to_email: str, code: str) -> str:
    """Отправка кода подтверждения (ввод на сайте, без ссылки с хостом)."""
    if not config.SMTP_SERVER or not config.SMTP_USERNAME or not config.SMTP_PASSWORD:
        return (
            "SMTP не настроен, аккаунт будет активирован без подтверждения e-mail."
        )

    subject = "Код подтверждения регистрации"
    body = (
        "Здравствуйте!\n\n"
        "Вы зарегистрировались в системе анализа лог-файлов.\n"
        f"Код подтверждения e-mail: {code}\n\n"
        "Введите этот код на странице регистрации в блоке под формой (появится после нажатия «Зарегистрироваться»). "
        "Код действителен 30 минут.\n\n"
        "Если вы не регистрировались, проигнорируйте это письмо.\n"
    )

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=10) as server:
            if config.SMTP_USE_TLS:
                server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)
        return "На указанный e-mail отправлен код подтверждения."
    except Exception as e:
        return f"Не удалось отправить письмо: {e}"


def is_user_authenticated() -> bool:
    return bool(session.get("user_email"))


def is_current_user_admin() -> bool:
    admin_email = (config.ADMIN_EMAIL or "").strip().lower()
    user_email = (session.get("user_email") or "").strip().lower()
    return bool(admin_email) and user_email == admin_email


def build_auth_layout():
    """Страница с регистрацией и авторизацией."""
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H1(
                                "Вход в систему анализа логов",
                                className="text-center mb-4",
                                style={"color": "#2c3e50", "fontWeight": "bold"},
                            )
                        ],
                        width=12,
                    )
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Card(
                                [
                                    dbc.CardHeader(
                                        "Авторизация", className="bg-primary text-white"
                                    ),
                                    dbc.CardBody(
                                        [
                                            dbc.Tabs(
                                                id="auth-tabs",
                                                active_tab="login-tab",
                                                children=[
                                                    dbc.Tab(
                                                        label="Вход",
                                                        tab_id="login-tab",
                                                        children=[
                                                            dbc.Form(
                                                                [
                                                                    dbc.Label("E-mail"),
                                                                    dbc.Input(
                                                                        id="login-email",
                                                                        type="email",
                                                                        placeholder="Введите e-mail",
                                                                    ),
                                                                    dbc.Label(
                                                                        "Пароль",
                                                                        className="mt-2",
                                                                    ),
                                                                    dbc.Input(
                                                                        id="login-password",
                                                                        type="password",
                                                                        placeholder="Введите пароль",
                                                                    ),
                                                                    dbc.Button(
                                                                        "Войти",
                                                                        id="login-button",
                                                                        color="primary",
                                                                        className="mt-3",
                                                                    ),
                                                                    html.Div(
                                                                        id="login-message",
                                                                        className="mt-3",
                                                                    ),
                                                                ]
                                                            )
                                                        ],
                                                    ),
                                                    dbc.Tab(
                                                        label="Регистрация",
                                                        tab_id="register-tab",
                                                        children=[
                                                            dbc.Form(
                                                                [
                                                                    dbc.Label("E-mail"),
                                                                    dbc.Input(
                                                                        id="register-email",
                                                                        type="email",
                                                                        placeholder="Введите e-mail",
                                                                    ),
                                                                    dbc.Label(
                                                                        "Пароль",
                                                                        className="mt-2",
                                                                    ),
                                                                    dbc.Input(
                                                                        id="register-password",
                                                                        type="password",
                                                                        placeholder="Минимум 6 символов",
                                                                    ),
                                                                    dbc.Label(
                                                                        "Повторите пароль",
                                                                        className="mt-2",
                                                                    ),
                                                                    dbc.Input(
                                                                        id="register-password2",
                                                                        type="password",
                                                                        placeholder="Повторите пароль",
                                                                    ),
                                                                    dbc.Button(
                                                                        "Зарегистрироваться",
                                                                        id="register-button",
                                                                        color="success",
                                                                        className="mt-3",
                                                                    ),
                                                                    html.Div(
                                                                        id="register-message",
                                                                        className="mt-3",
                                                                    ),
                                                                    html.Div(
                                                                        id="register-verify-block",
                                                                        style={"display": "none"},
                                                                        className="mt-3 pt-3 border-top",
                                                                        children=[
                                                                            html.P(
                                                                                "Подтверждение e-mail",
                                                                                className="small fw-bold mb-2 text-secondary",
                                                                            ),
                                                                            html.P(
                                                                                "На почту отправлен код из 6 цифр. "
                                                                                "Введите его ниже и подтвердите e-mail.",
                                                                                className="small text-muted mb-2",
                                                                            ),
                                                                            dbc.Label(
                                                                                "Код из письма",
                                                                                className="small",
                                                                            ),
                                                                            dbc.Input(
                                                                                id="post-register-code",
                                                                                type="text",
                                                                                placeholder="6 цифр",
                                                                                maxLength=12,
                                                                                className="mb-2",
                                                                            ),
                                                                            dbc.Button(
                                                                                "Подтвердить e-mail",
                                                                                id="post-register-verify-btn",
                                                                                color="primary",
                                                                                size="sm",
                                                                                className="me-2",
                                                                            ),
                                                                            dbc.Button(
                                                                                "Выслать код повторно",
                                                                                id="post-register-resend-btn",
                                                                                color="outline-secondary",
                                                                                size="sm",
                                                                            ),
                                                                            html.Div(
                                                                                id="post-register-verify-message",
                                                                                className="mt-2",
                                                                            ),
                                                                        ],
                                                                    ),
                                                                    dbc.Button(
                                                                        "Ввести код из письма",
                                                                        id="reveal-verify-code-btn",
                                                                        color="link",
                                                                        className="p-0 mt-2 small",
                                                                    ),
                                                                ]
                                                            )
                                                        ],
                                                    ),
                                                ],
                                            ),
                                            dcc.Location(id="login-redirect", refresh=True),
                                            dcc.Store(id="pending-verify-email", storage_type="session"),
                                        ]
                                    ),
                                ]
                            ),
                        ],
                        width=6,
                        className="offset-md-3",
                    )
                ]
            ),
        ],
        fluid=True,
    )


def serve_layout():
    """Выбор макета: страница логина или основное приложение с вкладками."""
    if is_user_authenticated():
        return create_app_layout(
            include_audit_tab=is_current_user_admin(),
            user_email=session.get("user_email"),
        )
    return build_auth_layout()


app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = config.APP_TITLE
app.server.secret_key = config.SECRET_KEY
app.layout = serve_layout

register_upload_callbacks(app)
register_data_callbacks(app)
register_chart_callbacks(app)
register_export_callbacks(app)
register_audit_callbacks(app)

user_manager = UserManager()


@app.server.route("/confirm_email/<token>")
def confirm_email_route(token: str):
    """Обработка ссылки подтверждения e-mail."""
    success, message = user_manager.confirm_by_token(token)
    if audit_logger:
        audit_logger.log(
            action="confirm_email",
            user_email=None,
            status="success" if success else "error",
            metadata={"message": message},
        )
    status = "Успех" if success else "Ошибка"
    return f"{status}: {message}. Теперь вы можете вернуться в приложение и войти."


@app.callback(
    Output("login-message", "children"),
    Output("auth-tabs", "active_tab"),
    Output("login-redirect", "href"),
    Input("login-button", "n_clicks"),
    State("login-email", "value"),
    State("login-password", "value"),
    prevent_initial_call=True,
)
def handle_login(n_clicks, email, password):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if not email or not password:
        if audit_logger:
            audit_logger.log(
                action="login_failed",
                user_email=email,
                status="error",
                metadata={"reason": "empty_credentials"},
            )
        return dbc.Alert("Введите e-mail и пароль", color="warning"), "login-tab", ""

    user = user_manager.find_by_email(email)
    if not user or not user_manager.verify_password(user, password):
        if audit_logger:
            audit_logger.log(
                action="login_failed",
                user_email=email,
                status="error",
                metadata={"reason": "invalid_credentials"},
            )
        return (
            dbc.Alert("Неверный e-mail или пароль", color="danger"),
            "login-tab",
            "",
        )

    if not user.get("is_confirmed", False) and config.SMTP_SERVER:
        if audit_logger:
            audit_logger.log(
                action="login_blocked_unconfirmed",
                user_email=user.get("email", email),
                status="blocked",
                metadata={"reason": "email_not_confirmed"},
            )
        return (
            dbc.Alert(
                "E-mail ещё не подтверждён. Откройте вкладку «Регистрация» и внизу введите код из письма.",
                color="warning",
            ),
            "login-tab",
            "",
        )

    session["user_email"] = user["email"]
    if audit_logger:
        audit_logger.log(
            action="login_success",
            user_email=user["email"],
            status="success",
        )
    return (
        dbc.Alert("Успешный вход", color="success"),
        "login-tab",
        "/",
    )


@app.callback(
    Output("register-message", "children"),
    Output("register-verify-block", "style"),
    Output("pending-verify-email", "data"),
    Input("register-button", "n_clicks"),
    State("register-email", "value"),
    State("register-password", "value"),
    State("register-password2", "value"),
    prevent_initial_call=True,
)
def handle_register(n_clicks, email, password, password2):
    hidden = {"display": "none"}

    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if not email or not password or not password2:
        return dbc.Alert("Заполните все поля", color="warning"), hidden, no_update

    if "@" not in email:
        return dbc.Alert("Введите корректный e-mail", color="warning"), hidden, no_update

    if len(password) < 6:
        return (
            dbc.Alert("Пароль должен содержать минимум 6 символов", color="warning"),
            hidden,
            no_update,
        )

    if password != password2:
        return dbc.Alert("Пароли не совпадают", color="warning"), hidden, no_update

    require_confirmation = bool(config.SMTP_SERVER and config.SMTP_USERNAME and config.SMTP_PASSWORD)
    user, plain_code, error = user_manager.create_user(
        email=email,
        password=password,
        require_confirmation=require_confirmation,
    )

    if error:
        if audit_logger:
            audit_logger.log(
                action="register_failed",
                user_email=email,
                status="error",
                metadata={"reason": error},
            )
        return dbc.Alert(error, color="danger"), hidden, None

    messages = []
    email_norm = email.lower().strip()

    if require_confirmation and plain_code:
        info = send_verification_code_email(email, plain_code)
        messages.append(html.Div(info))
        messages.append(
            html.Div(
                "Регистрация прошла успешно. Введите код из письма в поле ниже."
            )
        )
    else:
        messages.append(
            html.Div(
                "SMTP не настроен, поэтому аккаунт сразу активирован без подтверждения e-mail."
            )
        )
        messages.append(
            html.Div(
                "Регистрация прошла успешно. Теперь вы можете войти, используя e-mail и пароль."
            )
        )

    if audit_logger:
        audit_logger.log(
            action="register_success",
            user_email=email,
            status="success",
            metadata={"require_confirmation": require_confirmation},
        )

    if require_confirmation and plain_code:
        return (
            dbc.Alert(messages, color="success"),
            {"display": "block"},
            email_norm,
        )
    return dbc.Alert(messages, color="success"), hidden, None


@app.callback(
    Output("post-register-verify-message", "children"),
    Input("post-register-verify-btn", "n_clicks"),
    Input("post-register-resend-btn", "n_clicks"),
    State("pending-verify-email", "data"),
    State("post-register-code", "value"),
    prevent_initial_call=True,
)
def handle_verify_flow(n_ok, n_resend, email, code):
    if not callback_context.triggered:
        raise dash.exceptions.PreventUpdate

    btn = callback_context.triggered[0]["prop_id"].split(".")[0]
    email = (email or "").strip().lower()
    if not email:
        return dbc.Alert(
            "Не найден e-mail для подтверждения. Зарегистрируйтесь заново.",
            color="warning",
        )

    if btn == "post-register-resend-btn":
        if not n_resend:
            raise dash.exceptions.PreventUpdate
        if not (config.SMTP_SERVER and config.SMTP_USERNAME and config.SMTP_PASSWORD):
            return dbc.Alert(
                "SMTP не настроен — повторная отправка кода недоступна.",
                color="warning",
            )
        plain, err = user_manager.regenerate_verification_code(email)
        if err:
            if audit_logger:
                audit_logger.log(
                    action="verify_code_resend",
                    user_email=email,
                    status="error",
                    metadata={"reason": err},
                )
            return dbc.Alert(err, color="danger")
        info = send_verification_code_email(email, plain)
        if audit_logger:
            audit_logger.log(
                action="verify_code_resend",
                user_email=email,
                status="success",
            )
        return dbc.Alert(f"{info} Проверьте почту.", color="success")

    if not n_ok:
        raise dash.exceptions.PreventUpdate
    ok, msg = user_manager.confirm_by_code(email, code)
    if audit_logger:
        audit_logger.log(
            action="confirm_email_code",
            user_email=email,
            status="success" if ok else "error",
            metadata={"message": msg},
        )
    if ok:
        return dbc.Alert(msg, color="success")
    return dbc.Alert(msg, color="danger")


@app.callback(
    Output("register-verify-block", "style", allow_duplicate=True),
    Input("reveal-verify-code-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reveal_register_verify_block(n_clicks):
    if n_clicks:
        return {"display": "block"}
    raise dash.exceptions.PreventUpdate


@app.callback(
    Output("logout-redirect", "href"),
    Input("logout-button", "n_clicks"),
    prevent_initial_call=True,
)
def handle_logout(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    user_email = session.get("user_email")
    session.clear()
    if audit_logger:
        audit_logger.log(
            action="logout_success",
            user_email=user_email,
            status="success",
        )
    return "/"


if __name__ == '__main__':
    print("Запуск приложения для анализа лог-файлов...")
    if config.APP_HOST in ("0.0.0.0", "::"):
        print(f"Сервер: все интерфейсы, порт {config.APP_PORT}.")
        print(f"На этом компьютере: http://127.0.0.1:{config.APP_PORT}")
        if config.PUBLIC_APP_URL:
            print(f"Ссылка для сети и писем (PUBLIC_APP_URL): {config.PUBLIC_APP_URL}")
        else:
            print(
                "В .env задайте PUBLIC_APP_URL (IPv4 из ipconfig), иначе в письме будет 127.0.0.1."
            )
    else:
        print(f"Откройте в браузере: http://{config.APP_HOST}:{config.APP_PORT}")
    print("=" * 50)

    app.run(
        debug=config.DEBUG_MODE,
        host=config.APP_HOST,
        port=config.APP_PORT,
        dev_tools_ui=False,
        dev_tools_props_check=False,
    )

