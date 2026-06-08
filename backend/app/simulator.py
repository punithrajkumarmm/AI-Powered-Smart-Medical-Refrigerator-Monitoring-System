from datetime import datetime, timezone
import random

from .schemas import TelemetryReading

SCENARIOS = ["normal", "door_open", "high_temperature", "high_humidity", "power_loss"]


def generate_sample_reading(device_id: str, scenario: str = "normal") -> TelemetryReading:
    now = datetime.now(timezone.utc)
    base_temp = 5.0
    base_humidity = 55.0
    door_open = False
    power_ok = True

    if scenario == "door_open":
        door_open = True
        temperature_c = round(base_temp + random.uniform(0.8, 1.8), 1)
        humidity_pct = round(base_humidity + random.uniform(4.0, 8.0), 1)
    elif scenario == "high_temperature":
        temperature_c = round(random.uniform(9.0, 14.0), 1)
        humidity_pct = round(base_humidity + random.uniform(1.0, 4.0), 1)
    elif scenario == "high_humidity":
        temperature_c = round(base_temp + random.uniform(-0.3, 0.5), 1)
        humidity_pct = round(random.uniform(72.0, 85.0), 1)
    elif scenario == "power_loss":
        power_ok = False
        temperature_c = round(base_temp + random.uniform(0.2, 0.8), 1)
        humidity_pct = round(base_humidity + random.uniform(1.0, 3.0), 1)
    else:
        temperature_c = round(base_temp + random.uniform(-0.7, 0.7), 1)
        humidity_pct = round(base_humidity + random.uniform(-4.0, 4.0), 1)

    return TelemetryReading(
        device_id=device_id,
        timestamp=now,
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        door_open=door_open,
        power_ok=power_ok,
    )
