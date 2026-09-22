"""
ai_explain.py

OceanMind AI - AI Explanation Layer

IMPORTANT:
The AI does NOT calculate marine safety.

The deterministic rule engine has already calculated:
    SAFE
    CAUTION
    DO NOT VENTURE
    DATA UNAVAILABLE

Claude's ONLY job is to explain that result in simple Hinglish.

The AI must NEVER:
- change the verdict
- calculate a new verdict
- invent weather/ocean values
- invent PFZ information
- invent fish species
- override the deterministic rule engine
"""

import os
import logging
from typing import List, Optional, Dict, Any


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# FALLBACK EXPLANATION
# ============================================================

def generate_fallback_explanation(
    city_name: str,
    target_day: str,
    verdict: str,
    wave_height_m: Optional[float],
    wind_speed_kmh: Optional[float],
    wind_gusts_kmh: Optional[float],
    reasons: List[str],
    worst_period: Optional[str] = None
) -> str:
    """
    Generate a safe fallback explanation when Claude is unavailable.

    This function does NOT calculate the verdict.
    It only explains the verdict already provided.
    """

    day_hi = {
        "today": "aaj",
        "tomorrow": "kal",
        "day_after": "parson"
    }.get(target_day, target_day)

    # --------------------------------------------------------
    # DATA UNAVAILABLE
    # --------------------------------------------------------

    if verdict == "DATA UNAVAILABLE":
        return (
            f"{city_name} mein {day_hi} ke liye zaroori marine forecast data "
            f"poora available nahi hai. Incomplete data ke basis par fishing "
            f"ka safety decision na lein. Data dobara check karein."
        )

    # --------------------------------------------------------
    # DO NOT VENTURE
    # --------------------------------------------------------

    if verdict == "DO NOT VENTURE":
        detail = ""

        if reasons:
            detail = reasons[0]

        return (
            f"{city_name} mein {day_hi} samundari conditions safe nahi hain "
            f"(DO NOT VENTURE). {detail} Apni safety sabse pehle rakhein "
            f"aur samundar mein na jaayein. Official advisory ho to uska "
            f"pal an karein."
        )

    # --------------------------------------------------------
    # CAUTION
    # --------------------------------------------------------

    if verdict == "CAUTION":
        detail = ""

        if reasons:
            detail = reasons[0]

        return (
            f"{city_name} mein {day_hi} savdhani ki zaroorat hai (CAUTION). "
            f"{detail} Conditions ko departure se pehle dobara check karein "
            f"aur zaroori safety precautions follow karein."
        )

    # --------------------------------------------------------
    # SAFE
    # --------------------------------------------------------

    return (
        f"{city_name} mein {day_hi} ke forecast mein koi prototype safety "
        f"threshold exceed nahi hua (SAFE). Phir bhi samundari conditions "
        f"badal sakti hain, isliye departure se pehle latest forecast aur "
        f"official advisory check karein."
    )


# ============================================================
# CLAUDE EXPLANATION
# ============================================================

