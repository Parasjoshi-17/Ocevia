"""
OceanMind AI - Flask Web Application and REST API

Architecture:

USER
  ↓
Flask API
  ↓
Intent / City / Date / Time Resolution
  ↓
Weather API + Marine API
  ↓
Hourly Data Merge
  ↓
Deterministic Safety Engine
  ↓
AI Explanation
  ↓
SQLite History
  ↓
JSON Response
  ↓
Frontend

IMPORTANT:
- The LLM does NOT decide safety.
- rules.py decides the safety verdict.
- Weather and marine values come from real APIs.
- No weather/ocean values are fabricated.
"""

import os
import re
from datetime import datetime, timedelta, timezone

from flask import Flask, render_template, request, jsonify

from database import (
    init_db,
    get_cities,
    get_city_by_name,
    save_history,
    get_history,
)

from weather import get_weather
from marine import get_marine
from rules import evaluate_time_window
from ai_explain import get_ai_explanation
from intent_parser import parse_query
from agents.orchestrator import run_orchestrator
from map_data import get_map_data

# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

# Initialize SQLite database when application starts.
init_db()


# ============================================================
# CONSTANTS
# ============================================================

VALID_DAYS = {
    "today",
    "tomorrow",
    "day_after",
    "day_after_tomorrow",
}

SOURCE_WEATHER = "Open-Meteo Forecast API"
SOURCE_MARINE = "Open-Meteo Marine API"


# India has a single time zone (IST, UTC+05:30, no DST). "Today" and
# "tomorrow" are defined in IST so the answer does not shift by a day
# when the server itself runs on UTC (e.g. most cloud hosts).
IST = timezone(timedelta(hours=5, minutes=30))


def today_ist():
    return datetime.now(IST).date()


# Fishing time windows.
TIME_WINDOWS = {
    "morning": (6, 10),
    "afternoon": (12, 16),
    "evening": (17, 21),
    "all_day": (0, 23),
}


# ============================================================
# HELPER: NORMALIZE DAY INPUT
# ============================================================

def normalize_target_day(target_day):
    """
    Normalize different possible frontend/user values.

    Examples:
        "Today"                -> "today"
        "TOMORROW"             -> "tomorrow"
        "day after"            -> "day_after"
        "day after tomorrow"   -> "day_after_tomorrow"
    """

    if not isinstance(target_day, str):
        return None

    target_day = target_day.strip().lower()

    replacements = {
        "day after tomorrow": "day_after_tomorrow",
        "day-after-tomorrow": "day_after_tomorrow",
        "day after": "day_after",
        "day-after": "day_after",
    }

    target_day = replacements.get(
        target_day,
        target_day
    )

    if target_day not in VALID_DAYS:
        return None

    return target_day


# ============================================================
# HELPER: GET FORECAST DATE
# ============================================================

def get_forecast_date(target_day):
    """
    Convert a user-friendly day into YYYY-MM-DD.

    today:
        today

    tomorrow:
        today + 1 day

    day_after / day_after_tomorrow:
        today + 2 days
    """

    target_day = normalize_target_day(target_day)

    if target_day is None:
        return None

    today = today_ist()

    if target_day == "today":
        return today.isoformat()

    if target_day == "tomorrow":
        return (
            today + timedelta(days=1)
        ).isoformat()

    if target_day in {
        "day_after",
        "day_after_tomorrow",
    }:
        return (
            today + timedelta(days=2)
        ).isoformat()

    return None


# ============================================================
# HELPER: SAFE FLOAT CONVERSION
# ============================================================

def safe_float(value):
    """
    Convert a value to float safely.

    Returns None if conversion is impossible.
    """

    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


# ============================================================
# HELPER: MERGE WEATHER + MARINE DATA
# ============================================================

