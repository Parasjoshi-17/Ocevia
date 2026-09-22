"""
OceanMind AI - Explanation Agent

Responsibility:
    Convert an already calculated safety result
    into a user-friendly explanation.

The explanation agent cannot change the verdict.
"""

from ai_explain import get_ai_explanation


def run_explanation_agent(
    city_name,
    target_day,
    verdict,
    wave_height_m,
    wind_speed_kmh,
    wind_gusts_kmh,
    reasons,
):
    """
    Generate an explanation for an already calculated result.
    """

    try:

        explanation = get_ai_explanation(
            city_name=city_name,
            target_day=target_day,
            verdict=verdict,
            wave_height_m=wave_height_m,
            wind_speed_kmh=wind_speed_kmh,
            wind_gusts_kmh=wind_gusts_kmh,
            reasons=reasons,
        )

        return {
            "status": "success",
            "explanation": explanation,
        }

    except Exception as exc:

        return {
            "status": "error",
            "error": str(exc),
        }