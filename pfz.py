"""
pfz.py

Fetches official INCOIS Potential Fishing Zone (PFZ) advisory
data for a given coastal state/sector and returns ONE normalized
shape that every other module (fishing_suitability, orchestrator,
map_data, the React PFZ layer) consumes.

This module only retrieves PFZ data.
It does NOT decide fishing suitability.
It does NOT invent PFZ coordinates, chlorophyll values, depths or
fish species under any circumstances.

============================================================
NORMALIZED OUTPUT
============================================================

Available (real zone coordinates were retrieved from INCOIS):

    {
        "available": True,
        "source": "INCOIS PFZ Advisory",
        "sector": "MAHARASHTRA",
        "advisory_date": "2026-09-19",     # only if INCOIS published it
        "valid_until":   "2026-09-20",     # only if INCOIS published it
        "source_url": "...",
        "zones": [ {"latitude": 19.1, "longitude": 71.3}, ... ],
    }

Unavailable (the expected result today - see below):

    {
        "available": False,
        "source": "INCOIS PFZ Advisory",
        "sector": "MAHARASHTRA",
        "reason": "No current advisory available",
        "message": "No current PFZ advisory available for this region/date.",
        "detail": "<why, in plain language>",
        "advisory_date": "...",            # only if INCOIS published it
        "valid_until": "...",              # only if INCOIS published it
        "source_url": "...",
    }

Zone objects contain ONLY fields present in the source. Today that
is latitude/longitude. Depth / distance / direction / landing centre
are NOT extracted yet (see _parse_zones) - they will be added only
after a real INCOIS response has been captured and its layout
verified.

============================================================
HONEST LIMITATION OF THIS INTEGRATION
============================================================

Verified by fetching the live page (September 2026):

    https://incois.gov.in/MarineFisheries/TextDataHome?mfid=1&request_locale=en

The static HTML of that page contains the sector drop-down
(GUJARAT, MAHARASHTRA, GOA, KARNATAKA, KERALA, SOUTH TAMILNADU,
NORTH TAMILNADU, SOUTH ANDHRA PRADESH, NORTH ANDHRA PRADESH,
ODISHA, WEST BENGAL, ANDAMAN, NICOBAR, LAKSHADWEEP) and the
"Forecast Date / Valid upto" window - but NO zone coordinates.
The per-sector text is loaded client-side after a sector is
selected. The old approach (regex the landing page for
coordinates) therefore always returned zero points.

A separate INCOIS GeoPortal (incois.gov.in/geoportal/MFASPFZ) is
backed by a GeoServer, but the PFZ layer name/endpoint could not be
confirmed, and INCOIS's PfzWebGis page disallows automated access
in robots.txt. Nothing here guesses at those endpoints.

STATUS (September 2026): NOT INTEGRATED. The real INCOIS request behind
the sector selector has NOT been identified (see PFZ_ENDPOINT_CAPTURE.md).
Until it is configured, every call returns the "unavailable" shape.

What this module does today:

  1. Reads the real advisory window (forecast date / valid upto)
     from the landing page, when it can.
  2. Retrieves zone coordinates ONLY from a sector request that you
     configure after capturing it in Chrome DevTools -> Network:

         INCOIS_PFZ_SECTOR_URL      request URL; may contain {sector}
                                    (url-encoded sector name) and/or
                                    {sector_id}
         INCOIS_PFZ_SECTOR_METHOD   GET (default) or POST
         INCOIS_PFZ_SECTOR_BODY     form body for POST, same placeholders,
                                    e.g. "sectorId={sector_id}"
         INCOIS_PFZ_SECTOR_IDS      JSON map sector name -> id, e.g.
                                    {"MAHARASHTRA": "2", ...}
         INCOIS_PFZ_SECTOR_HEADERS  JSON map of extra request headers

     With no URL configured, PFZ is reported as unavailable. That is
     the normal, honest outcome - never papered over with invented
     data.
  3. Parses the response with `_parse_zones()`, which ONLY accepts a
     record that carries labelled "Latitude" and "Longitude" values
     (degree-minute-second such as "16 55 54", or labelled decimal
     degrees) inside the Indian EEZ bounds. Nothing else on the page
     is ever treated as a coordinate. The label layout follows an
     INCOIS PFZ record republished by MSSRF's Fisher Friend portal
     (2018); the CURRENT INCOIS response format is unverified, so
     adapt `_parse_zones()` to a real captured sample.
"""

import copy
import json
import logging
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


SOURCE_NAME = "INCOIS PFZ Advisory"

UNAVAILABLE_MESSAGE = (
    "No current PFZ advisory available for this region/date."
)

