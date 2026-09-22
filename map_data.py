import copy
import math
import threading
import time

import requests

from pfz import get_pfz_advisory


WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"


# ============================================================
# REGIONAL MAP WINDOWS
# ============================================================

# ============================================================
# REGIONAL OCEAN DOMAINS
# ============================================================
#
# One domain per seeded city, chosen so the window is mostly the
# SEA the city's fleet actually works in, not a box centred on land.
# Each is ~7 degrees square (about 750 km), which at the grid step
# below is a few hundred real Open-Meteo points - a useful regional
# map, not the whole Indian Ocean and not thousands of requests.
#
# These are map/query windows only. They never create data: every
# value still comes from a real Open-Meteo response for a real
# coordinate inside the window.
# ============================================================

REGIONS = {
    # Northern / central Arabian Sea, Maharashtra coast.
    "Mumbai": {
        "min_lat": 15.0,
        "max_lat": 22.5,
        "min_lon": 66.0,
        "max_lon": 73.5,
    },

    # Northern Arabian Sea, Gujarat / Saurashtra coast.
    "Veraval": {
        "min_lat": 17.0,
        "max_lat": 24.0,
        "min_lon": 64.5,
        "max_lon": 72.0,
    },

    # Central Arabian Sea, Goa / Konkan coast.
    "Panaji": {
        "min_lat": 12.0,
        "max_lat": 19.0,
        "min_lon": 67.5,
        "max_lon": 74.5,
    },

    # South-eastern Arabian Sea, Karnataka coast.
    "Mangaluru": {
        "min_lat": 9.5,
        "max_lat": 16.5,
        "min_lon": 68.5,
        "max_lon": 75.5,
    },

    # South-eastern Arabian Sea, Kerala / Lakshadweep-facing waters.
    "Kochi": {
        "min_lat": 6.0,
        "max_lat": 13.5,
        "min_lon": 70.0,
        "max_lon": 77.0,
    },

    # Gulf of Mannar / Comorin, where the Arabian Sea meets the
    # Bay of Bengal.
    "Kanyakumari": {
        "min_lat": 4.0,
        "max_lat": 11.0,
        "min_lon": 73.0,
        "max_lon": 80.0,
    },

    # Western Bay of Bengal, Tamil Nadu coast.
    "Chennai": {
        "min_lat": 9.0,
        "max_lat": 16.0,
        "min_lon": 78.5,
        "max_lon": 85.5,
    },

    # Central-western Bay of Bengal, Andhra coast.
    "Visakhapatnam": {
        "min_lat": 13.0,
        "max_lat": 20.0,
        "min_lon": 81.0,
        "max_lon": 88.0,
    },

    # Northern Bay of Bengal, Odisha coast.
    "Puri": {
        "min_lat": 15.5,
        "max_lat": 22.0,
        "min_lon": 83.0,
        "max_lon": 90.0,
    },

    # Head of the Bay of Bengal, West Bengal coast.
    "Digha": {
        "min_lat": 17.0,
        "max_lat": 22.5,
        "min_lon": 85.5,
        "max_lon": 92.5,
    },
}


def _select_region(city_name, center_latitude, center_longitude):
    """
    Choose the map window for a city.

    ROOT CAUSE OF THE WRONG-REGION BUG:
    the old code looped over REGIONS and took the FIRST rectangle
    that contained the city's coordinate. The rectangles overlap, so
    Mangaluru and Kanyakumari matched the Kochi rectangle, Panaji and
    Veraval matched Mumbai's, and Digha matched Puri's - five of the
    ten seeded cities got another city's window.

    Now the requested city name selects its own region directly.
    Coordinates are only a fallback for a city that has no entry in
    REGIONS (none of the ten seeded cities do), and even then the
    containing region with the NEAREST centre is used, never simply
    the first one.

    Returns (region_dict, source) where source is "city",
    "coordinates" or "default_window".
    """

    if city_name:

        wanted = str(city_name).strip().lower()

        for name, region in REGIONS.items():

            if name.lower() == wanted:
                return region, "city"

    best = None
    best_distance = None

    for region in REGIONS.values():

        if not (
            region["min_lat"] <= center_latitude <= region["max_lat"]
            and region["min_lon"] <= center_longitude <= region["max_lon"]
        ):
            continue

        mid_lat = (region["min_lat"] + region["max_lat"]) / 2
        mid_lon = (region["min_lon"] + region["max_lon"]) / 2

        distance = (
            (center_latitude - mid_lat) ** 2
            + (center_longitude - mid_lon) ** 2
        )

        if best is None or distance < best_distance:
            best = region
            best_distance = distance

    if best is not None:
        return best, "coordinates"

    return (
        {
            "min_lat": center_latitude - 4.5,
            "max_lat": center_latitude + 4.5,
            "min_lon": center_longitude - 4.5,
            "max_lon": center_longitude + 4.5,
        },
        "default_window",
    )


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value):
    try:
        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


