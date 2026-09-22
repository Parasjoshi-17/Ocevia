"""
OceanMind AI - PFZ Agent

Responsibility:
    Retrieve the official INCOIS Potential Fishing Zone (PFZ)
    advisory for a city's sector.

This agent does NOT:
    - decide fishing suitability
    - decide safety
    - invent PFZ coordinates when the official advisory is
      unavailable
"""

from pfz import get_pfz_advisory


def run_pfz_agent(city_name, state, forecast_date):
    """
    Retrieve the PFZ advisory for the requested city/date.

    Returns:
        {
            "status": "success",
            "data": { ... }          # see pfz.get_pfz_advisory
        }
        or
        {
            "status": "success",
            "data": {"status": "unavailable", ...}
        }

    NOTE:
    "status": "success" here means the agent ran without a
    crash - it does NOT mean a PFZ advisory was found. Check
    data["status"] ("success" vs "unavailable") for that.
    """

    try:

        result = get_pfz_advisory(
            city_name=city_name,
            state=state,
            forecast_date=forecast_date,
        )

        if not isinstance(result, dict):

            return {
                "status": "error",
                "error": "PFZ agent received an invalid response.",
            }

        return {
            "status": "success",
            "data": result,
        }

    except Exception as exc:

        return {
            "status": "error",
            "error": str(exc),
        }