def get_ai_explanation(
    city_name: str,
    target_day: str,
    verdict: str,
    wave_height_m: Optional[float],
    wind_speed_kmh: Optional[float],
    wind_gusts_kmh: Optional[float],
    reasons: List[str],
    worst_period: Optional[str] = None,
    hours_evaluated: Optional[int] = None
) -> str:
    """
    Generate a short Hinglish explanation using Claude.

    CRITICAL:
    The verdict is already calculated by the deterministic rule engine.

    Claude can explain it but MUST NOT:
        - change it
        - contradict it
        - calculate another verdict
        - invent missing data
    """

    # --------------------------------------------------------
    # Validate inputs
    # --------------------------------------------------------

    verdict = str(verdict or "DATA UNAVAILABLE").strip().upper()

    if not isinstance(reasons, list):
        reasons = []

    # --------------------------------------------------------
    # API KEY
    # --------------------------------------------------------

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        logger.info(
            "ANTHROPIC_API_KEY is not set. "
            "Using deterministic fallback explanation."
        )

        return generate_fallback_explanation(
            city_name=city_name,
            target_day=target_day,
            verdict=verdict,
            wave_height_m=wave_height_m,
            wind_speed_kmh=wind_speed_kmh,
            wind_gusts_kmh=wind_gusts_kmh,
            reasons=reasons,
            worst_period=worst_period
        )

    # --------------------------------------------------------
    # Import Anthropic only when required
    # --------------------------------------------------------

    try:
        from anthropic import Anthropic

    except ImportError:
        logger.warning(
            "Anthropic package is not installed. "
            "Using fallback explanation."
        )

        return generate_fallback_explanation(
            city_name=city_name,
            target_day=target_day,
            verdict=verdict,
            wave_height_m=wave_height_m,
            wind_speed_kmh=wind_speed_kmh,
            wind_gusts_kmh=wind_gusts_kmh,
            reasons=reasons,
            worst_period=worst_period
        )

    # --------------------------------------------------------
    # Create Claude client
    # --------------------------------------------------------

    try:
        client = Anthropic(api_key=api_key)

    except Exception as e:
        logger.warning(
            f"Could not initialize Anthropic client: {e}"
        )

        return generate_fallback_explanation(
            city_name=city_name,
            target_day=target_day,
            verdict=verdict,
            wave_height_m=wave_height_m,
            wind_speed_kmh=wind_speed_kmh,
            wind_gusts_kmh=wind_gusts_kmh,
            reasons=reasons,
            worst_period=worst_period
        )

    # --------------------------------------------------------
    # Prepare safe values for prompt
    # --------------------------------------------------------

    wave_text = (
        f"{wave_height_m:.2f} m"
        if isinstance(wave_height_m, (int, float))
        else "unavailable"
    )

    wind_text = (
        f"{wind_speed_kmh:.1f} km/h"
        if isinstance(wind_speed_kmh, (int, float))
        else "unavailable"
    )

    gust_text = (
        f"{wind_gusts_kmh:.1f} km/h"
        if isinstance(wind_gusts_kmh, (int, float))
        else "unavailable"
    )

    reason_text = (
        "; ".join(str(reason) for reason in reasons)
        if reasons
        else "No specific threshold reason was recorded."
    )

    period_text = worst_period or "Not available"

    hours_text = (
        str(hours_evaluated)
        if hours_evaluated is not None
        else "Not available"
    )

    # ========================================================
    # SYSTEM INSTRUCTION
    # ========================================================

    system_instruction = """
You are the explanation layer of OceanMind AI.

You help Indian fishermen understand marine forecast results
in simple everyday Hinglish using Roman Hindi.

CRITICAL ARCHITECTURE RULE:

The safety verdict has ALREADY been calculated by a deterministic
OceanMind rule engine.

You MUST NOT:
- calculate a new safety verdict
- change the verdict
- contradict the verdict
- downgrade the verdict
- upgrade the verdict
- invent weather values
- invent ocean values
- invent PFZ information
- invent fish species
- claim that the rule engine is officially certified
- claim that the thresholds are official government limits

Your ONLY job is to explain the supplied result.

The supplied verdict is authoritative for this response.

Use only the data provided in the user message.

If a value is unavailable, say that it is unavailable.

Keep the response concise, practical and understandable
for a fisherman.

Use simple Hinglish in Roman script.

Do not give a guarantee that conditions are completely safe.

Mention checking the latest official marine/fishermen advisory
when appropriate.

Maximum 70 words.
"""

    # ========================================================
    # USER PROMPT
    # ========================================================

    user_prompt = f"""
OceanMind AI forecast result:

City:
{city_name}

Forecast day:
{target_day}

Safety verdict:
{verdict}

Worst forecast period:
{period_text}

Hours evaluated:
{hours_text}

Wave height at the worst period:
{wave_text}

Wind speed at the worst period:
{wind_text}

Wind gust at the worst period:
{gust_text}

Rule-engine reasons:
{reason_text}

Explain this EXACT result to the fisherman in simple Hinglish.

Do NOT change the verdict.

Do NOT make a new safety calculation.

Do NOT invent information.

If the verdict is:
SAFE:
Explain that no configured prototype safety threshold was exceeded,
while reminding the user that conditions can change.

CAUTION:
Explain the reason for caution and recommend reassessing conditions
before departure and following appropriate safety precautions.

DO NOT VENTURE:
Clearly tell the fisherman not to venture into the sea and
to follow official advisories.

DATA UNAVAILABLE:
Clearly explain that the required forecast data is incomplete
and a safety decision should not be made from incomplete data.
"""

    # ========================================================
    # CLAUDE MODEL
    # ========================================================

    model_names = [
        "claude-sonnet-4-6",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022"
    ]

    last_error = None

    # ========================================================
    # TRY MODELS
    # ========================================================

    for model_name in model_names:

        try:

            logger.info(
                f"Requesting Claude explanation using {model_name}"
            )

            response = client.messages.create(
                model=model_name,
                max_tokens=180,
                system=system_instruction,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )

            # ------------------------------------------------
            # Extract text safely
            # ------------------------------------------------

            if not response.content:
                continue

            text_parts = []

            for block in response.content:

                if hasattr(block, "text"):
                    text_parts.append(block.text)

            explanation = " ".join(text_parts).strip()

            if explanation:
                return explanation

        except Exception as e:

            last_error = e

            logger.warning(
                f"Claude model {model_name} failed: {e}"
            )

    # ========================================================
    # FALLBACK
    # ========================================================

    logger.warning(
        f"All Claude models failed. Last error: {last_error}"
    )

    return generate_fallback_explanation(
        city_name=city_name,
        target_day=target_day,
        verdict=verdict,
        wave_height_m=wave_height_m,
        wind_speed_kmh=wind_speed_kmh,
        wind_gusts_kmh=wind_gusts_kmh,
        reasons=reasons,
        worst_period=worst_period
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("OceanMind AI - AI Explanation Test")
    print("=" * 60)

    test_cases = [

        {
            "verdict": "SAFE",
            "wave": 0.9,
            "wind": 15.0,
            "gust": 25.0,
            "reasons": []
        },

        {
            "verdict": "CAUTION",
            "wave": 0.98,
            "wind": 15.5,
            "gust": 40.0,
            "reasons": [
                "Wind gusts are 40.0 km/h "
                "(caution threshold: 40.0 km/h)"
            ]
        },

        {
            "verdict": "DO NOT VENTURE",
            "wave": 2.8,
            "wind": 30.0,
            "gust": 50.0,
            "reasons": [
                "Wave height is 2.80 m "
                "(danger threshold: 2.50 m)"
            ]
        },

        {
            "verdict": "DATA UNAVAILABLE",
            "wave": None,
            "wind": None,
            "gust": None,
            "reasons": [
                "Missing: wave height"
            ]
        }
    ]

    for case in test_cases:

        print()
        print("-" * 60)
        print(f"VERDICT: {case['verdict']}")
        print("-" * 60)

        result = get_ai_explanation(
            city_name="Mumbai",
            target_day="tomorrow",
            verdict=case["verdict"],
            wave_height_m=case["wave"],
            wind_speed_kmh=case["wind"],
            wind_gusts_kmh=case["gust"],
            reasons=case["reasons"],
            worst_period="2026-09-18T12:00",
            hours_evaluated=24
        )

        print(result)