MAX_GRID_POINTS = 260

# Open-Meteo accepts many coordinates in one call, but the request is a
# GET, so the coordinate list has to stay inside a sane URL length.
COORDS_PER_REQUEST = 100


def _grid_step_for(region, max_points=MAX_GRID_POINTS):
    """
    Pick the finest grid step from a fixed ladder that still keeps the
    region under `max_points` requested coordinates. Coarser steps are
    only ever a REQUEST-count decision - they never change a value.
    """

    lat_span = region["max_lat"] - region["min_lat"]
    lon_span = region["max_lon"] - region["min_lon"]

    for step in (0.25, 0.5, 0.75, 1.0):

        rows = int(lat_span / step) + 1
        columns = int(lon_span / step) + 1

        if rows * columns <= max_points:
            return step

    return 1.0


def _chunks(items, size):

    for start in range(0, len(items), size):
        yield items[start:start + size]


def _build_grid(region, step=0.5):
    """
    Create a regional latitude/longitude grid.
    """

    latitudes = []
    longitudes = []

    current = region["min_lat"]

    while current <= region["max_lat"] + 0.0001:
        latitudes.append(round(current, 2))
        current += step

    current = region["min_lon"]

    while current <= region["max_lon"] + 0.0001:
        longitudes.append(round(current, 2))
        current += step

    coordinates = []

    for latitude in latitudes:
        for longitude in longitudes:
            coordinates.append(
                {
                    "latitude": latitude,
                    "longitude": longitude,
                }
            )

    return coordinates


def _build_target_time(forecast_date, forecast_time):
    """
    Convert date + time into Open-Meteo hourly format.
    """

    if not forecast_time:
        forecast_time = "12:00"

    return f"{forecast_date}T{forecast_time}"


def _extract_hourly_value(hourly, variable, target_time):
    """
    Extract one hourly variable value.
    """

    if not hourly:
        return None

    times = hourly.get("time", [])
    values = hourly.get(variable, [])

    if not times or not values:
        return None

    for index, time_value in enumerate(times):

        if time_value == target_time:

            if index < len(values):
                return _safe_float(values[index])

            return None

    return None


# ============================================================
# MARINE DATA
# ============================================================

def _fetch_marine_grid(
    coordinates,
    forecast_date,
    forecast_time,
):
    """
    Fetch marine forecast data for the regional grid.

    The Marine API is requested with cell_selection=sea so
    the API prefers marine/sea grid cells.
    """

    if not coordinates:
        return []

    marine_points = []

    # Open-Meteo snaps each requested coordinate to a model cell, so
    # several neighbouring requests (especially near the coast) can
    # come back as the SAME cell. Keep each real cell once.
    seen_cells = set()

    for batch in _chunks(coordinates, COORDS_PER_REQUEST):
        _fetch_marine_batch(
            batch,
            forecast_date,
            forecast_time,
            marine_points,
            seen_cells,
        )

    return marine_points


