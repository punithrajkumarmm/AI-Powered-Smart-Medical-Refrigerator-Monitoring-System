from datetime import datetime
from .schemas import AlertStatus, TelemetryReading

TEMP_MIN_C = 2.0
TEMP_MAX_C = 8.0
HUMIDITY_MAX_PCT = 70.0

ALERT_PRIORITY = {
    "critical": 3,
    "warning": 2,
    "normal": 1,
}


def evaluate_alert(reading: TelemetryReading) -> AlertStatus | None:
    now = datetime.utcnow()
    
    # Critical: Power failure
    if not reading.power_ok:
        return AlertStatus(
            device_id=reading.device_id,
            alert_level="RED - Critical",
            message="⚡ Power failure detected - Immediate action required!",
            triggered_at=now,
        )

    # Red: Temperature critically high (>10°C)
    if reading.temperature_c > 10.0:
        return AlertStatus(
            device_id=reading.device_id,
            alert_level="RED - Immediate Action",
            message=f"🔴 CRITICAL: Temperature {reading.temperature_c}°C - Vaccine spoilage risk HIGH",
            triggered_at=now,
        )

    # Red: Temperature critically low (<0°C)
    if reading.temperature_c < 0.0:
        return AlertStatus(
            device_id=reading.device_id,
            alert_level="RED - Immediate Action",
            message=f"🔴 CRITICAL: Temperature {reading.temperature_c}°C - Freezing risk",
            triggered_at=now,
        )

    # Orange: Temperature high risk (9-10°C)
    if 9.0 <= reading.temperature_c <= 10.0:
        return AlertStatus(
            device_id=reading.device_id,
            alert_level="ORANGE - High Risk",
            message=f"🟠 WARNING: Temperature {reading.temperature_c}°C - Vaccine spoilage risk increasing",
            triggered_at=now,
        )

    # Orange: Temperature low risk (0-1°C)
    if 0.0 <= reading.temperature_c < 1.0:
        return AlertStatus(
            device_id=reading.device_id,
            alert_level="ORANGE - High Risk",
            message=f"🟠 WARNING: Temperature {reading.temperature_c}°C - Risk of freezing damage",
            triggered_at=now,
        )

    # Yellow: Temperature warm (8-9°C)
    if 8.0 < reading.temperature_c < 9.0:
        return AlertStatus(
            device_id=reading.device_id,
            alert_level="YELLOW - Potential Issue",
            message=f"🟡 NOTICE: Temperature {reading.temperature_c}°C - Monitor closely",
            triggered_at=now,
        )

    # Yellow: Temperature cool (1-2°C)
    if 1.0 <= reading.temperature_c < 2.0:
        return AlertStatus(
            device_id=reading.device_id,
            alert_level="YELLOW - Potential Issue",
            message=f"🟡 NOTICE: Temperature {reading.temperature_c}°C - Slightly below range",
            triggered_at=now,
        )

    # Yellow: Door open
    if reading.door_open:
        return AlertStatus(
            device_id=reading.device_id,
            alert_level="YELLOW - Potential Issue",
            message="🚪 NOTICE: Door is open - Please close",
            triggered_at=now,
        )

    # Yellow: High humidity
    if reading.humidity_pct > HUMIDITY_MAX_PCT:
        return AlertStatus(
            device_id=reading.device_id,
            alert_level="YELLOW - Potential Issue",
            message=f"💧 NOTICE: Humidity {reading.humidity_pct}% exceeds threshold ({HUMIDITY_MAX_PCT}%)",
            triggered_at=now,
        )

    # Green: Normal operation
    return None
