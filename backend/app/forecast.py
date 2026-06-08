from __future__ import annotations

from typing import List, Optional

import numpy as np

try:
    import tensorflow as tf
    from tensorflow.keras.layers import Dense, LSTM
    from tensorflow.keras.models import Sequential
except ImportError:  # pragma: no cover
    tf = None

from .schemas import TelemetryReading

from .schemas import TelemetryReading

LOOKBACK_HOURS = 48
FORECAST_HOURS = 24


def _build_sequences(history: List[TelemetryReading], lookback: int = LOOKBACK_HOURS):
    temps = [reading.temperature_c for reading in history]
    if len(temps) < lookback + 1:
        return None, None

    x = []
    y = []
    for start in range(len(temps) - lookback):
        x.append(temps[start : start + lookback])
        y.append(temps[start + lookback])

    x_arr = np.array(x, dtype=np.float32).reshape(-1, lookback, 1)
    y_arr = np.array(y, dtype=np.float32)
    return x_arr, y_arr


def _build_model(input_shape: tuple[int, int]) -> Sequential:
    model = Sequential(
        [
            LSTM(64, input_shape=input_shape),
            Dense(1),
        ]
    )
    model.compile(optimizer="adam", loss="mean_squared_error")
    return model


def forecast_next_24_hours(history: List[TelemetryReading]) -> Optional[List[float]]:
    if tf is None:
        return None

    x, y = _build_sequences(history)
    if x is None or y is None or len(x) < 2:
        return None

    model = _build_model((x.shape[1], x.shape[2]))
    model.fit(x, y, epochs=20, batch_size=8, verbose=0)

    last_window = np.array([reading.temperature_c for reading in history[-LOOKBACK_HOURS:]], dtype=np.float32).reshape(1, LOOKBACK_HOURS, 1)
    predictions: list[float] = []

    for _ in range(FORECAST_HOURS):
        next_temp = float(model.predict(last_window, verbose=0)[0, 0])
        rounded_temp = round(next_temp, 1)
        predictions.append(rounded_temp)

        last_window = np.roll(last_window, -1, axis=1)
        last_window[0, -1, 0] = next_temp

    return predictions
