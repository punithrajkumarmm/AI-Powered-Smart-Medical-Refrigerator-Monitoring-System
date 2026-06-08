from datetime import datetime, timedelta
import sqlite3
from typing import List

from .db import get_connection
from .schemas import TelemetryReading

READ_LATEST_SQL = """
SELECT t.device_id, t.timestamp, t.temperature_c, t.humidity_pct, t.door_open, t.power_ok
FROM telemetry t
JOIN (
    SELECT device_id, MAX(timestamp) AS max_ts
    FROM telemetry
    GROUP BY device_id
) latest ON t.device_id = latest.device_id AND t.timestamp = latest.max_ts;
"""

READ_HISTORY_SQL = """
SELECT device_id, timestamp, temperature_c, humidity_pct, door_open, power_ok
FROM telemetry
WHERE device_id = ?
ORDER BY timestamp ASC;
"""

class TelemetryStore:
    def __init__(self) -> None:
        self._conn = get_connection()

    def save(self, reading: TelemetryReading) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO telemetry (device_id, timestamp, temperature_c, humidity_pct, door_open, power_ok) VALUES (?, ?, ?, ?, ?, ?)",
            (
                reading.device_id,
                reading.timestamp.isoformat(),
                reading.temperature_c,
                reading.humidity_pct,
                int(reading.door_open),
                int(reading.power_ok),
            ),
        )
        self._conn.commit()

    def latest(self, device_id: str) -> TelemetryReading | None:
        row = self._conn.execute(
            "SELECT device_id, timestamp, temperature_c, humidity_pct, door_open, power_ok FROM telemetry WHERE device_id = ? ORDER BY timestamp DESC LIMIT 1",
            (device_id,),
        ).fetchone()
        return self._row_to_reading(row) if row else None

    def all_latest(self) -> List[TelemetryReading]:
        rows = self._conn.execute(READ_LATEST_SQL).fetchall()
        return [self._row_to_reading(row) for row in rows]

    def history(self, device_id: str) -> List[TelemetryReading]:
        rows = self._conn.execute(READ_HISTORY_SQL, (device_id,)).fetchall()
        return [self._row_to_reading(row) for row in rows]

    def delete_device(self, device_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM telemetry WHERE device_id = ?", (device_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def rename_device(self, old_device_id: str, new_device_id: str) -> bool:
        cursor = self._conn.execute(
            "UPDATE telemetry SET device_id = ? WHERE device_id = ?",
            (new_device_id, old_device_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete_all_devices(self) -> int:
        cursor = self._conn.execute("DELETE FROM telemetry")
        self._conn.commit()
        return cursor.rowcount

    def delete_devices_older_than(self, days: int) -> int:
        """Delete all telemetry for devices whose latest reading is older than `days`.

        Returns the number of devices deleted.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()

        rows = self._conn.execute(
            "SELECT device_id FROM telemetry GROUP BY device_id HAVING MAX(timestamp) < ?",
            (cutoff_iso,),
        ).fetchall()
        device_ids = [row["device_id"] for row in rows]
        if not device_ids:
            return 0

        placeholders = ",".join("?" for _ in device_ids)
        cursor = self._conn.execute(f"DELETE FROM telemetry WHERE device_id IN ({placeholders})", tuple(device_ids))
        self._conn.commit()
        return len(device_ids)

    def _row_to_reading(self, row: sqlite3.Row) -> TelemetryReading:
        return TelemetryReading(
            device_id=row["device_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            temperature_c=row["temperature_c"],
            humidity_pct=row["humidity_pct"],
            door_open=bool(row["door_open"]),
            power_ok=bool(row["power_ok"]),
        )

store = TelemetryStore()
