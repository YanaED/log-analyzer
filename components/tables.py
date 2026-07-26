"""
Модуль компонентов таблиц
"""
from dash import html, dash_table
import dash_bootstrap_components as dbc
import config


def create_tables_component():
    """Создание компонента таблиц"""
    return dbc.Card([
        dbc.CardHeader("Таблица данных", className="bg-warning text-dark"),
        dbc.CardBody([
            html.Div(
                dbc.Alert("Выберите коллекцию и нажмите 'Загрузить данные' для просмотра", color="info"),
                id='data-preview',
                className="mt-3"
            )
        ])
    ], className="mb-4")


def create_data_table(df, page_size=None):
    """Создание таблицы данных из DataFrame"""
    if page_size is None:
        page_size = config.DEFAULT_TABLE_PAGE_SIZE
    
    exclude_columns = ['_id', 'uploaded_at']
    display_columns = [col for col in df.columns if col not in exclude_columns]
    
    # Убеждаемся, что message/raw_message включены в таблицу
    priority_columns = [
        'timestamp', 'level', 'message', 'description', 'raw_message',
        'user', 'server', 'ip_address', 'event_class', 'event_type', 'importance',
        'protection_object', 'protection_object_address',
        'url', 'http_status'
    ]
    ordered_columns = []
    for col in priority_columns:
        if col in display_columns:
            ordered_columns.append(col)
    for col in display_columns:
        if col not in ordered_columns:
            ordered_columns.append(col)
    
    # Формируем колонки с настройками ширины для message
    columns_config = []
    for col in ordered_columns:
        col_config = {"name": col, "id": col}
        if col in ['message', 'raw_message', 'description']:
            col_config['presentation'] = 'markdown'
            col_config['type'] = 'text'
        columns_config.append(col_config)
    
    # Стили для ячеек с сообщениями
    style_cell_conditional = []
    for col in ordered_columns:
        if col in ['message', 'raw_message', 'description']:
            style_cell_conditional.append({
                'if': {'column_id': col},
                'maxWidth': '400px',
                'whiteSpace': 'normal',
                'height': 'auto',
            })
        else:
            style_cell_conditional.append({
                'if': {'column_id': col},
                'maxWidth': '200px',
            })
    
    return dash_table.DataTable(
        data=df[ordered_columns].to_dict('records'),
        columns=columns_config,
        page_size=page_size,
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '8px',
            'overflow': 'hidden',
            'textOverflow': 'ellipsis',
        },
        style_cell_conditional=style_cell_conditional,
        style_header={
            'backgroundColor': '#8FC1E3',
            'color': '#1a1a1a',
            'fontWeight': 'bold'
        },
        filter_action="native",
        sort_action="native"
    )

