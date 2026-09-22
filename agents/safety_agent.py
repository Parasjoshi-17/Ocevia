"""
OceanMind AI - Safety Agent

Responsibility:
    Send selected scientific measurements to the
    deterministic safety engine.

The actual safety decision is made by rules.py.

The Safety Agent does NOT use an LLM.
"""

from rules import evaluate_time_window


def run_safety_agent(hourly_data):
    """
    Evaluate marine safety for the selected time window.

    Args:
        hourly_data:
            Filtered hourly weather/marine records.

    Returns:
        Deterministic safety result.
    """

    if not isinstance(hourly_data, list):
        return {
            "status": "error",
            "error": "Safety agent requires hourly data.",
        }

    if not hourly_data:
        return {
            "status": "error",
            "error": "No hourly data available for safety analysis.",
        }

    try:

        result = evaluate_time_window(
            hourly_data=hourly_data
        )

        if not isinstance(result, dict):

            return {
                "status": "error",
                "error": "Safety engine returned an invalid result.",
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