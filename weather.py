"""
weather.py

Fetches hourly weather data from Open-Meteo.

This module is responsible only for weather data.
It does NOT make safety decisions and does NOT generate
fallback weather values.
"""

import urllib.request
import urllib.parse
import json
import logging
import math
from typing import Dict, Any

logger = logging.getLogger(__name__)

OPEN_METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def _fetch_json(
    url: str,
    params: Dict[str, Any],
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Send GET request and return parsed JSON.
    """

    query_string = urllib.parse.urlencode(
        params,
        doseq=True
    )

    full_url = f"{url}?{query_string}"

    headers = {
        "User-Agent": "OceanMindAI/1.0"
    }

    request = urllib.request.Request(
        full_url,
        headers=headers
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout
    ) as response:

        content = response.read().decode("utf-8")

        return json.loads(content)


def _clean_value(value):
    """
    Convert invalid numeric values such as NaN into None.
    """

    if value is None:
        return None

    try:
        value = float(value)

        if math.isnan(value) or math.isinf(value):
            return None

        return value

    except (TypeError, ValueError):
        return None


def get_weather(
    latitude: float,
    longitude: float,
    date: str
) -> Dict[str, Any]:
    """
    Fetch hourly weather data for a specific location and date.

    Parameters
    ----------
    latitude : float
        Location latitude.

    longitude : float
        Location longitude.

    date : str
        Date in YYYY-MM-DD format.

    Returns
    -------
    dict
        Normalized weather data.
    """

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "hourly": [
            "temperature_2m",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "precipitation"
        ],

        "start_date": date,
        "end_date": date,

        "wind_speed_unit": "kmh",

        "timezone": "auto"
    }

    try:

        data = _fetch_json(
            OPEN_METEO_WEATHER_URL,
            params
        )

        hourly = data.get("hourly")

        if not hourly:
            return {
                "weather": None,
                "error": "Weather API returned no hourly data"
            }

        times = hourly.get("time", [])

        temperatures = hourly.get(
            "temperature_2m",
            []
        )

        wind_speeds = hourly.get(
            "wind_speed_10m",
            []
        )

        wind_directions = hourly.get(
            "wind_direction_10m",
            []
        )

        wind_gusts = hourly.get(
            "wind_gusts_10m",
            []
        )

        precipitation = hourly.get(
            "precipitation",
            []
        )

        hourly_data = []

        for i, time in enumerate(times):

            hourly_data.append({
                "time": time,

                "temperature": _clean_value(
                    temperatures[i]
                    if i < len(temperatures)
                    else None
                ),

                "wind_speed": _clean_value(
                    wind_speeds[i]
                    if i < len(wind_speeds)
                    else None
                ),

                "wind_direction": _clean_value(
                    wind_directions[i]
                    if i < len(wind_directions)
                    else None
                ),

                "wind_gust": _clean_value(
                    wind_gusts[i]
                    if i < len(wind_gusts)
                    else None
                ),

                "precipitation": _clean_value(
                    precipitation[i]
                    if i < len(precipitation)
                    else None
                )
            })

        return {
            "weather": {
                "latitude": latitude,
                "longitude": longitude,
                "date": date,

                "units": {
                    "temperature": "°C",
                    "wind_speed": "km/h",
                    "wind_direction": "degrees",
                    "wind_gust": "km/h",
                    "precipitation": "mm"
                },

                "hourly": hourly_data
            },

            "source": "Open-Meteo Weather API"
        }

    except Exception as e:

        logger.error(
            f"Weather API error: {e}"
        )

        return {
            "weather": None,
            "error": "Unable to fetch weather data"
        }


if __name__ == "__main__":

    # Mumbai test coordinates
    latitude = 19.076
    longitude = 72.8777

    result = get_weather(
        latitude,
        longitude,
        "2026-09-18"
    )

    print(json.dumps(
        result,
        indent=2
    ))