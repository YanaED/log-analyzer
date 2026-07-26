"""
Модуль машинного обучения для выявления аномалий в логах.
Используется Isolation Forest (неконтролируемое обучение).
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

FEATURE_NAMES_RU = {
    'hour': 'час',
    'day_of_week': 'день недели',
    'msg_len': 'длина сообщения',
}
TOP_REASONS_N = 3

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def _extract_features(df: pd.DataFrame, include_msg_len: bool = True) -> pd.DataFrame:
    """Извлечение признаков из логов для модели аномалий."""
    features = pd.DataFrame(index=df.index)
    
    if 'timestamp' in df.columns:
        ts = pd.to_datetime(df['timestamp'], errors='coerce')
        features['hour'] = ts.dt.hour.fillna(0).astype(int)
        features['day_of_week'] = ts.dt.dayofweek.fillna(0).astype(int)
    else:
        features['hour'] = 0
        features['day_of_week'] = 0

    if include_msg_len:
        if 'message' in df.columns:
            features['msg_len'] = df['message'].astype(str).str.len().fillna(0)
        elif 'raw_message' in df.columns:
            features['msg_len'] = df['raw_message'].astype(str).str.len().fillna(0)
        else:
            features['msg_len'] = 0

    return features


def _compute_anomaly_reasons(
    X: pd.DataFrame,
    anomaly_mask: np.ndarray,
    feature_names_ru: Dict[str, str],
    top_n: int = TOP_REASONS_N,
) -> pd.Series:
    """
    Для каждой аномальной записи определяет признаки, сильнее всего отличающиеся от медианы.
    Возвращает Series (index = index из X) со строкой вида "час: выше среднего; частота IP: ниже среднего".
    """
    median = X.median()
    std = X.std().replace(0, 1)  # избегаем деления на ноль
    reasons_by_idx = {}
    for idx in X.index[anomaly_mask]:
        row = X.loc[idx]
        z = (row - median) / std
        z = z.replace([np.inf, -np.inf], 0).fillna(0)
        top = z.abs().nlargest(top_n)
        parts = []
        for feat in top.index:
            name_ru = feature_names_ru.get(feat, feat)
            direction = "выше среднего" if z[feat] > 0 else "ниже среднего"
            parts.append(f"{name_ru}: {direction}")
        reasons_by_idx[idx] = "; ".join(parts) if parts else "—"
    return pd.Series(reasons_by_idx)


def detect_anomalies(
    df: pd.DataFrame,
    contamination: float = 0.1,
    random_state: int = 42,
    max_samples: Optional[int] = 256,
    include_msg_len: bool = True,
) -> Dict:
    """
    Выявление аномалий в логах с помощью Isolation Forest.
    
    :param df: DataFrame с логами (колонки: timestamp, level, http_status, ip_address, message/raw_message, url и т.д.)
    :param contamination: доля ожидаемых аномалий (0.01–0.2), по умолчанию 0.1
    :param random_state: seed для воспроизводимости
    :param max_samples: макс. число образцов для обучения (для скорости)
    :return: dict с ключами: anomaly_indices, anomaly_scores, n_anomalies, n_total, df_flagged, success, error
    """
    result = {
        'anomaly_indices': [],
        'anomaly_scores': [],
        'n_anomalies': 0,
        'n_total': len(df),
        'df_flagged': None,
        'success': False,
        'error': None,
    }
    
    if not SKLEARN_AVAILABLE:
        result['error'] = 'Не установлена библиотека scikit-learn. Выполните: pip install scikit-learn'
        return result
    
    if df is None or df.empty or len(df) < 10:
        result['error'] = 'Недостаточно данных для анализа (нужно минимум 10 записей).'
        return result
    
    try:
        features = _extract_features(df, include_msg_len=include_msg_len)
        X = features.fillna(0).astype(float)
        
        n_samples = min(max_samples or len(X), len(X))
        model = IsolationForest(
            contamination=min(max(0.01, contamination), 0.5),
            random_state=random_state,
            max_samples=n_samples,
            n_estimators=100,
        )
        predictions = model.fit_predict(X)  # -1 = аномалия, 1 = норма
        scores = model.decision_function(X)  # чем ниже — тем более аномально
        
        anomaly_mask = predictions == -1
        result['anomaly_indices'] = df.index[anomaly_mask].tolist()
        result['anomaly_scores'] = scores[anomaly_mask].tolist()
        result['n_anomalies'] = int(anomaly_mask.sum())
        result['success'] = True

        df_flagged = df.copy()
        df_flagged['_anomaly'] = anomaly_mask.astype(int)
        df_flagged['_anomaly_score'] = scores
        reasons = _compute_anomaly_reasons(X, anomaly_mask, FEATURE_NAMES_RU)
        df_flagged['_anomaly_reasons'] = reasons.reindex(df_flagged.index).fillna('').astype(str)
        result['df_flagged'] = df_flagged

    except Exception as e:
        result['error'] = str(e)
    
    return result