def merge_hourly_data(weather_result, marine_result):
    """
    Merge weather and marine hourly forecasts by timestamp.

    Weather provides:
        temperature
        wind speed
        wind direction
        wind gust
        precipitation

    Marine provides:
        wave height
        wave direction
        wind-wave height
        wind-wave direction
        sea-surface temperature
    """

    if not isinstance(weather_result, dict):
        return []

    if not isinstance(marine_result, dict):
        return []

    weather = weather_result.get("weather")
    marine = marine_result.get("marine")

    if not isinstance(weather, dict):
        return []

    if not isinstance(marine, dict):
        return []

    weather_hourly = weather.get("hourly", [])
    marine_hourly = marine.get("hourly", [])

    if not isinstance(weather_hourly, list):
        return []

    if not isinstance(marine_hourly, list):
        return []

    # --------------------------------------------------------
    # Index weather data by timestamp
    # --------------------------------------------------------

    weather_by_time = {}

    for item in weather_hourly:

        if not isinstance(item, dict):
            continue

        timestamp = item.get("time")

        if timestamp:
            weather_by_time[timestamp] = item

    # --------------------------------------------------------
    # Index marine data by timestamp
    # --------------------------------------------------------

    marine_by_time = {}

    for item in marine_hourly:

        if not isinstance(item, dict):
            continue

        timestamp = item.get("time")

        if timestamp:
            marine_by_time[timestamp] = item

    # --------------------------------------------------------
    # Find common timestamps
    # --------------------------------------------------------

    common_times = sorted(
        set(weather_by_time.keys())
        &
        set(marine_by_time.keys())
    )

    merged = []

    # --------------------------------------------------------
    # Merge records
    # --------------------------------------------------------

    for timestamp in common_times:

        weather_item = weather_by_time[timestamp]
        marine_item = marine_by_time[timestamp]

        merged.append(
            {
                "time": timestamp,

                # -------------------------
                # Weather
                # -------------------------

                "temperature": safe_float(
                    weather_item.get("temperature")
                ),

                "wind_speed": safe_float(
                    weather_item.get("wind_speed")
                ),

                "wind_direction": safe_float(
                    weather_item.get("wind_direction")
                ),

                "wind_gust": safe_float(
                    weather_item.get("wind_gust")
                ),

                "precipitation": safe_float(
                    weather_item.get("precipitation")
                ),

                # -------------------------
                # Marine
                # -------------------------

                "wave_height": safe_float(
                    marine_item.get("wave_height")
                ),

                "wave_direction": safe_float(
                    marine_item.get("wave_direction")
                ),

                "wind_wave_height": safe_float(
                    marine_item.get("wind_wave_height")
                ),

                "wind_wave_direction": safe_float(
                    marine_item.get("wind_wave_direction")
                ),

                "sea_surface_temperature": safe_float(
                    marine_item.get(
                        "sea_surface_temperature"
                    )
                ),
            }
        )

    return merged


# ============================================================
# HELPER: FILTER TIME WINDOW
# ============================================================

def filter_time_window(hourly_data, time_window):
    """
    Filter hourly forecast data according to the
    requested fishing time window.
    """

    if not isinstance(hourly_data, list):
        return []

    if time_window not in TIME_WINDOWS:
        return []

    start_hour, end_hour = TIME_WINDOWS[time_window]

    filtered = []

    for item in hourly_data:

        if not isinstance(item, dict):
            continue

        timestamp = item.get("time")

        if not timestamp:
            continue

        try:
            hour = int(timestamp[11:13])

        except (ValueError, TypeError):
            continue

        if start_hour <= hour <= end_hour:
            filtered.append(item)

    return filtered


# ============================================================
# HELPER: FIND WORST PERIOD DATA
# ============================================================

def get_worst_period_data(hourly_data, worst_period):
    """
    Find the complete hourly record corresponding to
    the worst safety period.
    """

    if not worst_period:
        return None

    if not isinstance(hourly_data, list):
        return None

    for item in hourly_data:

        if not isinstance(item, dict):
            continue

        if item.get("time") == worst_period:
            return item

    return None


# ============================================================
# HELPER: GET SAFETY REASONS
# ============================================================

