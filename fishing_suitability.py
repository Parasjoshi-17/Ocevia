"""
fishing_suitability.py

Deterministic fishing-opportunity engine for OceanMind AI.

IMPORTANT:
- This is NOT a machine-learning model. There is no reliable
  labelled training dataset for this hackathon prototype, so
  fishing suitability is computed the same way marine safety is:
  fixed, explainable rules over real evidence.
- This engine NEVER recomputes or overrides the marine safety
  verdict from rules.py. Safety and fishing opportunity are kept
  as two separate concepts that are only combined here at the
  very end, for display purposes.
- This engine NEVER invents PFZ points, chlorophyll values, or
  fish species. It only reasons about whatever pfz.py actually
  returned.
- There is deliberately NO numeric "fishing score" and no
  "low/medium/high probability": a missing PFZ advisory is reported
  as missing, never translated into "low opportunity".

THE RULE:
    DATA PROVIDES EVIDENCE.
    RULES DECIDE SAFETY.
    AI EXPLAINS.

Fishing suitability sits alongside "RULES DECIDE SAFETY": it is
a second, independent deterministic rule set, not a new safety
decision and not an AI guess.
"""

from typing import Dict, Any, Optional


# ============================================================
# FISHING STATUS VALUES
# ============================================================

STATUS_UNSAFE_DO_NOT_VENTURE = "unsafe_do_not_venture"
STATUS_DATA_UNAVAILABLE = "data_unavailable"
STATUS_PFZ_UNAVAILABLE = "pfz_unavailable"
STATUS_OPPORTUNITY_WITH_CAUTION = "opportunity_with_caution"
STATUS_OPPORTUNITY_INDICATED = "opportunity_indicated"

LABEL_PFZ_AVAILABLE = "PFZ advisory available"
LABEL_PFZ_UNAVAILABLE = "No current PFZ advisory"
LABEL_DATA_UNAVAILABLE = "Fishing opportunity unavailable"

PFZ_UNAVAILABLE_MESSAGE = (
    "No current PFZ advisory available for this region/date."
)


def evaluate_fishing_suitability(
    safety_verdict: str,
    pfz_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Combine the (already-decided) marine safety verdict with the
    PFZ advisory to produce a fishing-opportunity assessment.

    Parameters
    ----------
    safety_verdict : str
        One of "SAFE", "CAUTION", "DO NOT VENTURE",
        "DATA UNAVAILABLE" - as decided by rules.py. This
        function treats it as authoritative and never changes
        it.

    pfz_result : dict or None
        The normalized dict returned by pfz.get_pfz_advisory():
        {"available": True, "zones": [...], "sector": ..., ...}
        or
        {"available": False, "sector": ..., "message": ...}

    Returns
    -------
    dict:
        {
            "fishing_status": <one of the STATUS_* constants>,
            "label": <short heading, e.g. "PFZ advisory available">,
            "message": <deterministic, rule-generated explanation>,
            "safety_verdict": <passthrough of safety_verdict>,
            "pfz_available": True | False,
            "sector": <sector name if known>,
            "zone_count": <number of real PFZ zones, if any>,
        }
    """

    if not isinstance(pfz_result, dict):
        pfz_result = {}

    zones = pfz_result.get("zones")
    zone_count = len(zones) if isinstance(zones, list) else 0

    pfz_available = pfz_result.get("available") is True and zone_count > 0
    sector = pfz_result.get("sector")

    label = LABEL_PFZ_AVAILABLE if pfz_available else LABEL_PFZ_UNAVAILABLE

    verdict = str(safety_verdict or "DATA UNAVAILABLE").strip().upper()

    def result(status, result_label, message):

        return {
            "fishing_status": status,
            "label": result_label,
            "message": message,
            "safety_verdict": verdict,
            "pfz_available": pfz_available,
            "sector": sector,
            "zone_count": zone_count,
        }

    # --------------------------------------------------------
    # 1. SAFETY DATA ITSELF IS INCOMPLETE
    #
    # If we cannot even determine whether it is safe to be at
    # sea, we cannot responsibly comment on where to fish
    # either. This mirrors rules.py's own "DATA UNAVAILABLE
    # takes priority" behaviour.
    # --------------------------------------------------------

    if verdict == "DATA UNAVAILABLE":

        return result(
            STATUS_DATA_UNAVAILABLE,
            LABEL_DATA_UNAVAILABLE,
            (
                "Marine safety data is incomplete, so fishing "
                "opportunity cannot be assessed from this "
                "forecast."
            ),
        )

    # --------------------------------------------------------
    # 2. UNSAFE OVERRIDES EVERYTHING
    #
    # Hard rule: if safety is DO NOT VENTURE, the system must never
    # recommend going fishing, even if the PFZ advisory indicates
    # activity. The PFZ label still reports the advisory honestly;
    # the message carries the safety-first recommendation.
    # --------------------------------------------------------

    if verdict == "DO NOT VENTURE":

        if pfz_available:
            message = (
                "Potential fishing activity may be indicated, but "
                "current marine conditions are unsafe. Do not venture."
            )
        else:
            message = (
                "Current marine conditions are unsafe "
                "(DO NOT VENTURE). Do not venture, regardless of "
                "fishing zone data."
            )

        return result(
            STATUS_UNSAFE_DO_NOT_VENTURE,
            label,
            message,
        )

    # --------------------------------------------------------
    # 3. SAFE or CAUTION, BUT NO PFZ ADVISORY AVAILABLE
    #
    # Unavailable PFZ data is reported as unavailable - never
    # silently treated as "no fishing opportunity" or "low
    # suitability".
    # --------------------------------------------------------

    if not pfz_available:

        return result(
            STATUS_PFZ_UNAVAILABLE,
            label,
            PFZ_UNAVAILABLE_MESSAGE,
        )

    # --------------------------------------------------------
    # 4. SAFE or CAUTION, PFZ ADVISORY AVAILABLE
    # --------------------------------------------------------

    if verdict == "CAUTION":

        return result(
            STATUS_OPPORTUNITY_WITH_CAUTION,
            label,
            (
                "The PFZ advisory indicates potential fishing "
                "activity in this sector, but marine conditions "
                "call for caution. Assess conditions carefully "
                "before heading to the indicated zones."
            ),
        )

    if verdict == "SAFE":

        return result(
            STATUS_OPPORTUNITY_INDICATED,
            label,
            (
                "The PFZ advisory indicates potential fishing "
                "activity in this sector, and marine conditions are "
                "currently safe."
            ),
        )

    # Any other value is not a verdict rules.py produces. Never let
    # an unrecognised string fall through to "safe".

    return result(
        STATUS_DATA_UNAVAILABLE,
        LABEL_DATA_UNAVAILABLE,
        (
            "The marine safety verdict was not recognised, so "
            "fishing opportunity cannot be assessed."
        ),
    )
