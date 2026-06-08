from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class TelemetryReading:
    device_id: str
    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    door_open: bool
    power_ok: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelemetryReading":
        if not isinstance(data, dict):
            raise ValueError("Telemetry payload must be a JSON object")

        device_id = data.get("device_id")
        if not isinstance(device_id, str):
            raise ValueError("device_id must be a string")

        timestamp_value = data.get("timestamp")
        if isinstance(timestamp_value, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_value)
            except ValueError:
                raise ValueError("timestamp must be an ISO 8601 datetime string")
        elif isinstance(timestamp_value, datetime):
            timestamp = timestamp_value
        else:
            raise ValueError("timestamp is required and must be an ISO 8601 string")

        temperature_c = data.get("temperature_c")
        if not isinstance(temperature_c, (int, float)):
            raise ValueError("temperature_c must be a number")

        humidity_pct = data.get("humidity_pct")
        if not isinstance(humidity_pct, (int, float)):
            raise ValueError("humidity_pct must be a number")

        door_open = data.get("door_open")
        if not isinstance(door_open, bool):
            raise ValueError("door_open must be a boolean")

        power_ok = data.get("power_ok")
        if not isinstance(power_ok, bool):
            raise ValueError("power_ok must be a boolean")

        return cls(
            device_id=device_id,
            timestamp=timestamp,
            temperature_c=float(temperature_c),
            humidity_pct=float(humidity_pct),
            door_open=door_open,
            power_ok=power_ok,
        )


@dataclass
class AlertStatus:
    device_id: str
    alert_level: str
    message: str
    triggered_at: datetime


@dataclass
class AlertHistoryItem:
    device_id: str
    timestamp: datetime
    alert_level: str
    message: str
    temperature_c: float
    humidity_pct: float
    door_open: bool
    power_ok: bool


@dataclass
class DashboardStatus:
    device_id: str
    last_reading: TelemetryReading
    alert_status: AlertStatus | None
    healthy: bool
