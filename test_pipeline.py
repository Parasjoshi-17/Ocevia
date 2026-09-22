"""
test_pipeline.py - Comprehensive verification suite for BlueMindAI.
Tests:
  1. SQLite database setup, seeding 10 cities, history persistence.
  2. Open-Meteo live API integration for marine wave and weather data.
  3. Deterministic rule engine thresholds (DO NOT VENTURE / CAUTION / SAFE).
  4. Hinglish AI explanation generator & fallback.
  5. Flask endpoints (/, /api/cities, /api/ask, /api/history).
"""

import os
import unittest
from database import init_db, get_cities, get_city_by_name, save_history, get_history
from weather import get_live_marine_weather
from rules import evaluate_safety
from ai_explain import get_ai_explanation, generate_fallback_explanation
from app import app

TEST_DB = "test_bluemind.db"


class TestBlueMindAI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        init_db(TEST_DB)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_01_database_seeding(self):
        cities = get_cities(TEST_DB)
        self.assertGreaterEqual(len(cities), 10)
        city_names = [c["name"] for c in cities]
        self.assertIn("Mumbai", city_names)
        self.assertIn("Chennai", city_names)
        self.assertIn("Kochi", city_names)
        self.assertIn("Visakhapatnam", city_names)

        mumbai = get_city_by_name("mumbai", TEST_DB)
        self.assertIsNotNone(mumbai)
        self.assertAlmostEqual(mumbai["latitude"], 18.9220, places=2)

    def test_02_database_history(self):
        record = {
            "city_name": "Mumbai",
            "target_day": "tomorrow",
            "forecast_date": "2026-09-16",
            "wave_height_m": 1.2,
            "wind_speed_kmh": 22.0,
            "wind_gusts_kmh": 35.0,
            "verdict": "SAFE",
            "badge_color": "green",
            "explanation": "Namaste bhai! Samundar shant hai."
        }
        rec_id = save_history(record, TEST_DB)
        self.assertIsInstance(rec_id, int)
        history = get_history(limit=5, db_path=TEST_DB)
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["city_name"], "Mumbai")
        self.assertEqual(history[0]["verdict"], "SAFE")

    def test_03_weather_live_api(self):
        # Fetch live data for Mumbai
        data = get_live_marine_weather(18.9220, 72.8347, "tomorrow")
        self.assertEqual(data["target_day"], "tomorrow")
        self.assertIn("wave_height_m", data)
        self.assertIn("wind_speed_kmh", data)
        self.assertIn("wind_gusts_kmh", data)
        self.assertGreater(data["wave_height_m"], 0)
        self.assertGreater(data["wind_speed_kmh"], 0)
        self.assertEqual(data["raw_source"], "Open-Meteo Live API")

    def test_04_rules_thresholds(self):
        # DO NOT VENTURE: wave > 2.5
        r1 = evaluate_safety(2.6, 20.0, 30.0)
        self.assertEqual(r1["verdict"], "DO NOT VENTURE")
        self.assertEqual(r1["badge_color"], "red")

        # DO NOT VENTURE: wind > 45
        r2 = evaluate_safety(1.2, 46.0, 50.0)
        self.assertEqual(r2["verdict"], "DO NOT VENTURE")
        self.assertEqual(r2["badge_color"], "red")

        # DO NOT VENTURE: gust > 60
        r3 = evaluate_safety(1.2, 30.0, 62.0)
        self.assertEqual(r3["verdict"], "DO NOT VENTURE")
        self.assertEqual(r3["badge_color"], "red")

        # CAUTION: wave > 1.5
        r4 = evaluate_safety(1.6, 20.0, 30.0)
        self.assertEqual(r4["verdict"], "CAUTION")
        self.assertEqual(r4["badge_color"], "yellow")

        # CAUTION: wind > 25
        r5 = evaluate_safety(1.0, 26.0, 30.0)
        self.assertEqual(r5["verdict"], "CAUTION")
        self.assertEqual(r5["badge_color"], "yellow")

        # SAFE: wave <= 1.5, wind <= 25, gust <= 60
        r6 = evaluate_safety(1.0, 18.0, 25.0)
        self.assertEqual(r6["verdict"], "SAFE")
        self.assertEqual(r6["badge_color"], "green")

    def test_05_ai_explanation_and_fallback(self):
        expl_safe = generate_fallback_explanation("Mumbai", "tomorrow", "SAFE", 1.0, 15.0, 20.0, ["Calm"])
        self.assertIn("SAFE", expl_safe)
        self.assertIn("Mumbai", expl_safe)
        self.assertLess(len(expl_safe.split()), 60)

        expl_danger = generate_fallback_explanation("Veraval", "today", "DO NOT VENTURE", 2.8, 50.0, 65.0, ["High waves"])
        self.assertIn("DO NOT VENTURE", expl_danger)
        self.assertIn("Veraval", expl_danger)
        self.assertLess(len(expl_danger.split()), 60)

    def test_06_flask_routes(self):
        client = app.test_client()

        # GET /
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"BlueMindAI", resp.data)

        # GET /api/cities
        resp_cities = client.get("/api/cities")
        self.assertEqual(resp_cities.status_code, 200)
        json_cities = resp_cities.get_json()
        self.assertEqual(json_cities["status"], "success")
        self.assertGreaterEqual(len(json_cities["cities"]), 10)

        # POST /api/ask (Live test for Mumbai, Tomorrow)
        resp_ask = client.post("/api/ask", json={"city": "Mumbai", "day": "tomorrow"})
        self.assertEqual(resp_ask.status_code, 200)
        json_ask = resp_ask.get_json()
        self.assertEqual(json_ask["status"], "success")
        self.assertEqual(json_ask["city"], "Mumbai")
        self.assertIn(json_ask["verdict"], ["SAFE", "CAUTION", "DO NOT VENTURE"])
        self.assertIn(json_ask["badge_color"], ["green", "yellow", "red"])
        self.assertIn("metrics", json_ask)
        self.assertGreater(json_ask["metrics"]["wave_height_m"], 0)

        # GET /api/history
        resp_hist = client.get("/api/history")
        self.assertEqual(resp_hist.status_code, 200)
        json_hist = resp_hist.get_json()
        self.assertEqual(json_hist["status"], "success")
        self.assertGreaterEqual(len(json_hist["history"]), 1)


if __name__ == "__main__":
    unittest.main()