TEXT_DATA_URL = "https://incois.gov.in/MarineFisheries/TextDataHome"

LANDING_URL = f"{TEXT_DATA_URL}?mfid=1&request_locale=en"

# Optional, explicitly configured sector endpoint. Must contain {sector}.
SECTOR_URL_ENV = "INCOIS_PFZ_SECTOR_URL"
SECTOR_METHOD_ENV = "INCOIS_PFZ_SECTOR_METHOD"
SECTOR_BODY_ENV = "INCOIS_PFZ_SECTOR_BODY"
SECTOR_IDS_ENV = "INCOIS_PFZ_SECTOR_IDS"
SECTOR_HEADERS_ENV = "INCOIS_PFZ_SECTOR_HEADERS"


# ============================================================
# STATE -> INCOIS SECTOR MAPPING
# ============================================================
#
# Sector names match the drop-down on the live INCOIS page.
# Tamil Nadu and Andhra Pradesh are split into North/South
# sectors, so those are resolved per city.
# ============================================================

SECTOR_BY_STATE = {
    "Gujarat": "GUJARAT",
    "Maharashtra": "MAHARASHTRA",
    "Goa": "GOA",
    "Karnataka": "KARNATAKA",
    "Kerala": "KERALA",
    "Odisha": "ODISHA",
    "West Bengal": "WEST BENGAL",
}

SECTOR_BY_CITY_OVERRIDE = {
    "Chennai": "NORTH TAMILNADU",
    "Kanyakumari": "SOUTH TAMILNADU",
    "Visakhapatnam": "NORTH ANDHRA PRADESH",
}


# ============================================================
# SMALL IN-PROCESS CACHE
# ============================================================
#
# /api/ask and /api/map-data both need the PFZ result for the same
# city/date. Caching by (sector, forecast_date) means the second
# call does not hit INCOIS again. Failures are cached briefly so a
# dashboard reload does not hammer an unreachable server.
# ============================================================

_CACHE: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()

TTL_AVAILABLE_SECONDS = 30 * 60
TTL_UNAVAILABLE_SECONDS = 5 * 60


def _cache_get(key):

    with _CACHE_LOCK:

        entry = _CACHE.get(key)

        if not entry:
            return None

        expires_at, value = entry

        if expires_at < time.time():
            del _CACHE[key]
            return None

        return copy.deepcopy(value)


def _cache_put(key, value, ttl):

    with _CACHE_LOCK:
        _CACHE[key] = (time.time() + ttl, copy.deepcopy(value))


def clear_cache():
    """Used by tests."""

    with _CACHE_LOCK:
        _CACHE.clear()


# ============================================================
# PARSING
# ============================================================

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+(\d{4})\b",
    re.IGNORECASE,
)


def _get_sector(city_name: str, state: str) -> str:
    """
    Resolve the INCOIS sector name for a city/state.
    """

    if city_name in SECTOR_BY_CITY_OVERRIDE:
        return SECTOR_BY_CITY_OVERRIDE[city_name]

    return SECTOR_BY_STATE.get(state, (state or "").upper())