def get_safety_reasons(safety_result):
    """
    Extract reasons from the worst hourly safety result.
    """

    if not isinstance(safety_result, dict):
        return []

    hourly_results = safety_result.get(
        "hourly_results",
        []
    )

    worst_period = safety_result.get(
        "worst_period"
    )

    # --------------------------------------------------------
    # First try exact worst period
    # --------------------------------------------------------

    for item in hourly_results:

        if not isinstance(item, dict):
            continue

        if item.get("time") == worst_period:

            result = item.get(
                "result",
                {}
            )

            reasons = result.get(
                "reasons",
                []
            )

            if isinstance(reasons, list):
                return reasons

    # --------------------------------------------------------
    # Fallback: collect reasons from all hours
    # --------------------------------------------------------

    reasons = []

    for item in hourly_results:

        if not isinstance(item, dict):
            continue

        result = item.get(
            "result",
            {}
        )

        current_reasons = result.get(
            "reasons",
            []
        )

        if isinstance(current_reasons, list):
            reasons.extend(current_reasons)

    return reasons


# ============================================================
# HELPER: ERROR RESPONSE
# ============================================================

def api_error(message, status_code=400, details=None):
    """
    Return a consistent API error response.
    """

    response = {
        "status": "error",
        "message": message,
    }

    if details:
        response["details"] = details

    return jsonify(response), status_code


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/", methods=["GET"])
def index():
    """
    Render the main OceanMind AI interface.

    Analysis itself is performed through /api/ask.
    """

    cities = get_cities()

    city_name = (
        request.args
        .get("city", "Mumbai")
        .strip()
    )

    target_day = normalize_target_day(
        request.args.get(
            "day",
            "tomorrow"
        )
    )

    if target_day is None:
        target_day = "tomorrow"

    return render_template(
        "index.html",
        cities=cities,
        initial_verdict=None,
        selected_city=city_name,
        selected_day=target_day,
    )


# ============================================================
# API: CITIES
# ============================================================

@app.route("/api/cities", methods=["GET"])
def api_cities():
    """
    Return all coastal cities stored in SQLite.
    """

    try:

        cities = get_cities()

        return jsonify(
            {
                "status": "success",
                "cities": cities,
            }
        )

    except Exception as exc:

        app.logger.exception(
            "Failed to retrieve cities"
        )

        return api_error(
            "Unable to retrieve coastal cities.",
            500,
            str(exc),
        )


# ============================================================
# API: MAIN ANALYSIS
# ============================================================

