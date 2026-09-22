"""
OceanMind AI - Agent Orchestrator

The orchestrator coordinates specialized agents.

Architecture:

User
 ↓
Intent Agent
 ↓
Orchestrator
 ├── Weather Agent
 ├── Ocean Agent
 ├── Safety Agent
 └── Explanation Agent
 ↓
Structured Result
"""

from agents.weather_agent import run_weather_agent
from agents.ocean_agent import run_ocean_agent
from agents.safety_agent import run_safety_agent
from agents.explanation_agent import run_explanation_agent
from agents.pfz_agent import run_pfz_agent
from agents.fishing_agent import run_fishing_agent


def merge_hourly_data(weather_result, marine_result):
    """
    Merge weather and marine data using matching timestamps.

    This is intentionally kept simple for the first
    orchestrator version.
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

    weather_by_time = {
        item.get("time"): item
        for item in weather_hourly
        if isinstance(item, dict) and item.get("time")
    }

    marine_by_time = {
        item.get("time"): item
        for item in marine_hourly
        if isinstance(item, dict) and item.get("time")
    }

    common_times = sorted(
        set(weather_by_time)
        &
        set(marine_by_time)
    )

    merged = []

    for timestamp in common_times:

        weather_item = weather_by_time[timestamp]
        marine_item = marine_by_time[timestamp]

        merged.append(
            {
                "time": timestamp,

                "temperature": weather_item.get(
                    "temperature"
                ),

                "wind_speed": weather_item.get(
                    "wind_speed"
                ),

                "wind_direction": weather_item.get(
                    "wind_direction"
                ),

                "wind_gust": weather_item.get(
                    "wind_gust"
                ),

                "precipitation": weather_item.get(
                    "precipitation"
                ),

                "wave_height": marine_item.get(
                    "wave_height"
                ),

                "wave_direction": marine_item.get(
                    "wave_direction"
                ),

                "wind_wave_height": marine_item.get(
                    "wind_wave_height"
                ),

                "wind_wave_direction": marine_item.get(
                    "wind_wave_direction"
                ),

                "sea_surface_temperature": marine_item.get(
                    "sea_surface_temperature"
                ),
            }
        )

    return merged


def filter_time_window(hourly_data, time_window):
    """
    Filter hourly records according to the requested
    fishing time window.
    """

    time_windows = {
        "morning": (6, 10),
        "afternoon": (12, 16),
        "evening": (17, 21),
        "all_day": (0, 23),
    }

    if not isinstance(hourly_data, list):
        return []

    if time_window not in time_windows:
        return []

    start_hour, end_hour = time_windows[time_window]

    selected = []

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
            selected.append(item)

    return selected


def run_orchestrator(
    latitude,
    longitude,
    forecast_date,
    time_window,
    city_name,
    target_day,
    state=None,
):
    """
    Coordinate the OceanMind agents.

    Flow:

        Weather Agent
              +
         Ocean Agent
              ↓
        Merge Data
              ↓
       Filter Time Window
              ↓
        Safety Agent
              ├──────────────┐
              ↓              ↓
       Explanation Agent   PFZ Agent
                              ↓
                        Fishing Agent
                    (safety verdict + PFZ)

    Marine safety and fishing opportunity are kept as separate
    concepts: the Fishing Agent only ever *reads* the safety
    verdict already produced above, it never recomputes or
    overrides it.
    """

    # ========================================================
    # 1. WEATHER AGENT
    # ========================================================

    weather_result = run_weather_agent(
        latitude=latitude,
        longitude=longitude,
        forecast_date=forecast_date,
    )

    if weather_result.get("status") != "success":

        return {
            "status": "error",
            "stage": "weather_agent",
            "error": weather_result.get(
                "error",
                "Weather data unavailable."
            ),
        }

    # ========================================================
    # 2. OCEAN AGENT
    # ========================================================

    ocean_result = run_ocean_agent(
        latitude=latitude,
        longitude=longitude,
        forecast_date=forecast_date,
    )

    if ocean_result.get("status") != "success":

        return {
            "status": "error",
            "stage": "ocean_agent",
            "error": ocean_result.get(
                "error",
                "Marine data unavailable."
            ),
        }

    # ========================================================
    # 3. MERGE DATA
    # ========================================================

    hourly_data = merge_hourly_data(
        weather_result["data"],
        ocean_result["data"],
    )

    if not hourly_data:

        return {
            "status": "error",
            "stage": "data_merge",
            "error": "No matching weather and marine data.",
        }

    # ========================================================
    # 4. FILTER TIME WINDOW
    # ========================================================

    selected_hourly_data = filter_time_window(
        hourly_data,
        time_window,
    )

    if not selected_hourly_data:

        return {
            "status": "error",
            "stage": "time_filter",
            "error": (
                f"No forecast hours available for "
                f"'{time_window}'."
            ),
        }

    # ========================================================
    # 5. SAFETY AGENT
    # ========================================================

    safety_result = run_safety_agent(
        selected_hourly_data
    )

    if safety_result.get("status") != "success":

        return {
            "status": "error",
            "stage": "safety_agent",
            "error": safety_result.get(
                "error",
                "Safety analysis failed."
            ),
        }

    safety_data = safety_result["data"]

    verdict = safety_data.get(
        "verdict",
        "DATA UNAVAILABLE"
    )

    worst_period = safety_data.get(
        "worst_period"
    )

    # ========================================================
    # 6. FIND WORST PERIOD
    # ========================================================

    worst_data = None

    for item in selected_hourly_data:

        if item.get("time") == worst_period:
            worst_data = item
            break

    if worst_data:

        wave_height_m = worst_data.get(
            "wave_height"
        )

        wind_speed_kmh = worst_data.get(
            "wind_speed"
        )

        wind_gusts_kmh = worst_data.get(
            "wind_gust"
        )

    else:

        wave_height_m = None
        wind_speed_kmh = None
        wind_gusts_kmh = None

    # ========================================================
    # 7. REASONS
    # ========================================================

    reasons = []

    for item in safety_data.get(
        "hourly_results",
        []
    ):

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

    # Remove duplicates while preserving order.

    reasons = list(
        dict.fromkeys(reasons)
    )

    # ========================================================
    # 8. PFZ AGENT
    # ========================================================
    #
    # Independent of safety: this only retrieves the official
    # INCOIS advisory (or a clear "unavailable" result). It
    # never blocks the response - a failed/unavailable PFZ
    # lookup still lets marine safety and weather results
    # through.

    pfz_result = run_pfz_agent(
        city_name=city_name,
        state=state,
        forecast_date=forecast_date,
    )

    if pfz_result.get("status") == "success":
        pfz_data = pfz_result.get("data", {})
    else:
        # The agent itself crashed (not the same as "no advisory").
        # Report it as unavailable in the normalized PFZ shape.
        pfz_data = {
            "available": False,
            "source": "INCOIS PFZ Advisory",
            "reason": "No current advisory available",
            "message": (
                "No current PFZ advisory available for this "
                "region/date."
            ),
        }

    # ========================================================
    # 9. FISHING SUITABILITY AGENT
    # ========================================================
    #
    # Deterministic rules only - combines the safety verdict
    # already decided above with the PFZ result. Never
    # recomputes safety, never invents PFZ data, and produces no
    # numeric score.

    fishing_result = run_fishing_agent(
        safety_verdict=verdict,
        pfz_result=pfz_data,
    )

    if fishing_result.get("status") == "success":
        fishing_data = dict(fishing_result.get("data", {}))
    else:
        fishing_data = {
            "fishing_status": "data_unavailable",
            "label": "Fishing opportunity unavailable",
            "message": "Fishing suitability could not be evaluated.",
            "safety_verdict": verdict,
        }

    # Evidence only: the real sea-surface temperature observed in
    # the requested window, shown next to the opportunity result.
    # It is NOT an input to the fishing status - there is no
    # validated rule that turns SST into fishing probability.

    sst_values = [
        item.get("sea_surface_temperature")
        for item in selected_hourly_data
        if isinstance(item.get("sea_surface_temperature"), (int, float))
    ]

    if sst_values:
        fishing_data["environment"] = {
            "sea_surface_temperature_c": {
                "min": min(sst_values),
                "max": max(sst_values),
            },
            "note": (
                "Observed forecast conditions shown for context; "
                "not used to score fishing opportunity."
            ),
        }

    # ========================================================
    # 10. EXPLANATION AGENT
    # ========================================================

    explanation_result = run_explanation_agent(
        city_name=city_name,
        target_day=target_day,
        verdict=verdict,
        wave_height_m=wave_height_m,
        wind_speed_kmh=wind_speed_kmh,
        wind_gusts_kmh=wind_gusts_kmh,
        reasons=reasons,
    )

    if explanation_result.get("status") == "success":

        explanation = explanation_result.get(
            "explanation",
            ""
        )

    else:

        explanation = (
            "Safety assessment completed using "
            "the deterministic rule engine."
        )

    # ========================================================
    # 11. FINAL STRUCTURED RESULT
    # ========================================================

    return {
        "status": "success",

        "weather": weather_result,
        "ocean": ocean_result,

        "hourly_data": hourly_data,

        "selected_hourly_data": selected_hourly_data,

        "safety": safety_data,

        "pfz": pfz_data,

        "fishing": fishing_data,

        "explanation": explanation,

        "metrics": {
            "wave_height_m": wave_height_m,
            "wind_speed_kmh": wind_speed_kmh,
            "wind_gusts_kmh": wind_gusts_kmh,
        },

        "reasons": reasons,
    }