def _fetch_marine_batch(
    coordinates,
    forecast_date,
    forecast_time,
    marine_points,
    seen_cells,
):
    """
    One Marine API request for up to COORDS_PER_REQUEST coordinates.
    Appends the real points it returns to `marine_points`.
    """

    latitudes = ",".join(
        str(point["latitude"])
        for point in coordinates
    )

    longitudes = ",".join(
        str(point["longitude"])
        for point in coordinates
    )

    params = {
        "latitude": latitudes,
        "longitude": longitudes,

        "hourly": ",".join(
            [
                "wave_height",
                "wave_direction",
                "sea_surface_temperature",
            ]
        ),

        "start_date": forecast_date,
        "end_date": forecast_date,

        "timezone": "Asia/Kolkata",

        "cell_selection": "sea",
    }

    response = requests.get(
        MARINE_API_URL,
        params=params,
        timeout=45,
    )

    response.raise_for_status()

    data = response.json()

    # Open-Meteo returns a list when multiple locations
    # are requested.
    if isinstance(data, dict):
        data = [data]

    target_time = _build_target_time(
        forecast_date,
        forecast_time,
    )

    for item in data:

        latitude = _safe_float(
            item.get("latitude")
        )

        longitude = _safe_float(
            item.get("longitude")
        )

        if latitude is None or longitude is None:
            continue

        hourly = item.get(
            "hourly",
            {},
        )

        wave_height = _extract_hourly_value(
            hourly,
            "wave_height",
            target_time,
        )

        wave_direction = _extract_hourly_value(
            hourly,
            "wave_direction",
            target_time,
        )

        sea_surface_temperature = _extract_hourly_value(
            hourly,
            "sea_surface_temperature",
            target_time,
        )

        # wave_height is our basic marine-data check.
        if wave_height is None:
            continue

        cell = (round(latitude, 2), round(longitude, 2))

        if cell in seen_cells:
            continue

        seen_cells.add(cell)

        marine_points.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "wave_height": wave_height,
                "wave_direction": wave_direction,
                "sea_surface_temperature":
                    sea_surface_temperature,
            }
        )


# ============================================================
# WEATHER DATA
# ============================================================

def _fetch_weather_for_marine_points(
    marine_points,
    forecast_date,
    forecast_time,
):
    """
    Fetch wind data using the same ordered list of
    marine coordinates.

    IMPORTANT:
    We do NOT compare the coordinates returned by the
    Weather API with the Marine API coordinates.

    Both APIs can snap coordinates to different model
    grid cells.

    Instead, we preserve the original marine coordinate
    by index.
    """

    if not marine_points:
        return []

    weather_points = []

    for batch in _chunks(marine_points, COORDS_PER_REQUEST):
        _fetch_weather_batch(
            batch,
            forecast_date,
            forecast_time,
            weather_points,
        )

    return weather_points


def _fetch_weather_batch(
    marine_points,
    forecast_date,
    forecast_time,
    weather_points,
):
    """
    One Forecast API request for up to COORDS_PER_REQUEST of the
    marine coordinates, appending wind at those coordinates.
    """

    latitudes = ",".join(
        str(point["latitude"])
        for point in marine_points
    )

    longitudes = ",".join(
        str(point["longitude"])
        for point in marine_points
    )

    params = {
        "latitude": latitudes,
        "longitude": longitudes,

        "hourly": ",".join(
            [
                "wind_speed_10m",
                "wind_direction_10m",
            ]
        ),

        "start_date": forecast_date,
        "end_date": forecast_date,

        "timezone": "Asia/Kolkata",

        "cell_selection": "sea",
    }

    response = requests.get(
        WEATHER_API_URL,
        params=params,
        timeout=45,
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict):
        data = [data]

    target_time = _build_target_time(
        forecast_date,
        forecast_time,
    )

    for index, item in enumerate(data):

        # ----------------------------------------------------
        # IMPORTANT
        #
        # Use the original marine coordinates.
        #
        # Do NOT use:
        #
        # item["latitude"]
        # item["longitude"]
        #
        # because the Forecast API may snap the location
        # to a different model grid.
        # ----------------------------------------------------

        if index >= len(marine_points):
            continue

        latitude = marine_points[index][
            "latitude"
        ]

        longitude = marine_points[index][
            "longitude"
        ]

        hourly = item.get(
            "hourly",
            {},
        )

        wind_speed = _extract_hourly_value(
            hourly,
            "wind_speed_10m",
            target_time,
        )

        wind_direction = _extract_hourly_value(
            hourly,
            "wind_direction_10m",
            target_time,
        )

        if (
            wind_speed is None
            or wind_direction is None
        ):
            continue

        weather_points.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "wind_speed": wind_speed,
                "wind_direction": wind_direction,
            }
        )