@app.route("/api/ask", methods=["POST"])
def api_ask():
    """
    Main OceanMind AI analysis endpoint.

    Supports TWO input formats.

    --------------------------------------------------------
    Natural language:
    --------------------------------------------------------

    {
        "query": "Can I go fishing tomorrow morning near Mumbai?"
    }

    --------------------------------------------------------
    Structured:
    --------------------------------------------------------

    {
        "city": "Mumbai",
        "target_day": "tomorrow",
        "time_window": "morning"
    }

    Natural language is parsed by intent_parser.py.

    The parser ONLY extracts:
        intent
        city
        target_day
        time_window

    It does NOT decide safety.

    Safety is always calculated by rules.py.
    """

    # ========================================================
    # 1. READ REQUEST
    # ========================================================

    data = request.get_json(
        silent=True
    )

    if data is None:

        return api_error(
            "Request body must contain valid JSON.",
            400,
        )

    if not isinstance(data, dict):

        return api_error(
            "Request body must be a JSON object.",
            400,
        )

    # ========================================================
    # 2. RESOLVE USER INPUT
    # ========================================================
    #
    # ROOT CAUSE OF "City name must be a string." (history):
    #
    #   Home.jsx collects city + date from dropdowns and navigates
    #   to /dashboard with them in router state, but Dashboard.jsx
    #   only ever POSTed {"query": ...}. The backend therefore had
    #   to guess the city from the sentence. Quick questions such as
    #   "Is it safe to go fishing tomorrow?" contain no city, so
    #   intent_parser returned city=None, and None failed the
    #   isinstance(city_name, str) check below. Only queries that
    #   literally contained "Mumbai" (Dashboard's hard-coded default
    #   text) worked. It was a lost field, not a type problem.
    #
    # Resolution rules (same for every field):
    #
    #   1. A value the user actually typed inside the query text
    #      ("near Kochi", "tomorrow morning") wins - it is the most
    #      recent and most specific statement of intent.
    #   2. Otherwise the explicit field sent by the frontend is used
    #      ("city", "target_day"/"day", "time_window") - this is the
    #      city/day the user selected on the Home page.
    #   3. Otherwise defaults: tomorrow / all_day. A missing CITY
    #      never defaults - it is a 400, never a silent Mumbai.

    query = data.get("query")

    if query is not None and not isinstance(query, str):

        return api_error(
            "query must be a string.",
            400,
        )

    raw_city = data.get("city")

    if raw_city is not None and not isinstance(raw_city, str):

        return api_error(
            "City name must be a string.",
            400,
        )

    request_city = (raw_city or "").strip()

    request_day = data.get(
        "target_day",
        data.get("day")
    )

    request_window = data.get("time_window")

    resolved_from = {}

    if query and query.strip():

        # ----------------------------------------------------
        # NATURAL LANGUAGE (+ optional explicit context)
        # ----------------------------------------------------

        parsed = parse_query(query)

        if not isinstance(parsed, dict):

            return api_error(
                "Intent parser returned an invalid response.",
                500,
            )

        if parsed.get("status") != "success":

            return api_error(
                parsed.get(
                    "message",
                    parsed.get(
                        "error",
                        "Could not understand the query."
                    )
                ),
                400,
            )

        input_mode = "natural_language"

        intent = parsed.get("intent")

        # city
        if parsed.get("city"):
            city_name = parsed["city"]
            resolved_from["city"] = "query"
        else:
            city_name = request_city
            resolved_from["city"] = (
                "request" if request_city else "missing"
            )

        # day
        if parsed.get("target_day_explicit"):
            target_day = parsed["target_day"]
            resolved_from["target_day"] = "query"
        elif request_day not in (None, ""):
            target_day = request_day
            resolved_from["target_day"] = "request"
        else:
            target_day = parsed["target_day"]
            resolved_from["target_day"] = "default"

        # time window
        if parsed.get("time_window_explicit"):
            time_window = parsed["time_window"]
            resolved_from["time_window"] = "query"
        elif request_window not in (None, ""):
            time_window = request_window
            resolved_from["time_window"] = "request"
        else:
            time_window = parsed["time_window"]
            resolved_from["time_window"] = "default"

    else:

        # ----------------------------------------------------
        # STRUCTURED JSON MODE (no query text)
        # ----------------------------------------------------

        query = None
        input_mode = "structured"

        intent = data.get("intent", "fishing_safety")

        city_name = request_city
        resolved_from["city"] = (
            "request" if request_city else "missing"
        )

        target_day = (
            request_day
            if request_day not in (None, "")
            else "tomorrow"
        )
        resolved_from["target_day"] = (
            "request" if request_day not in (None, "") else "default"
        )

        time_window = (
            request_window
            if request_window not in (None, "")
            else "all_day"
        )
        resolved_from["time_window"] = (
            "request" if request_window not in (None, "") else "default"
        )

    # ========================================================
    # 3. VALIDATE CITY
    # ========================================================

    if not isinstance(city_name, str):

        return api_error(
            "City name must be a string.",
            400,
        )

    city_name = city_name.strip()

    if not city_name:

        return api_error(
            (
                "No city was specified. Select a coastal city or "
                "mention a supported one in your question."
            ),
            400,
        )

    city_info = get_city_by_name(
        city_name
    )

    if not city_info:

        return api_error(
            (
                f"City '{city_name}' "
                "was not found in the coastal "
                "city database."
            ),
            404,
        )

    # ========================================================
    # 4. VALIDATE TARGET DAY
    # ========================================================

    target_day = normalize_target_day(
        target_day
    )

    if target_day is None:

        return api_error(
            (
                "Invalid target_day. Use "
                "'today', 'tomorrow', "
                "or 'day_after_tomorrow'."
            ),
            400,
        )

    forecast_date = get_forecast_date(
        target_day
    )

    if forecast_date is None:

        return api_error(
            "Unable to determine forecast date.",
            400,
        )

    # ========================================================
    # 5. VALIDATE TIME WINDOW
    # ========================================================

    if not isinstance(time_window, str):

        return api_error(
            "time_window must be a string.",
            400,
        )

    time_window = time_window.strip().lower()

    if time_window not in TIME_WINDOWS:

        return api_error(
            (
                "Invalid time_window. Use "
                "'morning', 'afternoon', "
                "'evening', or 'all_day'."
            ),
            400,
        )

    # ========================================================
    # 6. GET COORDINATES
    # ========================================================

    latitude = safe_float(
        city_info.get("latitude")
    )

    longitude = safe_float(
        city_info.get("longitude")
    )

    if latitude is None or longitude is None:

        return api_error(
            "City coordinates are invalid.",
            500,
        )

    # ========================================================
    # 7. RUN AGENT ORCHESTRATOR
    # ========================================================

    try:

        orchestrator_result = run_orchestrator(
            latitude=latitude,
            longitude=longitude,
            forecast_date=forecast_date,
            time_window=time_window,
            city_name=city_info["name"],
            target_day=target_day,
            state=city_info.get("state"),
        )

    except Exception as exc:

        app.logger.exception(
            "Agent orchestrator failure"
        )

        return api_error(
            "Agent orchestration failed.",
            500,
            str(exc),
        )

    if not isinstance(
        orchestrator_result,
        dict
    ):

        return api_error(
            "Agent orchestrator returned an invalid response.",
            500,
        )

    if orchestrator_result.get("status") != "success":

        return api_error(
            orchestrator_result.get(
                "error",
                "Agent orchestration failed."
            ),
            502,
        )

    # ========================================================
    # 8. EXTRACT AGENT RESULTS
    # ========================================================

    hourly_data = orchestrator_result.get(
        "hourly_data",
        []
    )

    selected_hourly_data = orchestrator_result.get(
        "selected_hourly_data",
        []
    )

    safety_result = orchestrator_result.get(
        "safety",
        {}
    )

    verdict = safety_result.get(
        "verdict",
        "DATA UNAVAILABLE"
    )

    badge_color = safety_result.get(
        "badge_color",
        "gray"
    )

    advisory = safety_result.get(
        "advisory",
        ""
    )

    worst_period = safety_result.get(
        "worst_period"
    )

    # ========================================================
    # 9. EXTRACT METRICS
    # ========================================================

    orchestrator_metrics = orchestrator_result.get(
        "metrics",
        {}
    )

    wave_height_m = orchestrator_metrics.get(
        "wave_height_m"
    )

    wind_speed_kmh = orchestrator_metrics.get(
        "wind_speed_kmh"
    )

    wind_gusts_kmh = orchestrator_metrics.get(
        "wind_gusts_kmh"
    )

    # ========================================================
    # 10. EXTRACT SAFETY REASONS
    # ========================================================

    reasons = orchestrator_result.get(
        "reasons",
        []
    )

    # ========================================================
    # 11. EXTRACT AI EXPLANATION
    # ========================================================

    explanation = orchestrator_result.get(
        "explanation",
        ""
    )

    # ========================================================
    # 11b. EXTRACT PFZ + FISHING SUITABILITY
    # ========================================================

    pfz_data = orchestrator_result.get(
        "pfz",
        {
            "available": False,
            "source": "INCOIS PFZ Advisory",
            "reason": "No current advisory available",
            "message": "No current PFZ advisory available for this region/date.",
        }
    )

    fishing_data = orchestrator_result.get(
        "fishing",
        {
            "fishing_status": "data_unavailable",
            "message": "Fishing suitability could not be evaluated.",
            "safety_verdict": verdict,
        }
    )

    # ========================================================
    # 12. VALIDATE ORCHESTRATOR OUTPUT
    # ========================================================

    if not selected_hourly_data:

        return api_error(
            (
                f"No forecast hours were available "
                f"for the '{time_window}' time window."
            ),
            502,
        )

    if not explanation:

        explanation = (
            "Safety assessment completed using "
            "the deterministic rule engine."
        )

    # ========================================================
    # 15. SAVE HISTORY
    # ========================================================

    history_record = {
        "city_name": city_info["name"],
        "target_day": target_day,
        "forecast_date": forecast_date,

        "wave_height_m": wave_height_m,
        "wind_speed_kmh": wind_speed_kmh,
        "wind_gusts_kmh": wind_gusts_kmh,

        "verdict": verdict,
        "badge_color": badge_color,
        "explanation": explanation,
    }

    try:

        saved_id = save_history(
            history_record
        )

    except Exception as exc:

        # History failure should not destroy
        # an otherwise valid analysis.
        app.logger.exception(
            "Failed to save history"
        )

        saved_id = None

    # ========================================================
    # 16. RETURN RESULT
    # ========================================================

    return jsonify(
        {
            "status": "success",

            "query_id": saved_id,

            # -------------------------
            # INPUT
            # -------------------------

            "input_mode": input_mode,
            "query": query,
            "intent": intent,

            # Where each of city / target_day / time_window came from:
            # "query" (typed in the question), "request" (explicit
            # field from the frontend), or "default".
            "resolved_from": resolved_from,

            # -------------------------
            # LOCATION
            # -------------------------

            "city": city_info["name"],
            "state": city_info["state"],

            "coordinates": {
                "latitude": latitude,
                "longitude": longitude,
            },

            # -------------------------
            # DATE / TIME
            # -------------------------

            "target_day": target_day,
            "forecast_date": forecast_date,
            "time_window": time_window,

            # -------------------------
            # SAFETY
            # -------------------------

            "verdict": verdict,

            "badge_color": badge_color,

            "badge_text_en": safety_result.get(
                "badge_text_en"
            ),

            "badge_text_hi": safety_result.get(
                "badge_text_hi"
            ),

            "advisory": advisory,

            "worst_period": worst_period,

            "hours_evaluated": safety_result.get(
                "hours_evaluated",
                len(selected_hourly_data)
            ),

            "reasons": reasons,

            # -------------------------
            # WORST PERIOD METRICS
            # -------------------------

            "metrics": {
                "wave_height_m": wave_height_m,
                "wind_speed_kmh": wind_speed_kmh,
                "wind_gusts_kmh": wind_gusts_kmh,
            },

            # -------------------------
            # AI
            # -------------------------

            "explanation": explanation,

            # -------------------------
            # FISHING ZONES (PFZ) + SUITABILITY
            #
            # Kept separate from "verdict" above:
            #   verdict = marine SAFETY (rules.py)
            #   fishing = fishing OPPORTUNITY (fishing_suitability.py)
            # -------------------------

            "pfz": pfz_data,

            "fishing": fishing_data,

            # -------------------------
            # COMPLETE HOURLY DATA
            # -------------------------

            # Keep complete data for:
            # - charts
            # - Leaflet map
            # - timeline
            # - wave direction arrows
            # - wind direction arrows

            "hourly_data": hourly_data,

            # Only the hours inside the requested time window.
            "selected_hourly_data": selected_hourly_data,

            # -------------------------
            # SOURCES
            # -------------------------

            "sources": {
                "weather": SOURCE_WEATHER,
                "marine": SOURCE_MARINE,
            },
        }
    )

