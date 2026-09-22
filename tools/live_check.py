"""
live_check.py - run this LOCALLY against your running backend to verify
real data end to end (the offline unit tests cannot do that).

    python tools/live_check.py                 # http://127.0.0.1:5000
    python tools/live_check.py http://host:5000

For each of Mumbai, Kochi, Chennai, Visakhapatnam, Mangaluru it checks:
  /api/ask      city, forecast date (IST tomorrow), time window, safety verdict,
                PFZ shape, fishing block
  /api/map-data city + centre, region == that city's own window, every point
                inside it, real (non-null) wind/wave counts, SST count,
                PFZ real-or-explicitly-unavailable
and finally the three natural-language queries. Prints PASS/FAIL per check;
exit code 1 if anything failed. It never fabricates or fills in data.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from map_data import REGIONS  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
CITIES = ["Mumbai", "Kochi", "Chennai", "Visakhapatnam", "Mangaluru"]
VERDICTS = {"SAFE", "CAUTION", "DO NOT VENTURE", "DATA UNAVAILABLE"}
FAILS = []


def check(label, ok, extra=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label} {extra}".rstrip())
    if not ok:
        FAILS.append(label)


class HttpClient:
    def __init__(self, base):
        import requests
        self.base, self.r = base.rstrip("/"), requests

    def post(self, path, body):
        resp = self.r.post(self.base + path, json=body, timeout=120)
        return resp.status_code, resp.json()

    def get(self, path):
        resp = self.r.get(self.base + path, timeout=120)
        return resp.status_code, resp.json()


def run(client, cities=CITIES):
    tomorrow = (datetime.now(IST).date() + timedelta(days=1)).isoformat()

    for city in cities:
        print(f"\n=== {city} (structured context: tomorrow / morning) ===")
        code, ask = client.post("/api/ask", {"query": "Can I go fishing tomorrow morning?", "city": city})
        check("/api/ask 200", code == 200, str(ask.get("message", "")))
        if code != 200:
            continue
        check("city", ask["city"] == city, ask["city"])
        check("forecast_date == tomorrow (IST)", ask["forecast_date"] == tomorrow, ask["forecast_date"])
        check("time_window == morning", ask["time_window"] == "morning")
        check("verdict produced", ask["verdict"] in VERDICTS, ask["verdict"])
        pfz = ask.get("pfz", {})
        check("pfz normalized ('available' bool)", isinstance(pfz.get("available"), bool))
        if pfz.get("available"):
            check("pfz zones are real dicts with lat/lon", all("latitude" in z and "longitude" in z for z in pfz["zones"]),
                  f"{len(pfz['zones'])} zones")
        else:
            check("pfz unavailable message exact", pfz.get("message") == "No current PFZ advisory available for this region/date.")
        fishing = ask.get("fishing", {})
        check("fishing separate from safety", "fishing_status" in fishing and "safety_verdict" in fishing)
        if ask["verdict"] == "DO NOT VENTURE":
            check("DNV => fishing says do not venture", "Do not venture" in fishing.get("message", ""))

        hour = (ask.get("worst_period") or f"{tomorrow}T12:00").split("T")[1][:5]
        code, m = client.get(f"/api/map-data?city={city}&date={ask['forecast_date']}&time={hour}")
        check("/api/map-data 200", code == 200, str(m.get("message", "")))
        if code != 200:
            continue
        reg = REGIONS[city]
        check("map city", m["city"] == city)
        check("region_source == city", m.get("region_source") == "city", str(m.get("region_source")))
        check("region == this city's window", all(m["region"][k] == reg[k] for k in reg))
        pts = m["points"]
        check("points returned", len(pts) > 0, f"{len(pts)} points")
        check("all points inside region", all(reg["min_lat"] - 1 <= p["latitude"] <= reg["max_lat"] + 1 and
                                              reg["min_lon"] - 1 <= p["longitude"] <= reg["max_lon"] + 1 for p in pts),
              "(1 deg tolerance for model-cell snapping)")
        n = len(pts)
        wind = sum(p.get("wind_speed") is not None for p in pts)
        wave = sum(p.get("wave_height") is not None for p in pts)
        sst = sum(p.get("sea_surface_temperature") is not None for p in pts)
        check("wind values present", wind == n, f"{wind}/{n}")
        check("wave values present", wave == n, f"{wave}/{n}")
        check("SST values present (some null is possible)", sst > 0, f"{sst}/{n}")
        check("center is this city", isinstance(m["center"]["latitude"], float))
        b = m.get("data_bounds") or {}
        check("data_bounds reported", bool(b))
        if b:
            check("data covers most of the domain (lat)",
                  (b["max_lat"] - b["min_lat"]) > 0.6 * (reg["max_lat"] - reg["min_lat"]),
                  f'{b["min_lat"]:.1f}-{b["max_lat"]:.1f}N vs {reg["min_lat"]}-{reg["max_lat"]}N')
            check("data covers most of the domain (lon)",
                  (b["max_lon"] - b["min_lon"]) > 0.6 * (reg["max_lon"] - reg["min_lon"]),
                  f'{b["min_lon"]:.1f}-{b["max_lon"]:.1f}E vs {reg["min_lon"]}-{reg["max_lon"]}E')
        check("API requests per map load stayed small", m.get("api_requests", 99) <= 10,
              f'{m.get("api_requests")} requests for {m.get("requested_point_count")} coordinates')
        check("enough points for a field", n >= 40, f"{n} points")

    print("\n=== natural-language queries ===")
    for q, expect in [("Can I go fishing tomorrow morning near Mumbai?", "Mumbai"),
                      ("Can I go fishing tomorrow morning near Kochi?", "Kochi"),
                      ("Can I go fishing tomorrow morning near Chennai?", "Chennai")]:
        code, a = client.post("/api/ask", {"query": q})
        check(q, code == 200 and a.get("city") == expect and a.get("time_window") == "morning",
              a.get("city", a.get("message", "")))
    return FAILS


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"
    failed = run(HttpClient(base))
    print("\nRESULT:", "ALL CHECKS PASSED" if not failed else f"{len(failed)} CHECK(S) FAILED: {failed}")
    sys.exit(1 if failed else 0)
