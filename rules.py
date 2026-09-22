"""
rules.py

Deterministic marine-condition assessment engine for OceanMind AI.

IMPORTANT:
- This engine does NOT use an LLM to make safety decisions.
- It evaluates numerical forecast data against configurable thresholds.
- The default profile is intended as a conservative prototype profile
  for small/artisanal fishing boats.
- These thresholds are NOT an official government navigation standard.
- Official IMD/INCOIS warnings should override this local assessment
  when integrated into the system.
"""

from typing import Dict, List, Any, Optional


# ============================================================
# DEFAULT SMALL FISHING BOAT PROFILE
# ============================================================
#
# These are prototype operating thresholds, not official
# government safety limits.
#
# They should eventually be calibrated against:
# - INCOIS SVAS
# - IMD fisherman warnings
# - vessel size/type
# - local coastal conditions
#

DEFAULT_PROFILE = {
    "wave": {
        "caution": 1.5,
        "danger": 2.5
    },

    "wind": {
        "caution": 25.0,
        "danger": 45.0
    },

    "gust": {
        "caution": 40.0,
        "danger": 60.0
    }
}


# ============================================================
# SINGLE-HOUR ASSESSMENT
# ============================================================

def evaluate_safety(
    wave_height_m: Optional[float],
    wind_speed_kmh: Optional[float],
    wind_gusts_kmh: Optional[float],
    profile: Dict[str, Any] = DEFAULT_PROFILE,
    official_warning: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate marine conditions for one forecast hour.

    Verdict:
        SAFE
        CAUTION
        DO NOT VENTURE
        DATA UNAVAILABLE

    The engine is deterministic.
    The LLM must never modify the verdict.
    """

    # --------------------------------------------------------
    # 1. Check whether required data exists
    # --------------------------------------------------------

    missing_data = []

    if wave_height_m is None:
        missing_data.append("wave height")

    if wind_speed_kmh is None:
        missing_data.append("wind speed")

    if wind_gusts_kmh is None:
        missing_data.append("wind gust")

    if missing_data:

        return {
            "verdict": "DATA UNAVAILABLE",

            "badge_color": "gray",

            "badge_text_en": "DATA UNAVAILABLE",

            "badge_text_hi": "डेटा उपलब्ध नहीं है",

            "advisory": (
                "Required marine forecast data is unavailable. "
                "Do not make a safety decision from incomplete data."
            ),

            "reasons": [
                f"Missing: {', '.join(missing_data)}"
            ],

            "metrics": {
                "wave_height_m": wave_height_m,
                "wind_speed_kmh": wind_speed_kmh,
                "wind_gusts_kmh": wind_gusts_kmh
            },

            "thresholds_exceeded": [],

            "official_warning": official_warning
        }


    # --------------------------------------------------------
    # 2. Read thresholds
    # --------------------------------------------------------

    wave_caution = profile["wave"]["caution"]
    wave_danger = profile["wave"]["danger"]

    wind_caution = profile["wind"]["caution"]
    wind_danger = profile["wind"]["danger"]

    gust_caution = profile["gust"]["caution"]
    gust_danger = profile["gust"]["danger"]


    danger_triggers = []
    caution_triggers = []


    # --------------------------------------------------------
    # 3. DANGER CONDITIONS
    # --------------------------------------------------------

    if wave_height_m >= wave_danger:

        danger_triggers.append(
            f"Wave height is {wave_height_m:.2f} m "
            f"(danger threshold: {wave_danger:.2f} m)"
        )

    if wind_speed_kmh >= wind_danger:

        danger_triggers.append(
            f"Wind speed is {wind_speed_kmh:.1f} km/h "
            f"(danger threshold: {wind_danger:.1f} km/h)"
        )

    if wind_gusts_kmh >= gust_danger:

        danger_triggers.append(
            f"Wind gusts are {wind_gusts_kmh:.1f} km/h "
            f"(danger threshold: {gust_danger:.1f} km/h)"
        )


    # --------------------------------------------------------
    # 4. OFFICIAL WARNING OVERRIDE
    # --------------------------------------------------------

    if official_warning:

        return {
            "verdict": "DO NOT VENTURE",

            "badge_color": "red",

            "badge_text_en": "DO NOT VENTURE",

            "badge_text_hi": "समंदर में न जाएं",

            "advisory": (
                "An official marine/fishermen warning is active "
                "for this area. Follow the official advisory."
            ),

            "reasons": [
                f"Official warning: {official_warning}"
            ],

            "metrics": {
                "wave_height_m": wave_height_m,
                "wind_speed_kmh": wind_speed_kmh,
                "wind_gusts_kmh": wind_gusts_kmh
            },

            "thresholds_exceeded": [
                "OFFICIAL_WARNING"
            ],

            "official_warning": official_warning
        }


    # --------------------------------------------------------
    # 5. DO NOT VENTURE
    # --------------------------------------------------------

    if danger_triggers:

        return {
            "verdict": "DO NOT VENTURE",

            "badge_color": "red",

            "badge_text_en": "DO NOT VENTURE",

            "badge_text_hi": "समंदर में न जाएं",

            "advisory": (
                "Marine conditions exceed the prototype "
                "danger thresholds for the selected boat profile."
            ),

            "reasons": danger_triggers,

            "metrics": {
                "wave_height_m": wave_height_m,
                "wind_speed_kmh": wind_speed_kmh,
                "wind_gusts_kmh": wind_gusts_kmh
            },

            "thresholds_exceeded": danger_triggers,

            "official_warning": None
        }


    # --------------------------------------------------------
    # 6. CAUTION CONDITIONS
    # --------------------------------------------------------

    if wave_height_m >= wave_caution:

        caution_triggers.append(
            f"Wave height is {wave_height_m:.2f} m "
            f"(caution threshold: {wave_caution:.2f} m)"
        )

    if wind_speed_kmh >= wind_caution:

        caution_triggers.append(
            f"Wind speed is {wind_speed_kmh:.1f} km/h "
            f"(caution threshold: {wind_caution:.1f} km/h)"
        )

    if wind_gusts_kmh >= gust_caution:

        caution_triggers.append(
            f"Wind gusts are {wind_gusts_kmh:.1f} km/h "
            f"(caution threshold: {gust_caution:.1f} km/h)"
        )


    if caution_triggers:

        return {
            "verdict": "CAUTION",

            "badge_color": "yellow",

            "badge_text_en": "CAUTION",

            "badge_text_hi": "सावधानी बरतें",

            "advisory": (
                "Conditions are elevated. Small-boat fishers "
                "should assess the situation carefully, "
                "consider staying closer to shore, and "
                "follow local official advisories."
            ),

            "reasons": caution_triggers,

            "metrics": {
                "wave_height_m": wave_height_m,
                "wind_speed_kmh": wind_speed_kmh,
                "wind_gusts_kmh": wind_gusts_kmh
            },

            "thresholds_exceeded": caution_triggers,

            "official_warning": None
        }


    # --------------------------------------------------------
    # 7. NORMAL CONDITIONS
    # --------------------------------------------------------

    return {
        "verdict": "SAFE",

        "badge_color": "green",

        "badge_text_en": "SAFE",

        "badge_text_hi": "अनुकूल परिस्थितियां",

        "advisory": (
            "No major threshold has been exceeded in the "
            "available forecast data. Continue to monitor "
            "weather and official marine advisories."
        ),

        "reasons": [
            f"Wave height: {wave_height_m:.2f} m",
            f"Wind speed: {wind_speed_kmh:.1f} km/h",
            f"Wind gusts: {wind_gusts_kmh:.1f} km/h"
        ],

        "metrics": {
            "wave_height_m": wave_height_m,
            "wind_speed_kmh": wind_speed_kmh,
            "wind_gusts_kmh": wind_gusts_kmh
        },

        "thresholds_exceeded": [],

        "official_warning": None
    }


# ============================================================
# TIME-WINDOW ASSESSMENT
# ============================================================

def evaluate_time_window(
    hourly_data: List[Dict[str, Any]],
    profile: Dict[str, Any] = DEFAULT_PROFILE,
    official_warning: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate multiple forecast hours.

    Example:
        tomorrow morning = 06:00 to 10:00

    The overall result uses the most severe condition
    observed during the requested window.

    This prevents the system from saying SAFE simply because
    the average conditions look acceptable while one hour
    contains a dangerous spike.
    """

    if not hourly_data:

        return {
            "verdict": "DATA UNAVAILABLE",
            "hours_evaluated": 0,
            "hourly_results": [],
            "advisory": "No forecast hours were available."
        }


    hourly_results = []

    severity_order = {
        "SAFE": 1,
        "CAUTION": 2,
        "DO NOT VENTURE": 3,
        "DATA UNAVAILABLE": 4
    }


    for hour in hourly_data:

        result = evaluate_safety(
            wave_height_m=hour.get("wave_height"),
            wind_speed_kmh=hour.get("wind_speed"),
            wind_gusts_kmh=hour.get("wind_gust"),
            profile=profile,
            official_warning=official_warning
        )

        hourly_results.append({
            "time": hour.get("time"),
            "result": result
        })


    # --------------------------------------------------------
    # Find overall condition in requested period
    # --------------------------------------------------------

    # DATA UNAVAILABLE takes priority because a safety decision
    # must not be made from incomplete forecast data.
    if any(
        item["result"]["verdict"] == "DATA UNAVAILABLE"
        for item in hourly_results
    ):
        overall_verdict = "DATA UNAVAILABLE"

        # Find the first hour where required data is missing.
        overall_result = next(
            item
            for item in hourly_results
            if item["result"]["verdict"] == "DATA UNAVAILABLE"
        )

    else:
        # No missing data, so select the most severe valid condition.
        severity_order = {
            "SAFE": 1,
            "CAUTION": 2,
            "DO NOT VENTURE": 3
        }

        overall_result = max(
            hourly_results,
            key=lambda x: severity_order.get(
                x["result"]["verdict"],
                0
            )
        )

        overall_verdict = overall_result["result"]["verdict"]


    # --------------------------------------------------------
    # Build user-facing explanation
    # --------------------------------------------------------

    if overall_verdict == "DO NOT VENTURE":

        advisory = (
            "At least one forecast period contains conditions "
            "above the danger threshold. Do not treat the "
            "whole time window as suitable for fishing."
        )

    elif overall_verdict == "CAUTION":

        advisory = (
            "At least one forecast period has elevated marine "
            "conditions. Conditions should be reassessed "
            "before departure."
        )

    elif overall_verdict == "SAFE":

        advisory = (
            "No major prototype threshold was exceeded during "
            "the requested forecast period. Continue monitoring "
            "official marine warnings."
        )

    else:

        advisory = (
            "The forecast data is incomplete. "
            "A reliable assessment cannot be made."
        )


    return {
    "verdict": overall_verdict,

    "badge_color": {
        "SAFE": "green",
        "CAUTION": "yellow",
        "DO NOT VENTURE": "red",
        "DATA UNAVAILABLE": "gray"
    }.get(overall_verdict, "gray"),

    "badge_text_en": {
        "SAFE": "SAFE",
        "CAUTION": "CAUTION",
        "DO NOT VENTURE": "DO NOT VENTURE",
        "DATA UNAVAILABLE": "DATA UNAVAILABLE"
    }.get(overall_verdict, "DATA UNAVAILABLE"),

    "badge_text_hi": {
        "SAFE": "सुरक्षित",
        "CAUTION": "सावधानी",
        "DO NOT VENTURE": "समंदर में न जाएं",
        "DATA UNAVAILABLE": "डेटा उपलब्ध नहीं है"
    }.get(overall_verdict, "डेटा उपलब्ध नहीं है"),

    "advisory": advisory,

    "hours_evaluated": len(hourly_results),

    "hourly_results": hourly_results,

    "worst_period": overall_result["time"],

    "official_warning": official_warning
}


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":

    tests = [

        # Normal conditions
        {
            "name": "Normal",
            "wave": 0.8,
            "wind": 14,
            "gust": 20
        },

        # Elevated wave
        {
            "name": "Elevated waves",
            "wave": 1.8,
            "wind": 18,
            "gust": 30
        },

        # Elevated wind
        {
            "name": "Elevated wind",
            "wave": 1.0,
            "wind": 28,
            "gust": 35
        },

        # Dangerous wave
        {
            "name": "Dangerous waves",
            "wave": 2.6,
            "wind": 20,
            "gust": 30
        },

        # Dangerous wind
        {
            "name": "Dangerous wind",
            "wave": 1.0,
            "wind": 47,
            "gust": 55
        },

        # Dangerous gust
        {
            "name": "Dangerous gust",
            "wave": 1.2,
            "wind": 20,
            "gust": 65
        }
    ]


    for test in tests:

        result = evaluate_safety(
            wave_height_m=test["wave"],
            wind_speed_kmh=test["wind"],
            wind_gusts_kmh=test["gust"]
        )

        print(
            f"{test['name']}: "
            f"{result['verdict']}"
        )