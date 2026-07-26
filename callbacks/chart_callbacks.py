"""
Callbacks для графиков и визуализаций
"""
from dash import Input, Output, State, ctx
from time import perf_counter
import pandas as pd
from components.charts import (
    create_time_series_chart,
    create_level_distribution_chart,
    create_status_distribution_chart,
    create_geography_chart,
    create_top_urls_chart,
    create_ip_top_chart,
    create_empty_chart,
    create_chart_tabs,
    create_all_charts_layout,
    create_event_class_chart,
    create_event_type_chart,
    create_node_chart,
    create_category_chart,
    create_user_chart,
    create_importance_chart,
    create_fallback_chart,
)


def register_chart_callbacks(app):
    """Регистрация callbacks для графиков"""
    
    @app.callback(
        [Output('chart-tabs', 'children'),
         Output('chart-tabs', 'active_tab', allow_duplicate=True)],
        [Input('filtered-data-store', 'data'),
         Input('data-store', 'data'),
         Input('main-tabs', 'active_tab')],
        State('chart-tabs', 'active_tab'),
        prevent_initial_call='initial_duplicate'
    )
    def update_chart_tabs(filtered_data, original_data, main_active_tab, current_active_tab):
        """Обновление вкладок графиков на основе доступных данных"""
        t0 = perf_counter()
        # Перестраиваем вкладки каждый раз при открытии вкладки "Визуализация",
        # чтобы после смены датасета не оставался пустой chart-tabs до ручного refresh.
        if main_active_tab and main_active_tab != 'tab-visualization':
            dt_ms = (perf_counter() - t0) * 1000
            print(f"PERF update_chart_tabs duration_ms={dt_ms:.1f} reason=not_visualization")
            return [], None

        # Если сработало изменение data-store (сменили датасет на вкладке "Просмотр данных"),
        # то нужно строить вкладки по исходным данным нового датасета, а не по старым filtered-data-store.
        triggered_id = ctx.triggered_id
        if triggered_id == "filtered-data-store":
            data = filtered_data if filtered_data else original_data
        else:
            # На практике при смене датасета срабатывает именно data-store.
            data = original_data
        
        print(f"DEBUG: update_chart_tabs called - filtered_data: {len(filtered_data) if filtered_data else 0}, original_data: {len(original_data) if original_data else 0}")
        
        if data is None or len(data) == 0:
            print("DEBUG: No data available for chart tabs")
            dt_ms = (perf_counter() - t0) * 1000
            print(f"PERF update_chart_tabs duration_ms={dt_ms:.1f} reason=no_data")
            return [], None
        
        df = pd.DataFrame(data)
        print(f"DEBUG: DataFrame columns: {list(df.columns)}")
        print(f"DEBUG: DataFrame shape: {df.shape}")
        
        # Проверяем наличие полей
        print(f"DEBUG: has timestamp: {'timestamp' in df.columns and not df['timestamp'].isna().all()}")
        print(f"DEBUG: has level: {'level' in df.columns and not df['level'].isna().all()}")
        print(f"DEBUG: has http_status: {'http_status' in df.columns and not df['http_status'].isna().all()}")
        print(f"DEBUG: has ip_address: {'ip_address' in df.columns and not df['ip_address'].isna().all()}")
        print(f"DEBUG: has url: {'url' in df.columns and not df['url'].isna().all()}")
        
        new_tabs = create_chart_tabs(df)
        print(f"DEBUG: Created {len(new_tabs)} tabs: {[tab.tab_id for tab in new_tabs]}")
        
        # Сохраняем активную вкладку, если она все еще доступна
        available_tab_ids = [tab.tab_id for tab in new_tabs] if new_tabs else []
        
        if current_active_tab and current_active_tab in available_tab_ids:
            active_tab = current_active_tab
        elif available_tab_ids:
            active_tab = available_tab_ids[0]
        else:
            active_tab = None
        
        print(f"DEBUG: Selected active_tab: {active_tab}")
        dt_ms = (perf_counter() - t0) * 1000
        print(
            f"PERF update_chart_tabs duration_ms={dt_ms:.1f} "
            f"records={len(data)} tabs={len(new_tabs) if new_tabs else 0} active_tab={active_tab}"
        )
        return new_tabs, active_tab
    
    @app.callback(
        Output('charts-container', 'children'),
        [Input('chart-tabs', 'active_tab'),
         Input('filtered-data-store', 'data'),
         Input('data-store', 'data'),
         Input('chart-tabs', 'children')]
    )
    def update_charts(active_tab, filtered_data, original_data, chart_tabs):
        try:
            t0 = perf_counter()
            # При смене датасета срабатывает data-store — строим график по нему,
            # иначе могли бы остаться старые filtered-data-store от предыдущего датасета.
            triggered_id = ctx.triggered_id
            if triggered_id == "data-store":
                data = original_data
            elif triggered_id == "filtered-data-store":
                data = filtered_data if filtered_data else original_data
            else:
                # При переключении вкладок/активной вкладки используем "последние" доступные данные.
                data = filtered_data if filtered_data else original_data
            
            print(f"DEBUG: update_charts called - active_tab={active_tab}, data_length={len(data) if data else 0}, chart_tabs={len(chart_tabs) if chart_tabs else 0}")
            
            if data is None or len(data) == 0:
                print("DEBUG: No data in update_charts")
                dt_ms = (perf_counter() - t0) * 1000
                print(f"PERF update_charts duration_ms={dt_ms:.1f} reason=no_data active_tab={active_tab}")
                return create_empty_chart("Загрузите данные для визуализации")
            
            # Проверяем, созданы ли вкладки
            if not chart_tabs or len(chart_tabs) == 0:
                print("DEBUG: No chart tabs in update_charts")
                dt_ms = (perf_counter() - t0) * 1000
                print(f"PERF update_charts duration_ms={dt_ms:.1f} reason=no_tabs active_tab={active_tab}")
                return create_empty_chart("Создание вкладок визуализации...")
            
            if active_tab is None:
                # Если активная вкладка не установлена, используем первую доступную
                if chart_tabs and len(chart_tabs) > 0:
                    try:
                        t = chart_tabs[0]
                        first_tab_id = getattr(t, 'tab_id', None) or (t.get('props', {}).get('tab_id') if isinstance(t, dict) else None)
                        if first_tab_id:
                            active_tab = first_tab_id
                    except Exception:
                        active_tab = "tab-time-series"
                
                if active_tab is None:
                    print("DEBUG: No active tab available")
                    return create_empty_chart("Нет доступных визуализаций для данных")
            
            print(f"DEBUG: Creating chart for tab: {active_tab}, data size: {len(data)}")
            df = pd.DataFrame(data)
            print(f"DEBUG: DataFrame created, shape: {df.shape}")
            
            # Создаем график с обработкой ошибок
            try:
                if active_tab == "tab-all":
                    fig = create_all_charts_layout(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                if active_tab == "tab-time-series":
                    print("DEBUG: Creating time series chart")
                    fig = create_time_series_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-levels":
                    print("DEBUG: Creating level distribution chart")
                    fig = create_level_distribution_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-status":
                    print("DEBUG: Creating status distribution chart")
                    fig = create_status_distribution_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-ip-top":
                    fig = create_ip_top_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-geography":
                    print("DEBUG: Creating geography chart (this may take time for large datasets)")
                    fig = create_geography_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-urls":
                    fig = create_top_urls_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-event-class":
                    fig = create_event_class_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-event-type":
                    fig = create_event_type_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-node":
                    fig = create_node_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-category":
                    fig = create_category_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-user":
                    fig = create_user_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-importance":
                    fig = create_importance_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                elif active_tab == "tab-fallback":
                    fig = create_fallback_chart(df)
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} active_tab={active_tab} records={len(data)}")
                    return fig
                else:
                    print(f"DEBUG: Unknown tab: {active_tab}")
                    dt_ms = (perf_counter() - t0) * 1000
                    print(f"PERF update_charts duration_ms={dt_ms:.1f} reason=unknown_tab active_tab={active_tab}")
                    return create_empty_chart("Выберите вкладку для визуализации")
            except Exception as e:
                print(f"ERROR: Failed to create chart for {active_tab}: {e}")
                import traceback
                traceback.print_exc()
                dt_ms = (perf_counter() - t0) * 1000
                print(f"PERF update_charts duration_ms={dt_ms:.1f} error={str(e)} active_tab={active_tab}")
                return create_empty_chart(f"Ошибка при создании графика: {str(e)}")
        except Exception as e:
            print(f"ERROR: Exception in update_charts: {e}")
            import traceback
            traceback.print_exc()
            return create_empty_chart(f"Ошибка при обновлении графиков: {str(e)}")