# ============================================================
# MERGE
# ============================================================

def _merge_points(
    marine_points,
    weather_points,
):
    """
    Merge marine and wind data using coordinate identity
    already preserved from the marine list.

    No coordinate matching is performed here.
    """

    weather_by_index = {}

    for index, point in enumerate(
        weather_points
    ):
        weather_by_index[index] = point

    merged = []

    # Since the weather list only contains successful
    # weather points, coordinate matching by index is not
    # completely safe if some earlier weather point was
    # missing.

    # Therefore, build a coordinate lookup from the
    # original marine coordinate attached to each weather
    # point.

    weather_lookup = {}

    for point in weather_points:

        key = (
            round(point["latitude"], 2),
            round(point["longitude"], 2),
        )

        weather_lookup[key] = point

    for marine in marine_points:

        key = (
            round(marine["latitude"], 2),
            round(marine["longitude"], 2),
        )

        weather = weather_lookup.get(key)

        if weather is None:
            continue

        merged.append(
            {
                "latitude":
                    marine["latitude"],

                "longitude":
                    marine["longitude"],

                "wind_speed":
                    weather["wind_speed"],

                "wind_direction":
                    weather["wind_direction"],

                "wave_height":
                    marine["wave_height"],

                "wave_direction":
                    marine["wave_direction"],

                "sea_surface_temperature":
                    marine[
                        "sea_surface_temperature"
                    ],
            }
        )

    return merged


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def _build_map_data(
    center_latitude,
    center_longitude,
    forecast_date,
    forecast_time="12:00",
    city_name=None,
    state=None,
):
    """
    Return regional marine wind/wave/SST data, plus the official
    INCOIS PFZ advisory for the city's sector when available.
    """

    try:

        # ----------------------------------------------------
        # Select the map window BY CITY NAME (see _select_region).
        # ----------------------------------------------------

        selected_region, region_source = _select_region(
            city_name,
            center_latitude,
            center_longitude,
        )

        # ----------------------------------------------------
        # Build regional grid.
        # ----------------------------------------------------

        grid_step = _grid_step_for(selected_region)

        requested_grid = _build_grid(
            selected_region,
            step=grid_step,
        )

        # ----------------------------------------------------
        # STEP 1:
        # Get actual marine points first.
        # ----------------------------------------------------

        marine_points = _fetch_marine_grid(
            requested_grid,
            forecast_date,
            forecast_time,
        )

        if not marine_points:

            return {
                "status": "error",
                "message":
                    "No marine forecast points were returned.",
            }

        # ----------------------------------------------------
        # STEP 2:
        # Fetch wind at those marine locations.
        # ----------------------------------------------------

        weather_points = (
            _fetch_weather_for_marine_points(
                marine_points,
                forecast_date,
                forecast_time,
            )
        )

        if not weather_points:

            return {
                "status": "error",
                "message":
                    "No wind forecast points were returned "
                    "for the marine grid.",
            }

        # ----------------------------------------------------
        # STEP 3:
        # Merge.
        # ----------------------------------------------------

        points = _merge_points(
            marine_points,
            weather_points,
        )

        if not points:

            return {
                "status": "error",
                "message":
                    "No matching marine wind data was returned.",
            }

        # ----------------------------------------------------
        # Sort points for predictable output.
        # ----------------------------------------------------

        points.sort(
            key=lambda point: (
                point["latitude"],
                point["longitude"],
            )
        )

        # ------------------------------------------------
        # STEP 4:
        # Fetch the real INCOIS PFZ advisory for this city's
        # sector. This NEVER invents fishing-zone coordinates:
        # if INCOIS data cannot be retrieved or parsed, the
        # "pfz" block below is explicitly marked unavailable
        # rather than filled in with guesses.
        # ------------------------------------------------

        if city_name and state:

            pfz_result = get_pfz_advisory(
                city_name=city_name,
                state=state,
                forecast_date=forecast_date,
            )

        else:

            pfz_result = {
                "available": False,
                "source": "INCOIS PFZ Advisory",
                "reason": "No current advisory available",
                "message":
                    "No current PFZ advisory available for "
                    "this region/date.",
            }

        return {
            "status": "success",

            "date":
                forecast_date,

            "time":
                forecast_time,

            "points":
                points,

            "point_count":
                len(points),

            # Spacing of the coordinates we ASKED for. Open-Meteo then
            # snaps each to its own model cell, so this is the request
            # spacing, not a claim about model resolution.
            "grid_spacing_degrees":
                grid_step,

            "requested_point_count":
                len(requested_grid),

            "api_requests": (
                math.ceil(len(requested_grid) / COORDS_PER_REQUEST)
                + math.ceil(len(marine_points) / COORDS_PER_REQUEST)
            ),

            # The bounding box of the points that actually came back.
            # The map fits to this, so the viewport never shows a
            # small data patch floating in an empty ocean.
            "data_bounds": {
                "min_lat": min(p["latitude"] for p in points),
                "max_lat": max(p["latitude"] for p in points),
                "min_lon": min(p["longitude"] for p in points),
                "max_lon": max(p["longitude"] for p in points),
            },

            "pfz":
                pfz_result,

            "region_source":
                region_source,

            "region": {
                "min_lat":
                    selected_region["min_lat"],

                "max_lat":
                    selected_region["max_lat"],

                "min_lon":
                    selected_region["min_lon"],

                "max_lon":
                    selected_region["max_lon"],
            },

            "sources": {
                "marine":
                    "Open-Meteo Marine API",

                "weather":
                    "Open-Meteo Forecast API",
            },
        }

    except requests.RequestException as exc:

        return {
            "status": "error",
            "message":
                f"Open-Meteo request failed: {exc}",
        }

    except Exception as exc:

        return {
            "status": "error",
            "message":
                f"Map data processing failed: {exc}",
        }

