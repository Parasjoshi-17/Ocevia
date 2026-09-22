"""
marine.py

Fetches hourly ocean/marine data from Open-Meteo Marine API.

This module only retrieves marine data.
It does NOT make safety decisions.
It does NOT generate estimated/fake values.
"""

import urllib.request
import urllib.parse
import json
import logging
import math
from typing import Dict, Any

logger = logging.getLogger(__name__)

OPEN_METEO_MARINE_URL = (
    "https://marine-api.open-meteo.com/v1/marine"
)


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


def get_marine(
    latitude: float,
    longitude: float,
    date: str
) -> Dict[str, Any]:
    """
    Fetch hourly marine data for a specific location and date.

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
        Normalized marine data.
    """

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "hourly": [
            "wave_height",
            "wave_direction",
            "wind_wave_height",
            "wind_wave_direction",
            "sea_surface_temperature"
        ],

        "start_date": date,
        "end_date": date,

        "timezone": "auto"
    }

    try:

        data = _fetch_json(
            OPEN_METEO_MARINE_URL,
            params
        )

        hourly = data.get("hourly")

        if not hourly:
            return {
                "marine": None,
                "error": "Marine API returned no hourly data"
            }

        times = hourly.get("time", [])

        wave_heights = hourly.get(
            "wave_height",
            []
        )

        wave_directions = hourly.get(
            "wave_direction",
            []
        )

        wind_wave_heights = hourly.get(
            "wind_wave_height",
            []
        )

        wind_wave_directions = hourly.get(
            "wind_wave_direction",
            []
        )

        sea_surface_temperatures = hourly.get(
            "sea_surface_temperature",
            []
        )

        hourly_data = []

        for i, time in enumerate(times):

            hourly_data.append({
                "time": time,

                "wave_height": _clean_value(
                    wave_heights[i]
                    if i < len(wave_heights)
                    else None
                ),

                "wave_direction": _clean_value(
                    wave_directions[i]
                    if i < len(wave_directions)
                    else None
                ),

                "wind_wave_height": _clean_value(
                    wind_wave_heights[i]
                    if i < len(wind_wave_heights)
                    else None
                ),

                "wind_wave_direction": _clean_value(
                    wind_wave_directions[i]
                    if i < len(wind_wave_directions)
                    else None
                ),

                "sea_surface_temperature": _clean_value(
                    sea_surface_temperatures[i]
                    if i < len(sea_surface_temperatures)
                    else None
                )
            })

        return {
            "marine": {
                "latitude": latitude,
                "longitude": longitude,
                "date": date,

                "units": {
                    "wave_height": "m",
                    "wave_direction": "degrees",
                    "wind_wave_height": "m",
                    "wind_wave_direction": "degrees",
                    "sea_surface_temperature": "°C"
                },

                "hourly": hourly_data
            },

            "source": "Open-Meteo Marine API"
        }

    except Exception as e:

        logger.error(
            f"Marine API error: {e}"
        )

        return {
            "marine": None,
            "error": "Unable to fetch marine data"
        }


if __name__ == "__main__":

    # Mumbai test coordinates
    latitude = 19.076
    longitude = 72.8777

    result = get_marine(
        latitude,
        longitude,
        "2026-09-18"
    )

    print(json.dumps(
        result,
        indent=2
    ))