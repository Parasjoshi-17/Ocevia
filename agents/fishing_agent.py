"""Fishing Opportunity Agent for Ocevia.

This agent is a thin orchestration wrapper around the deterministic
fishing-suitability engine. It does not calculate marine safety and
does not invent PFZ or fisheries data.
"""

from fishing_suitability import evaluate_fishing_suitability


def run_fishing_agent(safety_verdict, pfz_result):
    """
    Evaluate fishing opportunity using the already-decided safety verdict
    and normalized PFZ result.

    Returns:
        {
            "status": "success",
            "data": {...}
        }
        or
        {
            "status": "error",
            "error": "..."
        }
    """
    try:
        result = evaluate_fishing_suitability(
            safety_verdict=safety_verdict,
            pfz_result=pfz_result,
        )

        if not isinstance(result, dict):
            return {
                "status": "error",
                "error": "Fishing suitability engine returned an invalid response.",
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
