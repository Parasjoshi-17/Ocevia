"""
OceanMind AI - Weather Agent

Responsibility:
    Retrieve weather forecast data for a requested location and date.

This agent does NOT:
    - decide safety
    - decide fishing opportunity
    - generate explanations
"""

from weather import get_weather


def run_weather_agent(latitude, longitude, forecast_date):
    """
    Retrieve weather data for the requested location and date.

    Returns:
        Dictionary containing weather data or an error.
    """

    try:
        result = get_weather(
            latitude=latitude,
            longitude=longitude,
            date=forecast_date,
        )

        if not isinstance(result, dict):
            return {
                "status": "error",
                "error": "Weather agent received an invalid response.",
            }

        if result.get("weather") is None:
            return {
                "status": "error",
                "error": result.get(
                    "error",
                    "Weather data unavailable."
                ),
            }

        return {
            "status": "success",
            "source": "Open-Meteo Forecast API",
            "data": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "error": str(exc),
        }