# ============================================================
# API: MARINE MAP DATA
# ============================================================

@app.route("/api/map-data", methods=["GET"])
def api_map_data():
    """
    Return spatial forecast data for the marine map.

    Contract (matches /api/ask - use the values it returned):

        /api/map-data?city=Kochi&date=2026-09-21&time=08:00

        city  - REQUIRED. There is no default city: a missing city
                is a 400, never a silent Mumbai.
        date  - YYYY-MM-DD (as returned in /api/ask "forecast_date"),
                or use target_day=today|tomorrow|day_after_tomorrow.
        time  - HH:MM (as derived from /api/ask "worst_period").
                Open-Meteo is hourly, so minutes are dropped.
                Defaults to 12:00 when omitted.
    """

    city_name = (request.args.get("city") or "").strip()

    if not city_name:

        return api_error(
            "city is required for /api/map-data.",
            400,
        )

    # --------------------------------------------------------
    # 1. GET CITY
    # --------------------------------------------------------

    city_info = get_city_by_name(city_name)

    if not city_info:
        return api_error(
            f"City '{city_name}' was not found in the coastal city database.",
            404,
        )

    # --------------------------------------------------------
    # 2. FORECAST DATE
    # --------------------------------------------------------

    forecast_date = (request.args.get("date") or "").strip()

    if not forecast_date:

        forecast_date = get_forecast_date(
            request.args.get("target_day")
        )

        if forecast_date is None:

            return api_error(
                "date (YYYY-MM-DD) or target_day is required.",
                400,
            )

    try:
        datetime.strptime(forecast_date, "%Y-%m-%d")

    except ValueError:

        return api_error(
            "date must be in YYYY-MM-DD format.",
            400,
        )

    # --------------------------------------------------------
    # 3. FORECAST HOUR
    # --------------------------------------------------------

    forecast_time = (request.args.get("time") or "12:00").strip()

    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", forecast_time):

        return api_error(
            "time must be in HH:MM (24-hour) format.",
            400,
        )

    # Open-Meteo hourly timestamps are on the hour.
    forecast_time = f"{forecast_time[:2]}:00"

    # --------------------------------------------------------
    # 4. COORDINATES
    # --------------------------------------------------------

    latitude = safe_float(
        city_info.get("latitude")
    )

    longitude = safe_float(
        city_info.get("longitude")
    )

    if latitude is None or longitude is None:
        return api_error(
            "City coordinates are invalid.",
            500,
        )

    # --------------------------------------------------------
    # 5. FETCH SPATIAL DATA
    # --------------------------------------------------------

    try:

        result = get_map_data(
            center_latitude=latitude,
            center_longitude=longitude,
            forecast_date=forecast_date,
            forecast_time=forecast_time,
            city_name=city_info["name"],
            state=city_info.get("state"),
        )

    except Exception as exc:

        app.logger.exception(
            "Marine map data failure"
        )

        return api_error(
            "Unable to retrieve marine map data.",
            502,
            str(exc),
        )

    # --------------------------------------------------------
    # 6. CHECK RESULT
    # --------------------------------------------------------

    if not isinstance(result, dict):
        return api_error(
            "Marine map returned an invalid response.",
            502,
        )

    if result.get("status") != "success":

        # map_data.py reports failures under "message".
        return api_error(
            result.get(
                "message",
                result.get(
                    "error",
                    "Marine map data unavailable.",
                ),
            ),
            502,
        )

    # --------------------------------------------------------
    # 7. ADD CITY INFORMATION
    # --------------------------------------------------------

    result["city"] = city_info["name"]
    result["state"] = city_info["state"]

    result["center"] = {
        "latitude": latitude,
        "longitude": longitude,
    }

    return jsonify(result)


