"""
test_ocevia_flow.py - OFFLINE plumbing tests for OCEVIA.

These tests never touch the network. They stub the weather/ocean/
safety/explanation agents (whose source is not part of this file set)
and Open-Meteo/INCOIS HTTP, so they verify ROUTING and LOGIC:

    city / day / time-window resolution, region selection,
    PFZ normalization, fishing-opportunity rules, API contracts.

They do NOT verify that live Open-Meteo / INCOIS data is real - use
tools/live_check.py against a running backend for that.

Run:  python -m unittest test_ocevia_flow -v
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

IST = timezone(timedelta(hours=5, minutes=30))

# Scenario knobs for the stub agents (test fixtures only).
SCENARIO = {"wave": 1.0, "wind": 15.0, "gust": 22.0, "sst": 28.0}
AGENT_CALLS = []


def install_offline_stubs():
    """
    Uses the project's REAL agents (weather/ocean/safety/explanation) and
    the REAL deterministic rules engine. Only the two network data sources
    are replaced by fixtures, and Claude is disabled so ai_explain uses
    its built-in fallback text.
    """

    os.environ.pop("ANTHROPIC_API_KEY", None)

    import agents.weather_agent as weather_agent
    import agents.ocean_agent as ocean_agent

    def hourly(kind, date):
        rows = []
        for h in range(24):
            t = f"{date}T{h:02d}:00"
            if kind == "weather":
                rows.append({"time": t, "temperature": 30.0,
                             "wind_speed": SCENARIO["wind"], "wind_direction": 250.0,
                             "wind_gust": SCENARIO["gust"], "precipitation": 0.0})
            else:
                rows.append({"time": t, "wave_height": SCENARIO["wave"], "wave_direction": 220.0,
                             "wind_wave_height": 0.5, "wind_wave_direction": 240.0,
                             "sea_surface_temperature": SCENARIO["sst"]})
        return rows

    def get_weather(latitude, longitude, date):
        AGENT_CALLS.append(("weather", latitude, longitude, date))
        return {"weather": {"hourly": hourly("weather", date)}, "source": "fixture"}

    def get_marine(latitude, longitude, date):
        AGENT_CALLS.append(("ocean", latitude, longitude, date))
        return {"marine": {"hourly": hourly("marine", date)}, "source": "fixture"}

    weather_agent.get_weather = get_weather
    ocean_agent.get_marine = get_marine


install_offline_stubs()

import pfz  # noqa: E402
import map_data  # noqa: E402
import fishing_suitability as fs  # noqa: E402
from intent_parser import parse_query  # noqa: E402
from database import INITIAL_CITIES  # noqa: E402
from app import app  # noqa: E402

CITIES = [c["name"] for c in INITIAL_CITIES]
BY_NAME = {c["name"]: c for c in INITIAL_CITIES}

LANDING_HTML = (
    "<html><body><select><option>GUJARAT</option><option>KERALA</option></select>"
    "<table><tr><th>Forecast Date</th><th>Valid upto</th></tr>"
    "<tr><td>19 SEP 2026</td><td>20 SEP 2026</td></tr></table></body></html>"
)


def tomorrow_ist():
    return (datetime.now(IST).date() + timedelta(days=1)).isoformat()


def today_ist_str():
    return datetime.now(IST).date().isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        SCENARIO.update({"wave": 1.0, "wind": 15.0, "gust": 22.0, "sst": 28.0})
        AGENT_CALLS.clear()
        pfz.clear_cache()
        map_data.clear_cache()
        os.environ.pop(pfz.SECTOR_URL_ENV, None)
        self._orig_http = pfz._http_get_text
        pfz._http_get_text = lambda url, timeout: LANDING_HTML
        self.client = app.test_client()

    def tearDown(self):
        pfz._http_get_text = self._orig_http
        os.environ.pop(pfz.SECTOR_URL_ENV, None)


class TestIntentParser(unittest.TestCase):
    def test_explicit_flags(self):
        p = parse_query("Is it safe to go fishing tomorrow?")
        self.assertIsNone(p["city"])
        self.assertTrue(p["target_day_explicit"])
        self.assertFalse(p["time_window_explicit"])
        p = parse_query("Where should I go fishing?")
        self.assertFalse(p["target_day_explicit"])
        p = parse_query("Can I go fishing near Vizag today evening?")
        self.assertEqual((p["city"], p["target_day"], p["time_window"]),
                         ("Visakhapatnam", "today", "evening"))


class TestAskCityFlow(Base):
    def ask(self, **body):
        return self.client.post("/api/ask", json=body)

    def test_all_ten_cities_via_explicit_context(self):
        """Home quick question has NO city in the text; the selected city must be used."""
        for name in CITIES:
            with self.subTest(city=name):
                AGENT_CALLS.clear()
                r = self.ask(query="Is it safe to go fishing tomorrow?", city=name,
                             target_day="Tomorrow", time_window="morning")
                self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
                j = r.get_json()
                self.assertEqual(j["city"], name)
                self.assertEqual(j["resolved_from"]["city"], "request")
                self.assertEqual(j["forecast_date"], tomorrow_ist())
                self.assertEqual(j["time_window"], "morning")
                self.assertEqual(j["hours_evaluated"], 5)  # 06..10
                self.assertEqual([round(j["coordinates"]["latitude"], 4), round(j["coordinates"]["longitude"], 4)],
                                 [BY_NAME[name]["lat"], BY_NAME[name]["lon"]])
                # weather + ocean agents were called with THIS city's numeric coordinates
                for kind, lat, lon, d in AGENT_CALLS:
                    self.assertIsInstance(lat, float)
                    self.assertEqual((lat, lon, d), (BY_NAME[name]["lat"], BY_NAME[name]["lon"], tomorrow_ist()))
                self.assertIn(j["verdict"], ("SAFE", "CAUTION", "DO NOT VENTURE"))

    def test_query_city_wins_over_context_and_natural_language_fallback(self):
        r = self.ask(query="Can I go fishing tomorrow morning near Kochi?", city="Mumbai")
        j = r.get_json()
        self.assertEqual((j["city"], j["resolved_from"]["city"]), ("Kochi", "query"))
        self.assertEqual((j["time_window"], j["resolved_from"]["time_window"]), ("morning", "query"))
        # natural language only (no explicit city field at all)
        j = self.ask(query="Can I go fishing tomorrow morning near Chennai?").get_json()
        self.assertEqual(j["city"], "Chennai")

    def test_day_and_window_from_request_when_query_silent(self):
        j = self.ask(query="Where should I go fishing?", city="Puri",
                     target_day="Day After Tomorrow", time_window="evening").get_json()
        exp = (datetime.now(IST).date() + timedelta(days=2)).isoformat()
        self.assertEqual((j["forecast_date"], j["time_window"]), (exp, "evening"))
        self.assertEqual(j["resolved_from"]["target_day"], "request")

    def test_query_day_beats_request_day(self):
        j = self.ask(query="safe to fish today?", city="Puri", target_day="Day After Tomorrow").get_json()
        self.assertEqual(j["forecast_date"], today_ist_str())

    def test_missing_city_is_400_not_mumbai(self):
        r = self.ask(query="Is it safe to go fishing tomorrow?")
        self.assertEqual(r.status_code, 400)
        self.assertIn("No city", r.get_json()["message"])
        self.assertEqual(AGENT_CALLS, [])

    def test_non_string_city_is_400(self):
        r = self.ask(query="q fishing", city={"name": "Kochi"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["message"], "City name must be a string.")

    def test_unknown_city_404(self):
        self.assertEqual(self.ask(query="fishing tomorrow", city="Atlantis").status_code, 404)

    def test_structured_mode_still_works(self):
        j = self.ask(city="Digha", target_day="tomorrow", time_window="all_day").get_json()
        self.assertEqual((j["city"], j["input_mode"]), ("Digha", "structured"))
        self.assertEqual(j["hours_evaluated"], 24)


class TestSafetyAndFishing(Base):
    def test_do_not_venture_overrides_even_with_pfz(self):
        SCENARIO["wave"] = 3.0
        j = self.client.post("/api/ask", json={"query": "fishing tomorrow", "city": "Mumbai"}).get_json()
        self.assertEqual(j["verdict"], "DO NOT VENTURE")
        self.assertEqual(j["fishing"]["fishing_status"], "unsafe_do_not_venture")
        self.assertIn("Do not venture", j["fishing"]["message"])

    def test_pfz_unavailable_shape_and_message_in_ask(self):
        j = self.client.post("/api/ask", json={"query": "fishing tomorrow", "city": "Kochi"}).get_json()
        self.assertFalse(j["pfz"]["available"])
        self.assertEqual(j["pfz"]["sector"], "KERALA")
        self.assertEqual(j["pfz"]["message"], "No current PFZ advisory available for this region/date.")
        self.assertEqual(j["fishing"]["fishing_status"], "pfz_unavailable")
        self.assertEqual(j["fishing"]["message"], "No current PFZ advisory available for this region/date.")
        for forbidden in ("score", "probability", "suitability_score"):
            self.assertNotIn(forbidden, j["fishing"])
        self.assertEqual(j["fishing"]["environment"]["sea_surface_temperature_c"], {"min": 28.0, "max": 28.0})

    def test_thresholds_unchanged(self):
        import rules
        self.assertEqual(rules.evaluate_safety(2.5, 10, 10)["verdict"], "DO NOT VENTURE")
        self.assertEqual(rules.evaluate_safety(1.5, 10, 10)["verdict"], "CAUTION")
        self.assertEqual(rules.evaluate_safety(1.0, 10, 10)["verdict"], "SAFE")
        self.assertEqual(rules.evaluate_safety(None, 10, 10)["verdict"], "DATA UNAVAILABLE")

    def test_truth_table(self):
        avail = {"available": True, "zones": [{"latitude": 15.4, "longitude": 73.2}], "sector": "GOA"}
        unav = {"available": False, "message": "x", "sector": "GOA"}
        S = fs.evaluate_fishing_suitability
        self.assertEqual(S("SAFE", avail)["fishing_status"], "opportunity_indicated")
        self.assertEqual(S("CAUTION", avail)["fishing_status"], "opportunity_with_caution")
        self.assertEqual(S("SAFE", unav)["fishing_status"], "pfz_unavailable")
        self.assertEqual(S("CAUTION", None)["fishing_status"], "pfz_unavailable")
        self.assertEqual(S("DATA UNAVAILABLE", avail)["fishing_status"], "data_unavailable")
        self.assertEqual(S("BOGUS", avail)["fishing_status"], "data_unavailable")
        r = S("DO NOT VENTURE", avail)
        self.assertEqual(r["fishing_status"], "unsafe_do_not_venture")
        self.assertEqual(r["label"], "PFZ advisory available")
        self.assertEqual(r["message"], "Potential fishing activity may be indicated, but current marine conditions are unsafe. Do not venture.")
        # available=True but zero zones is NOT an advisory
        self.assertEqual(S("SAFE", {"available": True, "zones": []})["fishing_status"], "pfz_unavailable")


class TestPfz(Base):
    def test_sector_mapping_matches_incois_dropdown(self):
        official = {"GUJARAT", "MAHARASHTRA", "GOA", "KARNATAKA", "KERALA", "SOUTH TAMILNADU", "NORTH TAMILNADU",
                    "SOUTH ANDHRA PRADESH", "NORTH ANDHRA PRADESH", "ODISHA", "WEST BENGAL"}
        got = {pfz._get_sector(c["name"], c["state"]) for c in INITIAL_CITIES}
        self.assertTrue(got <= official, got - official)

    def test_landing_page_gives_dates_but_no_zones(self):
        r = pfz.get_pfz_advisory("Mumbai", "Maharashtra", "2026-09-20")
        self.assertFalse(r["available"])
        self.assertEqual((r["advisory_date"], r["valid_until"]), ("2026-09-19", "2026-09-20"))
        self.assertNotIn("zones", r)

    def test_site_unreachable(self):
        def boom(url, timeout): raise OSError("down")
        pfz._http_get_text = boom
        r = pfz.get_pfz_advisory("Mumbai", "Maharashtra", "2026-09-20")
        self.assertFalse(r["available"])
        self.assertNotIn("advisory_date", r)

    # NOTE: coordinates below are TEST FIXTURES (synthetic numbers used only to
    # exercise the parser and request plumbing). They never reach the product.
    LABELLED = ("Direction: E Bearing In Degrees: 90 Latitude: 16 55 54 Longitude: 82 59 26 "
                "Depth : 280.00-285.00 Landing center: Kakinada Type: PFZ")   # layout of a real INCOIS record (MSSRF mirror, 2018)

    def test_parser_reads_only_labelled_records(self):
        z = pfz._parse_zones(self.LABELLED)
        self.assertEqual(z, [{"latitude": 16.93167, "longitude": 82.99056}])
        junk = ("Call 040 2389 5000. HQ 17.33 N 78.60 E. Also 15.4 N 73.2 E. "
                "Latitude: 99 10 10 Longitude: 82 1 1. Latitude: 16 75 10 Longitude: 82 10 10. "
                "Latitude: 19 0 0 Longitude: 40 0 0.")
        self.assertEqual(pfz._parse_zones(junk), [])            # nothing unlabelled / invalid / outside EEZ
        self.assertEqual(pfz._parse_zones("<td>Latitude</td><td>19.25</td><td>Longitude</td><td>71.5</td>"),
                         [{"latitude": 19.25, "longitude": 71.5}])
        self.assertEqual(pfz._parse_zones(""), [])

    def configure_post_endpoint(self, window="20 SEP 2026</td><td>22 SEP 2026"):
        os.environ[pfz.SECTOR_URL_ENV] = "https://example.invalid/getpfz"
        os.environ[pfz.SECTOR_METHOD_ENV] = "POST"
        os.environ[pfz.SECTOR_BODY_ENV] = "sectorId={sector_id}&lang=en"
        os.environ[pfz.SECTOR_IDS_ENV] = ('{"MAHARASHTRA": "2", "KERALA": "5", "NORTH ANDHRA PRADESH": "9"}')
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in (
            pfz.SECTOR_METHOD_ENV, pfz.SECTOR_BODY_ENV, pfz.SECTOR_IDS_ENV, pfz.SECTOR_HEADERS_ENV)])
        landing = LANDING_HTML.replace("19 SEP 2026</td><td>20 SEP 2026", window)
        sent = []
        by_id = {"2": "Latitude: 19 0 0 Longitude: 71 0 0", "5": "Latitude: 9 30 0 Longitude: 75 30 0",
                 "9": "Latitude: 17 30 0 Longitude: 83 30 0"}

        def fake(url, timeout, data=None, headers=None):
            if "example.invalid" not in url:
                return landing
            sent.append((url, data, headers))
            return by_id[data.decode().split("&")[0].split("=")[1]]
        pfz._http_get_text = fake
        return sent

    def test_three_sectors_get_their_own_request_and_their_own_zones(self):
        sent = self.configure_post_endpoint()
        expect = {("Mumbai", "Maharashtra"): ("MAHARASHTRA", "sectorId=2&lang=en", 19.0, 71.0),
                  ("Kochi", "Kerala"): ("KERALA", "sectorId=5&lang=en", 9.5, 75.5),
                  ("Visakhapatnam", "Andhra Pradesh"): ("NORTH ANDHRA PRADESH", "sectorId=9&lang=en", 17.5, 83.5)}
        for (city, state), (sector, body, lat, lon) in expect.items():
            r = pfz.get_pfz_advisory(city, state, "2026-09-21")
            self.assertTrue(r["available"], r)
            self.assertEqual(r["sector"], sector)
            self.assertEqual(r["zones"], [{"latitude": lat, "longitude": lon}])
            self.assertEqual((r["advisory_date"], r["valid_until"]), ("2026-09-20", "2026-09-22"))
            self.assertEqual(sent[-1][1].decode(), body)
        self.assertEqual(len(sent), 3)
        pfz.get_pfz_advisory("Mumbai", "Maharashtra", "2026-09-21")          # cache: no 4th request
        self.assertEqual(len(sent), 3)

    def test_missing_sector_id_or_failed_endpoint_is_unavailable(self):
        self.configure_post_endpoint()
        r = pfz.get_pfz_advisory("Panaji", "Goa", "2026-09-21")               # GOA has no id configured
        self.assertFalse(r["available"])
        self.assertEqual(r["message"], "No current PFZ advisory available for this region/date.")
        def boom(url, timeout, data=None, headers=None):
            if "example.invalid" in url: raise OSError("HTTP 500")
            return LANDING_HTML
        pfz._http_get_text = boom
        r = pfz.get_pfz_advisory("Mumbai", "Maharashtra", "2026-09-21")
        self.assertFalse(r["available"]); self.assertNotIn("zones", r)

    def test_available_pfz_flows_through_api_ask_with_safety_priority(self):
        self.configure_post_endpoint()
        j = self.client.post("/api/ask", json={"query": "fishing tomorrow", "city": "Mumbai"}).get_json()
        self.assertTrue(j["pfz"]["available"])
        self.assertEqual(j["fishing"]["fishing_status"], "opportunity_indicated")
        SCENARIO["wave"] = 3.0
        pfz.clear_cache()
        j = self.client.post("/api/ask", json={"query": "fishing tomorrow", "city": "Mumbai"}).get_json()
        self.assertEqual(j["verdict"], "DO NOT VENTURE")
        self.assertTrue(j["pfz"]["available"])
        self.assertEqual(j["fishing"]["message"],
                         "Potential fishing activity may be indicated, but current marine conditions are unsafe. Do not venture.")

    def test_advisory_not_covering_requested_date_is_unavailable(self):
        os.environ[pfz.SECTOR_URL_ENV] = "https://example.invalid/pfz?sector={sector}"
        pfz._http_get_text = lambda url, timeout: "Latitude: 15 24 0 Longitude: 73 12 0" if "example.invalid" in url else LANDING_HTML
        r = pfz.get_pfz_advisory("Panaji", "Goa", "2026-09-25")
        self.assertFalse(r["available"])
        self.assertEqual(r["reason"], "Advisory does not cover the requested date")

    def test_no_duplicate_requests_between_ask_and_map(self):
        n = []
        pfz._http_get_text = lambda url, timeout: (n.append(url), LANDING_HTML)[1]
        pfz.get_pfz_advisory("Kochi", "Kerala", "2026-09-21")
        pfz.get_pfz_advisory("Kochi", "Kerala", "2026-09-21")
        self.assertEqual(len(n), 1)


class TestMapData(Base):
    def install_fake_open_meteo(self):
        calls = []

        class Resp:
            def __init__(self, payload): self.payload = payload
            def raise_for_status(self): pass
            def json(self): return self.payload

        def fake_get(url, params=None, timeout=None):
            lats = [float(x) for x in params["latitude"].split(",")]
            lons = [float(x) for x in params["longitude"].split(",")]
            calls.append({"url": url, "lats": lats, "lons": lons, "params": params})
            t = params["start_date"] + "T08:00"
            items = []
            for la, lo in zip(lats, lons):
                snapped_lat, snapped_lon = float(round(la)), float(round(lo))  # neighbours share a cell
                hourly = {"time": [t]}
                if "marine" in url:
                    hourly.update(wave_height=[1.1], wave_direction=[210.0],
                                  sea_surface_temperature=[None if int(snapped_lon) % 2 else 28.4])
                else:
                    hourly.update(wind_speed_10m=[12.0], wind_direction_10m=[300.0])
                items.append({"latitude": snapped_lat, "longitude": snapped_lon, "hourly": hourly})
            return Resp(items)

        self._orig_get = map_data.requests.get
        map_data.requests.get = fake_get
        self.addCleanup(lambda: setattr(map_data.requests, "get", self._orig_get))
        return calls

    def test_region_is_the_requested_cities_own_window_for_all_ten(self):
        calls = self.install_fake_open_meteo()
        for name in CITIES:
            with self.subTest(city=name):
                calls.clear(); map_data.clear_cache()
                c = BY_NAME[name]
                res = map_data.get_map_data(c["lat"], c["lon"], "2026-09-21", "08:00", name, c["state"])
                self.assertEqual(res["status"], "success", res)
                self.assertEqual(res["region_source"], "city")
                reg = map_data.REGIONS[name]
                self.assertEqual({k: res["region"][k] for k in reg}, reg)
                # city centre lies inside its own window
                self.assertTrue(reg["min_lat"] <= c["lat"] <= reg["max_lat"] and reg["min_lon"] <= c["lon"] <= reg["max_lon"])
                marine = calls[0]
                self.assertTrue(all(reg["min_lat"] - 1e-6 <= la <= reg["max_lat"] + 1e-6 for la in marine["lats"]))
                self.assertTrue(all(reg["min_lon"] - 1e-6 <= lo <= reg["max_lon"] + 1e-6 for lo in marine["lons"]))
                keys = {(p["latitude"], p["longitude"]) for p in res["points"]}
                self.assertEqual(len(keys), len(res["points"]))  # snapped duplicates removed
                self.assertEqual(res["pfz"]["available"], False)

    def test_previously_wrong_cities(self):
        self.install_fake_open_meteo()
        for name, wrong in [("Mangaluru", "Kochi"), ("Kanyakumari", "Kochi"), ("Panaji", "Mumbai"),
                            ("Veraval", "Mumbai"), ("Digha", "Puri")]:
            c = BY_NAME[name]
            r, src = map_data._select_region(name, c["lat"], c["lon"])
            self.assertEqual(r, map_data.REGIONS[name]); self.assertNotEqual(r, map_data.REGIONS[wrong])

    def test_unknown_city_falls_back_to_nearest_centre_not_first(self):
        r, src = map_data._select_region("Nowhere", 12.9, 74.9)  # inside Kochi, Mangaluru, ... rectangles
        self.assertEqual(src, "coordinates")
        self.assertEqual(r, map_data.REGIONS["Mangaluru"])
        r, src = map_data._select_region("Nowhere", 40.0, 10.0)
        self.assertEqual(src, "default_window")

    def test_null_sst_stays_null_and_cache_prevents_refetch(self):
        calls = self.install_fake_open_meteo()
        c = BY_NAME["Kochi"]
        a = map_data.get_map_data(c["lat"], c["lon"], "2026-09-21", "08:00", "Kochi", "Kerala")
        n = len(calls)
        b = map_data.get_map_data(c["lat"], c["lon"], "2026-09-21", "08:00", "Kochi", "Kerala")
        self.assertEqual(len(calls), n)
        self.assertEqual(a["points"], b["points"])
        self.assertTrue(any(p["sea_surface_temperature"] is None for p in a["points"]))
        self.assertTrue(all(p["wave_height"] is not None and p["wind_speed"] is not None for p in a["points"]))

    def test_grid_is_batched_and_bounds_are_reported(self):
        calls = self.install_fake_open_meteo()
        c = BY_NAME["Kochi"]
        res = map_data.get_map_data(c["lat"], c["lon"], "2026-09-21", "08:00", "Kochi", "Kerala")
        # every requested coordinate goes out, but in batches, not one URL and not one per point
        self.assertEqual(res["requested_point_count"], len(map_data._build_grid(
            map_data.REGIONS["Kochi"], map_data._grid_step_for(map_data.REGIONS["Kochi"]))))
        self.assertGreater(len(calls), 1)
        self.assertLessEqual(len(calls), 8)
        self.assertEqual(res["api_requests"], len(calls))
        self.assertTrue(all(len(c["lats"]) <= map_data.COORDS_PER_REQUEST for c in calls))
        sent = sum(len(c["lats"]) for c in calls if "marine" in c["url"])
        self.assertEqual(sent, res["requested_point_count"])      # nothing silently dropped
        b = res["data_bounds"]
        self.assertEqual(b["min_lat"], min(p["latitude"] for p in res["points"]))
        self.assertEqual(b["max_lon"], max(p["longitude"] for p in res["points"]))
        reg = map_data.REGIONS["Kochi"]
        self.assertTrue(reg["min_lat"] - 1 <= b["min_lat"] and b["max_lat"] <= reg["max_lat"] + 1)

    def test_every_region_is_mostly_sea_and_contains_its_city(self):
        # crude land boxes: the peninsula, Sri Lanka - a region must not be centred on them
        for name, reg in map_data.REGIONS.items():
            c = BY_NAME[name]
            self.assertTrue(reg["min_lat"] <= c["lat"] <= reg["max_lat"], name)
            self.assertTrue(reg["min_lon"] <= c["lon"] <= reg["max_lon"], name)
            self.assertGreater(reg["max_lat"] - reg["min_lat"], 4.0, name)   # a regional window
            self.assertLess(reg["max_lat"] - reg["min_lat"], 10.0, name)     # not the whole ocean
            self.assertGreater(reg["max_lon"] - reg["min_lon"], 4.0, name)
            self.assertLess(reg["max_lon"] - reg["min_lon"], 10.0, name)
            step = map_data._grid_step_for(reg)
            self.assertLessEqual(len(map_data._build_grid(reg, step)), map_data.MAX_GRID_POINTS)

    def test_api_map_data_contract(self):
        calls = self.install_fake_open_meteo()
        g = lambda q: self.client.get("/api/map-data?" + q)
        self.assertEqual(g("date=2026-09-21").status_code, 400)                     # no silent Mumbai
        self.assertEqual(g("city=Kochi").status_code, 400)                          # no date
        self.assertEqual(g("city=Kochi&date=21-09-2026").status_code, 400)
        self.assertEqual(g("city=Kochi&date=2026-09-21&time=8am").status_code, 400)
        self.assertEqual(g("city=Atlantis&date=2026-09-21").status_code, 404)
        self.assertEqual(calls, [])
        r = g("city=Mangaluru&date=2026-09-21&time=08:30")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual((j["city"], j["time"], j["region_source"]), ("Mangaluru", "08:00", "city"))
        self.assertEqual(j["center"], {"latitude": BY_NAME["Mangaluru"]["lat"], "longitude": BY_NAME["Mangaluru"]["lon"]})
        self.assertEqual(j["region"]["min_lat"], map_data.REGIONS["Mangaluru"]["min_lat"])
        # target_day alternative to date
        self.assertEqual(g("city=Kochi&target_day=tomorrow&time=08:00").get_json()["date"], tomorrow_ist())


if __name__ == "__main__":
    unittest.main()
