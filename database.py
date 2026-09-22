"""
database.py - SQLite database setup and helper functions for BlueMindAI.
Stores coastal Indian cities and history of marine safety queries.
"""

import sqlite3
import os
from typing import List, Dict, Optional, Any

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bluemind.db")

# 10 Major Indian coastal cities with coordinates
INITIAL_CITIES = [
    {"name": "Mumbai", "state": "Maharashtra", "lat": 18.9220, "lon": 72.8347},
    {"name": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707},
    {"name": "Kochi", "state": "Kerala", "lat": 9.9312, "lon": 76.2673},
    {"name": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2185},
    {"name": "Mangaluru", "state": "Karnataka", "lat": 12.9141, "lon": 74.8560},
    {"name": "Panaji (Goa)", "state": "Goa", "lat": 15.4909, "lon": 73.8278},
    {"name": "Puri", "state": "Odisha", "lat": 19.8135, "lon": 85.8312},
    {"name": "Veraval", "state": "Gujarat", "lat": 20.9000, "lon": 70.3667},
    {"name": "Kanyakumari", "state": "Tamil Nadu", "lat": 8.0883, "lon": 77.5385},
    {"name": "Digha", "state": "West Bengal", "lat": 21.6266, "lon": 87.5074},
]


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Returns a SQLite connection with dict-like row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes tables and seeds initial coastal Indian cities."""
    conn = get_connection(db_path)
    with conn:
        # Create cities table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                state TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL
            )
        """)

        # Create history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                city_name TEXT NOT NULL,
                target_day TEXT NOT NULL,
                forecast_date TEXT,
                wave_height_m REAL,
                wind_speed_kmh REAL,
                wind_gusts_kmh REAL,
                verdict TEXT NOT NULL,
                badge_color TEXT NOT NULL,
                explanation TEXT NOT NULL
            )
        """)

        # Seed cities if empty
        cursor = conn.execute("SELECT COUNT(*) as count FROM cities")
        if cursor.fetchone()["count"] == 0:
            for city in INITIAL_CITIES:
                conn.execute(
                    "INSERT INTO cities (name, state, latitude, longitude) VALUES (?, ?, ?, ?)",
                    (city["name"], city["state"], city["lat"], city["lon"])
                )
    conn.close()


def get_cities(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Returns all seeded coastal cities."""
    conn = get_connection(db_path)
    cursor = conn.execute("SELECT id, name, state, latitude, longitude FROM cities ORDER BY name ASC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_city_by_name(name: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetches a single city record by name (case-insensitive)."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT id, name, state, latitude, longitude FROM cities WHERE LOWER(name) = LOWER(?)",
        (name.strip(),)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_history(record: Dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> int:
    """Saves a marine safety query and verdict to history."""
    conn = get_connection(db_path)
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO history (
                city_name, target_day, forecast_date, wave_height_m,
                wind_speed_kmh, wind_gusts_kmh, verdict, badge_color, explanation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("city_name"),
                record.get("target_day"),
                record.get("forecast_date"),
                record.get("wave_height_m"),
                record.get("wind_speed_kmh"),
                record.get("wind_gusts_kmh"),
                record.get("verdict"),
                record.get("badge_color"),
                record.get("explanation"),
            )
        )
        inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id


def get_history(limit: int = 20, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves recent queries from history."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        """
        SELECT id, timestamp, city_name, target_day, forecast_date,
               wave_height_m, wind_speed_kmh, wind_gusts_kmh, verdict, badge_color, explanation
        FROM history
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
    cities = get_cities()
    print(f"Loaded {len(cities)} coastal cities:")
    for c in cities:
        print(f" - {c['name']} ({c['state']}): {c['latitude']}, {c['longitude']}")