# ============================================================
# API: HISTORY
# ============================================================

@app.route("/api/history", methods=["GET"])
def api_history():
    """
    Return the latest 20 analysis records.
    """

    try:

        history = get_history(
            limit=20
        )

        return jsonify(
            {
                "status": "success",
                "history": history,
            }
        )

    except Exception as exc:

        app.logger.exception(
            "Failed to retrieve history"
        )

        return api_error(
            "Unable to retrieve query history.",
            500,
            str(exc),
        )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/api/health", methods=["GET"])
def api_health():
    """
    Basic health endpoint.
    """

    return jsonify(
        {
            "status": "success",
            "service": "OceanMind AI",
            "message": "Backend is running.",
        }
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def handle_404(error):

    return jsonify(
        {
            "status": "error",
            "message": "Endpoint not found.",
        }
    ), 404


@app.errorhandler(405)
def handle_405(error):

    return jsonify(
        {
            "status": "error",
            "message": "HTTP method not allowed.",
        }
    ), 405


@app.errorhandler(500)
def handle_500(error):

    app.logger.exception(
        "Unhandled server error"
    )

    return jsonify(
        {
            "status": "error",
            "message": "Internal server error.",
        }
    ), 500


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    print(
        f"Starting OceanMind AI on "
        f"http://127.0.0.1:{port}"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
    )