# ============================================================
# CACHED PUBLIC ENTRY POINT
# ============================================================
#
# One map load asks Open-Meteo for a few hundred grid points from
# each of the Marine and Forecast APIs. Re-asking the same
# city / date / hour (page reload, layer toggle re-fetch, demo
# retries) is served from memory for a short time instead of
# spending more of the free API quota. Only successful results are
# cached; the PFZ block is refreshed from pfz.py's own (shorter)
# cache on every hit.
# ============================================================

_MAP_CACHE = {}
_MAP_CACHE_LOCK = threading.Lock()
MAP_CACHE_TTL_SECONDS = 30 * 60


def get_map_data(
    center_latitude,
    center_longitude,
    forecast_date,
    forecast_time="12:00",
    city_name=None,
    state=None,
):
    """
    Return regional marine wind/wave/SST data, plus the official
    INCOIS PFZ advisory for the city's sector when available.
    """

    key = (
        (city_name or "").strip().lower(),
        round(center_latitude, 4),
        round(center_longitude, 4),
        str(forecast_date),
        str(forecast_time),
    )

    with _MAP_CACHE_LOCK:

        entry = _MAP_CACHE.get(key)

        cached = (
            copy.deepcopy(entry[1])
            if entry and entry[0] > time.time()
            else None
        )

    if cached is not None:

        # The PFZ block has its own (shorter) cache in pfz.py.
        if city_name and state:

            cached["pfz"] = get_pfz_advisory(
                city_name=city_name,
                state=state,
                forecast_date=forecast_date,
            )

        return cached

    result = _build_map_data(
        center_latitude=center_latitude,
        center_longitude=center_longitude,
        forecast_date=forecast_date,
        forecast_time=forecast_time,
        city_name=city_name,
        state=state,
    )

    if isinstance(result, dict) and result.get("status") == "success":

        with _MAP_CACHE_LOCK:
            _MAP_CACHE[key] = (
                time.time() + MAP_CACHE_TTL_SECONDS,
                copy.deepcopy(result),
            )

    return result


def clear_cache():
    """Used by tests."""

    with _MAP_CACHE_LOCK:
        _MAP_CACHE.clear()
