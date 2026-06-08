from pathlib import Path
import sqlite3
from datetime import datetime, timezone, timedelta

DB_PATH = Path(__file__).resolve().parent.parent / "telemetry.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Device IDs to remove
    to_remove = [
        "fridge-LG1",
        "fridge-LG2",
        "fridge-MI1",
        "fridge-MI2",
        "fridge-SONE1",
        "fridge-SONE2",
    ]

    # New device IDs to add
    to_add = [
        "Helmet scientific",
        "PHcbi (formerly panasonic healthcare)",
        "Thermo fisher scientific",
        "LG",
        "Samsung",
        "Whirlpool",
    ]

    # Delete old devices
    placeholders = ",".join("?" for _ in to_remove)
    cur.execute(f"DELETE FROM telemetry WHERE device_id IN ({placeholders})", tuple(to_remove))
    deleted = cur.rowcount
    print(f"Deleted {deleted} telemetry rows for specified old devices.")

    # Insert a single sample reading per new device (if not already present)
    now = datetime.now(timezone.utc)
    for idx, dev in enumerate(to_add):
        # Check if device already has any rows
        cur.execute("SELECT 1 FROM telemetry WHERE device_id = ? LIMIT 1", (dev,))
        if cur.fetchone():
            print(f"Device already exists, skipping insert: {dev}")
            continue

        ts = (now - timedelta(minutes=idx)).isoformat()
        temperature_c = 5.0
        humidity_pct = 55.0
        door_open = 0
        power_ok = 1

        cur.execute(
            "INSERT OR REPLACE INTO telemetry (device_id, timestamp, temperature_c, humidity_pct, door_open, power_ok) VALUES (?, ?, ?, ?, ?, ?)",
            (dev, ts, temperature_c, humidity_pct, door_open, power_ok),
        )
        print(f"Inserted sample reading for device: {dev}")

    conn.commit()
    conn.close()
    print("Database update complete.")


if __name__ == "__main__":
    main()
