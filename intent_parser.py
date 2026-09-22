"""
OceanMind AI - Natural Language Intent Parser

Converts a user's natural-language fishing query into
structured information that the backend can process.

Example:

Input:
    "Can I go fishing tomorrow morning near Mumbai?"

Output:
    {
        "intent": "fishing_safety",
        "city": "Mumbai",
        "target_day": "tomorrow",
        "time_window": "morning"
    }

IMPORTANT:
- This parser does NOT decide safety.
- This parser does NOT use weather data.
- This parser does NOT generate the final answer.
- It only extracts structured intent from the user's query.
"""

import re


# ============================================================
# SUPPORTED CITIES
# ============================================================

CITY_ALIASES = {
    "mumbai": "Mumbai",
    "bombay": "Mumbai",

    "kochi": "Kochi",
    "cochin": "Kochi",

    "chennai": "Chennai",
    "madras": "Chennai",

    "visakhapatnam": "Visakhapatnam",
    "vizag": "Visakhapatnam",

    "mangalore": "Mangaluru",
    "mangaluru": "Mangaluru",

    "panaji": "Panaji",
    "goa": "Panaji",

    "puri": "Puri",

    "veraval": "Veraval",

    "kanyakumari": "Kanyakumari",

    "digha": "Digha",
}


# ============================================================
# DAY ALIASES
# ============================================================

DAY_PATTERNS = [
    (
        r"\bday\s+after\s+tomorrow\b",
        "day_after_tomorrow",
    ),
    (
        r"\bday-after-tomorrow\b",
        "day_after_tomorrow",
    ),
    (
        r"\btomorrow\b",
        "tomorrow",
    ),
    (
        r"\btoday\b",
        "today",
    ),
]


# ============================================================
# TIME-WINDOW ALIASES
# ============================================================

TIME_PATTERNS = [
    (
        r"\b(morning|mornings)\b",
        "morning",
    ),
    (
        r"\b(afternoon|afternoons)\b",
        "afternoon",
    ),
    (
        r"\b(evening|evenings)\b",
        "evening",
    ),
    (
        r"\b(all\s*day|whole\s*day|entire\s*day)\b",
        "all_day",
    ),
]


# ============================================================
# INTENT DETECTION
# ============================================================

def detect_intent(query):
    """
    Detect the broad purpose of the user's query.

    Currently supported:
        fishing_safety
        unknown
    """

    if not isinstance(query, str):
        return "unknown"

    text = query.lower().strip()

    fishing_keywords = [
        "fish",
        "fishing",
        "fisherman",
        "fishermen",
        "fishing trip",
        "fishing boat",
        "go fishing",
        "मछली",
        "मासेमारी",
    ]

    safety_keywords = [
        "safe",
        "safety",
        "can i go",
        "should i go",
        "weather",
        "condition",
        "conditions",
        "जाऊ",
        "सुरक्षित",
        "सुरक्षा",
    ]

    has_fishing = any(
        keyword in text
        for keyword in fishing_keywords
    )

    has_safety = any(
        keyword in text
        for keyword in safety_keywords
    )

    if has_fishing and has_safety:
        return "fishing_safety"

    if has_fishing:
        return "fishing_safety"

    return "unknown"


# ============================================================
# CITY EXTRACTION
# ============================================================

def extract_city(query):
    """
    Extract a supported coastal city from the query.
    """

    if not isinstance(query, str):
        return None

    text = query.lower()

    # Sort by length so longer names are checked first.
    # Example: "Mangaluru" before shorter possible matches.
    for alias in sorted(
        CITY_ALIASES.keys(),
        key=len,
        reverse=True
    ):

        pattern = r"\b" + re.escape(alias) + r"\b"

        if re.search(pattern, text):
            return CITY_ALIASES[alias]

    return None


# ============================================================
# DAY EXTRACTION
# ============================================================

def extract_target_day(query):
    """
    Extract:
        today
        tomorrow
        day_after_tomorrow

    Defaults to tomorrow when no explicit day is mentioned.
    """

    if not isinstance(query, str):
        return None

    text = query.lower().strip()

    for pattern, target_day in DAY_PATTERNS:

        if re.search(pattern, text):
            return target_day

    # For fishing questions, tomorrow is the default.
    return "tomorrow"


# ============================================================
# TIME-WINDOW EXTRACTION
# ============================================================

def extract_time_window(query):
    """
    Extract:
        morning
        afternoon
        evening
        all_day

    Defaults to all_day if no specific period is mentioned.
    """

    if not isinstance(query, str):
        return None

    text = query.lower().strip()

    for pattern, time_window in TIME_PATTERNS:

        if re.search(pattern, text):
            return time_window

    return "all_day"


# ============================================================
# COMPLETE QUERY PARSER
# ============================================================

def parse_query(query):
    """
    Convert natural-language query into structured intent.
    """

    if not isinstance(query, str):
        return {
            "status": "error",
            "message": "Query must be a string.",
        }

    query = query.strip()

    if not query:
        return {
            "status": "error",
            "message": "Query cannot be empty.",
        }

    intent = detect_intent(query)
    city = extract_city(query)
    target_day = extract_target_day(query)
    time_window = extract_time_window(query)

    return {
        "status": "success",
        "intent": intent,
        "city": city,
        "target_day": target_day,
        "time_window": time_window,
        "original_query": query,
    }


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":

    test_queries = [
        "Can I go fishing tomorrow morning near Mumbai?",
        "Can I go fishing tomorrow evening near Kochi?",
        "Can I go fishing day after tomorrow near Chennai?",
        "Is it safe to fish in Mumbai tomorrow afternoon?",
        "Can I go fishing today near Panaji?",
        "Can I go fishing near Mangalore tomorrow morning?",
    ]

    print("=" * 70)
    print("OceanMind AI - Intent Parser Test")
    print("=" * 70)

    for query in test_queries:

        result = parse_query(query)

        print("\nQUERY:")
        print(query)

        print("\nRESULT:")
        print(result)

        print("-" * 70)