import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "telemetry.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_connection = sqlite3.connect(DB_PATH, check_same_thread=False)
_connection.row_factory = sqlite3.Row

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS telemetry (
    device_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    temperature_c REAL NOT NULL,
    humidity_pct REAL NOT NULL,
    door_open INTEGER NOT NULL,
    power_ok INTEGER NOT NULL,
    PRIMARY KEY (device_id, timestamp)
);
"""

_connection.execute(CREATE_TABLE)
_connection.commit()


def get_connection() -> sqlite3.Connection:
    return _connection