def _parse_advisory_window(page_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Read INCOIS's published "Forecast Date / Valid upto" window from
    the landing page, e.g. "19 SEP 2026  20 SEP 2026".

    Returns (advisory_date, valid_until) as ISO dates, or
    (None, None) if the page does not contain them in that form.
    Never guesses.
    """

    if not page_text:
        return None, None

    plain = re.sub(r"<[^>]+>", " ", page_text)
    plain = re.sub(r"\s+", " ", plain)

    index = plain.lower().find("forecast date")

    if index < 0:
        return None, None

    found = _DATE_PATTERN.findall(plain[index:index + 300])

    if len(found) < 2:
        return None, None

    def to_iso(parts):

        day, month, year = parts

        return date(
            int(year),
            _MONTHS[month[:3].upper()],
            int(day),
        ).isoformat()

    try:
        return to_iso(found[0]), to_iso(found[1])

    except (ValueError, KeyError):
        return None, None


_DMS = re.compile(
    r"^\W{0,12}?(\d{1,3})\s*(?:\u00b0|:|\s)\s*(\d{1,2})\s*(?:['\u2032\u2019:]|\s)\s*"
    r"(\d{1,2}(?:\.\d+)?)(?![\d.])"
)
_DECIMAL = re.compile(r"^\W{0,12}?(\d{1,3}\.\d+)(?!\d)")


def _read_coordinate(text: str) -> Optional[float]:
    """
    Read one coordinate that immediately follows a "Latitude" or
    "Longitude" label: degree-minute-second ("16 55 54") or decimal
    degrees ("16.93"). Returns None if it is neither.
    """

    match = _DMS.match(text)

    if match:

        degrees = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))

        if minutes >= 60 or seconds >= 60:
            return None

        return degrees + minutes / 60 + seconds / 3600

    match = _DECIMAL.match(text)

    if match:
        return float(match.group(1))

    return None


def _plain_text(payload_text: str) -> str:

    text = re.sub(r"<[^>]+>", " ", payload_text)
    text = text.replace("&nbsp;", " ").replace("&#176;", "\u00b0")

    return re.sub(r"\s+", " ", text)


def _parse_zones(payload_text: str) -> List[Dict[str, Any]]:
    """
    Extract real PFZ zones from a sector payload.

    A zone is created ONLY from a record that has a labelled
    "Latitude" AND a labelled "Longitude" that both parse as valid
    coordinates inside the Indian EEZ bounds. An unlabelled number, a
    phone number, an office address or an out-of-range value never
    becomes a zone. Returns [] if nothing qualifies - it must NEVER
    invent a point.

    Only latitude/longitude are extracted. Depth, distance, direction,
    bearing and landing centre appear in INCOIS text records, but
    their position relative to the coordinates (before or after) is
    not verified for the current INCOIS response, and attaching a
    neighbouring record's value to the wrong zone would be a silent
    invention. Extend this once a real sample has been captured.
    """

    if not payload_text:
        return []

    text = _plain_text(payload_text)

    starts = [m.start() for m in re.finditer(r"latitude", text, re.I)]

    zones = []
    seen = set()

    for index, start in enumerate(starts):

        end = starts[index + 1] if index + 1 < len(starts) else start + 700

        record = text[start:min(end, start + 700)]

        lat_match = re.match(r"latitude\W{0,3}", record, re.I)
        lon_match = re.search(r"longitude\W{0,3}", record, re.I)

        if not lat_match or not lon_match:
            continue

        latitude = _read_coordinate(record[lat_match.end():])
        longitude = _read_coordinate(record[lon_match.end():])

        if latitude is None or longitude is None:
            continue

        # Sanity bounds: Indian EEZ roughly 5N-25N, 60E-95E.
        if not (5.0 <= latitude <= 25.0):
            continue

        if not (60.0 <= longitude <= 95.0):
            continue

        key = (round(latitude, 4), round(longitude, 4))

        if key in seen:
            continue

        seen.add(key)

        zones.append(
            {
                "latitude": round(latitude, 5),
                "longitude": round(longitude, 5),
            }
        )

    return zones


# ============================================================
# HTTP
# ============================================================

def _http_get_text(
    url: str,
    timeout: int,
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
) -> str:
    """GET (data=None) or form POST (data=bytes) and return the body text."""

    request_headers = {"User-Agent": "OceviaOceanMind/1.0"}

    if headers:
        request_headers.update(headers)

    if data is not None:
        request_headers.setdefault(
            "Content-Type", "application/x-www-form-urlencoded"
        )

    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def _env_json(name: str) -> Dict[str, Any]:

    raw = os.environ.get(name, "").strip()

    if not raw:
        return {}

    try:
        value = json.loads(raw)

    except ValueError:
        logger.warning(f"{name} is not valid JSON; ignored.")
        return {}

    return value if isinstance(value, dict) else {}


def _build_sector_request(sector: str):
    """
    Build (url, data, headers) for the configured sector request, or
    None if it cannot be built (not configured, or a needed sector id
    is missing). Nothing is guessed.
    """

    template = os.environ.get(SECTOR_URL_ENV, "").strip()

    if not template:
        return None

    body_template = os.environ.get(SECTOR_BODY_ENV, "")

    method = os.environ.get(SECTOR_METHOD_ENV, "GET").strip().upper()

    sector_id = str(_env_json(SECTOR_IDS_ENV).get(sector, ""))

    combined = template + body_template

    if "{sector_id}" in combined and not sector_id:
        return None

    if "{sector}" not in combined and "{sector_id}" not in combined:
        return None

    def fill(text: str) -> str:
        return (
            text
            .replace("{sector}", urllib.parse.quote(sector))
            .replace("{sector_id}", urllib.parse.quote(sector_id))
        )

    data = fill(body_template).encode("utf-8") if method == "POST" else None

    headers = {
        str(k): str(v) for k, v in _env_json(SECTOR_HEADERS_ENV).items()
    }

    return fill(template), data, headers


# ============================================================
# RESULT BUILDERS
# ============================================================

def _unavailable(
    sector: str,
    detail: str,
    advisory_date: Optional[str] = None,
    valid_until: Optional[str] = None,
    reason: str = "No current advisory available",
) -> Dict[str, Any]:

    result = {
        "available": False,
        "source": SOURCE_NAME,
        "sector": sector,
        "reason": reason,
        "message": UNAVAILABLE_MESSAGE,
        "detail": detail,
        "source_url": LANDING_URL,
    }

    if advisory_date:
        result["advisory_date"] = advisory_date

    if valid_until:
        result["valid_until"] = valid_until

    return result


def _covers(advisory_date, valid_until, forecast_date) -> bool:
    """
    True if forecast_date lies inside INCOIS's published window.
    If the window is unknown we cannot say it does NOT cover the
    date, so unknown is treated as covered (the zones themselves are
    still real INCOIS data).
    """

    if not (advisory_date and valid_until and forecast_date):
        return True

    return advisory_date <= forecast_date <= valid_until


def _fetch_advisory(
    sector: str,
    forecast_date: str,
    timeout: int,
) -> Dict[str, Any]:

    # --------------------------------------------------------
    # 1. Landing page: real advisory window (dates only)
    # --------------------------------------------------------

    try:

        landing_text = _http_get_text(LANDING_URL, timeout)

    except Exception as exc:

        logger.warning(f"INCOIS landing page fetch failed: {exc}")

        return _unavailable(
            sector,
            "The INCOIS advisory site could not be reached.",
        )

    advisory_date, valid_until = _parse_advisory_window(landing_text)

    # --------------------------------------------------------
    # 2. Zone coordinates: only from an explicitly configured
    #    sector endpoint.
    # --------------------------------------------------------

    sector_request = _build_sector_request(sector)

    if sector_request is None:

        detail = (
            "INCOIS loads the per-sector PFZ coordinates through a "
            "client-side request, and no machine-readable sector "
            "request is configured for this system."
        )

        if advisory_date and valid_until:
            detail += (
                f" INCOIS lists an advisory dated {advisory_date} "
                f"(valid until {valid_until}) on its site."
            )

        return _unavailable(
            sector,
            detail,
            advisory_date,
            valid_until,
        )

    sector_url, sector_data, sector_headers = sector_request

    try:

        if sector_data is None and not sector_headers:
            payload = _http_get_text(sector_url, timeout)

        else:
            payload = _http_get_text(
                sector_url,
                timeout,
                data=sector_data,
                headers=sector_headers,
            )

    except Exception as exc:

        logger.warning(f"INCOIS sector fetch failed for {sector}: {exc}")

        return _unavailable(
            sector,
            "The INCOIS sector endpoint could not be reached.",
            advisory_date,
            valid_until,
        )

    zones = _parse_zones(payload)

    if not zones:

        return _unavailable(
            sector,
            "The INCOIS sector response contained no readable coordinates.",
            advisory_date,
            valid_until,
        )

    if not _covers(advisory_date, valid_until, forecast_date):

        return _unavailable(
            sector,
            (
                f"The latest INCOIS advisory is valid {advisory_date} to "
                f"{valid_until}, which does not include {forecast_date}."
            ),
            advisory_date,
            valid_until,
            reason="Advisory does not cover the requested date",
        )

    result = {
        "available": True,
        "source": SOURCE_NAME,
        "sector": sector,
        "source_url": sector_url,
        "zones": zones,
    }

    if advisory_date:
        result["advisory_date"] = advisory_date

    if valid_until:
        result["valid_until"] = valid_until

    return result


# ============================================================
# PUBLIC API
# ============================================================

def get_pfz_advisory(
    city_name: str,
    state: str,
    forecast_date: str,
    timeout: int = 10,
) -> Dict[str, Any]:
    """
    Fetch the official INCOIS PFZ advisory for a city's sector.

    Always returns the normalized dict documented at the top of
    this file. Results (including "unavailable") are cached briefly
    per (sector, forecast_date) so /api/ask and /api/map-data do not
    each hit INCOIS.
    """

    sector = _get_sector(city_name, state)

    key = (sector, str(forecast_date))

    cached = _cache_get(key)

    if cached is not None:
        return cached

    result = _fetch_advisory(sector, str(forecast_date), timeout)

    _cache_put(
        key,
        result,
        TTL_AVAILABLE_SECONDS
        if result.get("available")
        else TTL_UNAVAILABLE_SECONDS,
    )

    return result


if __name__ == "__main__":

    import json

    print(
        json.dumps(
            get_pfz_advisory(
                city_name="Mumbai",
                state="Maharashtra",
                forecast_date="2026-09-21",
            ),
            indent=2,
        )
    )
