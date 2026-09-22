"""
OceanMind AI - Ocean Agent

Responsibility:
    Retrieve marine/ocean forecast data.

This agent does NOT:
    - decide safety
    - decide fishing opportunity
    - generate explanations
"""

from marine import get_marine


def run_ocean_agent(latitude, longitude, forecast_date):
    """
    Retrieve marine data for the requested location and date.

    Returns:
        Dictionary containing marine data or an error.
    """

    try:

        result = get_marine(
            latitude=latitude,
            longitude=longitude,
            date=forecast_date,
        )

        if not isinstance(result, dict):

            return {
                "status": "error",
                "error": "Ocean agent received an invalid response.",
            }

        if result.get("marine") is None:

            return {
                "status": "error",
                "error": result.get(
                    "error",
                    "Marine data unavailable."
                ),
            }

        return {
            "status": "success",
            "source": "Open-Meteo Marine API",
            "data": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "error": str(exc),
        }