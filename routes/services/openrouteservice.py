"""
OpenRouteService Integration Module

This module handles all interactions with the OpenRouteService API:
1. Geocoding: Convert location names to coordinates
2. Routing: Calculate driving routes between two points
3. Geometry Processing: Encode/decode polylines, simplify GeoJSON
4. State Management: Build state corridors for USA routes

OpenRouteService API Docs: https://openrouteservice.org/dev/#/api-docs

Key Optimizations:
- Single routing API call per request (minimize API usage)
- Polyline encoding for compact coordinate storage
- Ramer-Douglas-Peucker algorithm for geometry simplification
- BFS algorithm for state-to-state path finding
"""

import requests
from django.conf import settings

# OpenRouteService API base URL
ORS_BASE_URL = "https://api.openrouteservice.org"

# USA bounding boxes for location validation
# Format: (min_lon, min_lat, max_lon, max_lat)
US_BBOXES = [
    (-124.848974, 24.396308, -66.885444, 49.384358),  # Contiguous US (lower 48)
    (-170.0, 51.0, -130.0, 71.0),  # Alaska
    (-161.0, 18.5, -154.0, 22.5),  # Hawaii
]

# Full state name to 2-letter abbreviation mapping
US_STATE_ABBREV = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC",
}

# Reverse mapping: 2-letter code → full state name
US_STATE_FULL_NAME = {abbr: name for name, abbr in US_STATE_ABBREV.items()}

# State adjacency graph for BFS pathfinding
# Used by build_state_corridor() to find shortest state-to-state path
US_STATE_NEIGHBORS = {
    "AL": ["FL", "GA", "TN", "MS"],
    "AK": [],
    "AZ": ["CA", "NV", "UT", "NM", "CO"],
    "AR": ["TX", "OK", "MO", "TN", "MS", "LA"],
    "CA": ["OR", "NV", "AZ"],
    "CO": ["WY", "NE", "KS", "OK", "NM", "AZ", "UT"],
    "CT": ["NY", "MA", "RI"],
    "DE": ["MD", "PA", "NJ"],
    "FL": ["AL", "GA"],
    "GA": ["FL", "AL", "TN", "NC", "SC"],
    "HI": [],
    "ID": ["WA", "OR", "NV", "UT", "WY", "MT"],
    "IL": ["WI", "IA", "MO", "KY", "IN", "MI"],
    "IN": ["MI", "OH", "KY", "IL"],
    "IA": ["MN", "SD", "NE", "MO", "IL", "WI"],
    "KS": ["NE", "CO", "OK", "MO"],
    "KY": ["IL", "IN", "OH", "WV", "VA", "TN", "MO"],
    "LA": ["TX", "AR", "MS"],
    "ME": ["NH"],
    "MD": ["VA", "WV", "PA", "DE", "DC"],
    "MA": ["NY", "VT", "NH", "RI", "CT"],
    "MI": ["WI", "IN", "OH"],
    "MN": ["ND", "SD", "IA", "WI"],
    "MS": ["LA", "AR", "TN", "AL"],
    "MO": ["IA", "IL", "KY", "TN", "AR", "OK", "KS", "NE"],
    "MT": ["ID", "WY", "SD", "ND"],
    "NE": ["SD", "IA", "MO", "KS", "CO", "WY"],
    "NV": ["OR", "ID", "UT", "AZ", "CA"],
    "NH": ["VT", "ME", "MA"],
    "NJ": ["NY", "PA", "DE"],
    "NM": ["AZ", "UT", "CO", "OK", "TX"],
    "NY": ["PA", "NJ", "CT", "MA", "VT"],
    "NC": ["VA", "TN", "GA", "SC"],
    "ND": ["MT", "SD", "MN"],
    "OH": ["PA", "WV", "KY", "IN", "MI"],
    "OK": ["KS", "CO", "NM", "TX", "AR", "MO"],
    "OR": ["WA", "ID", "NV", "CA"],
    "PA": ["NY", "NJ", "DE", "MD", "WV", "OH"],
    "RI": ["MA", "CT"],
    "SC": ["NC", "GA"],
    "SD": ["ND", "MT", "WY", "NE", "IA", "MN"],
    "TN": ["KY", "VA", "NC", "GA", "AL", "MS", "AR", "MO"],
    "TX": ["NM", "OK", "AR", "LA"],
    "UT": ["ID", "WY", "CO", "NM", "AZ", "NV"],
    "VT": ["NY", "NH", "MA"],
    "VA": ["MD", "DC", "WV", "KY", "TN", "NC"],
    "WA": ["ID", "OR"],
    "WV": ["OH", "PA", "MD", "VA", "KY"],
    "WI": ["MN", "IA", "IL", "MI"],
    "WY": ["MT", "SD", "NE", "CO", "UT", "ID"],
    "DC": ["MD", "VA"],
}


def normalize_state_code(value: str | None) -> str | None:
    """
    Convert state name or code to 2-letter abbreviation.
    
    Examples:
        "New York" → "NY"
        "NY" → "NY"
        "new york" → "NY"
    """
    if not value:
        return None

    value = value.strip().upper()
    if len(value) == 2:
        return value

    return US_STATE_ABBREV.get(value)


def state_code_to_full_name(state_code: str | None) -> str | None:
    """
    Convert 2-letter state code to full name.
    
    Example:
        "NY" → "NEW YORK"
    """
    if not state_code:
        return None

    return US_STATE_FULL_NAME.get(state_code.upper())


def build_state_corridor(start_state: str | None, end_state: str | None) -> list[str]:
    """
    Build shortest path through US states using BFS (Breadth-First Search).
    
    Uses US_STATE_NEIGHBORS adjacency graph to find path.
    
    Examples:
        build_state_corridor("NY", "CA") → ["NY", "PA", "OH", "IN", "IL", ...]
        build_state_corridor("NY", "NJ") → ["NY", "NJ"]
        build_state_corridor("NY", "NY") → ["NY"]
    
    Algorithm:
        1. Start at start_state
        2. Explore all neighboring states (breadth-first)
        3. Track parent pointers to reconstruct path
        4. Return shortest path from start to end
    """
    start_state = normalize_state_code(start_state)
    end_state = normalize_state_code(end_state)

    # Edge cases
    if not start_state and not end_state:
        return []
    if start_state == end_state:
        return [start_state]
    if not start_state or not end_state:
        return [state for state in [start_state, end_state] if state]

    # BFS algorithm
    queue = [start_state]
    parents = {start_state: None}

    while queue:
        current = queue.pop(0)
        if current == end_state:
            break
        for neighbor in US_STATE_NEIGHBORS.get(current, []):
            if neighbor not in parents:
                parents[neighbor] = current
                queue.append(neighbor)

    # No path found (shouldn't happen with complete US graph)
    if end_state not in parents:
        return [start_state, end_state]

    # Reconstruct path from end to start using parent pointers
    path = []
    node = end_state
    while node is not None:
        path.append(node)
        node = parents.get(node)

    return list(reversed(path))


def is_within_us_bbox(coords: list) -> bool:
    """
    Check if coordinates fall within USA bounding boxes.
    
    Covers contiguous US, Alaska, and Hawaii.
    
    Args:
        coords: [longitude, latitude]
    
    Returns:
        True if coords are in USA, False otherwise
    """
    if not coords or len(coords) != 2:
        return False

    lon, lat = coords
    for min_lon, min_lat, max_lon, max_lat in US_BBOXES:
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            return True

    return False


def geocode_place(place_name: str, enforce_us: bool = False) -> dict:
    """
    Convert text location to coordinates using OpenRouteService Geocoding API.
    
    Examples:
        "New York, NY" → {"coords": [-74.006, 40.7128], "country_code": "US", "state": "NY"}
        "Los Angeles" → {"coords": [-118.2437, 34.0522], "country_code": "US", "state": "CA"}
    
    Args:
        place_name: Text description of location
        enforce_us: If True, restricts search to USA only
    
    Returns:
        {
            "coords": [lon, lat],      # [longitude, latitude]
            "country_code": "US",       # ISO country code
            "state": "NY"               # 2-letter state code
        }
    
    Raises:
        ValueError: If location cannot be geocoded
        requests.HTTPError: If API request fails
    """
    url = f"{ORS_BASE_URL}/geocode/search"
    headers = {
        "Authorization": settings.OPENROUTESERVICE_API_KEY
    }
    params = {
        "text": place_name,
        "size": 1,
    }

    if enforce_us:
        params["boundary.country"] = "US"

    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()
    features = data.get("features")

    if not features:
        raise ValueError(f"Could not geocode location: {place_name}")

    feature = features[0]
    properties = feature.get("properties", {})

    country_code = (properties.get("country_code") or "").upper()
    country_name = (properties.get("country") or "").lower()
    state_raw = (
        properties.get("region_a")
        or properties.get("region")
        or properties.get("state")
        or properties.get("state_code")
    )
    state_code = normalize_state_code(state_raw)

    # Fallback normalization
    if not country_code and "united states" in country_name:
        country_code = "US"

    return {
        "coords": feature["geometry"]["coordinates"],  # [lon, lat]
        "country_code": country_code,
        "state": state_code,
    }


def get_route(start_coords: list, end_coords: list) -> dict:
    """
    Get driving route from OpenRouteService Directions API.
    
    🎯 KEY REQUIREMENT: This is the ONLY routing API call per request!
    
    Args:
        start_coords: [longitude, latitude] of start point
        end_coords: [longitude, latitude] of end point
    
    Returns:
        {
            "summary": {
                "distance": 2797.18,      # Total distance in miles
                "duration": 162036        # Travel time in seconds
            },
            "geometry": {...}            # Route coordinates (encoded or GeoJSON)
        }
    
    API Response Formats:
        - format="geojson" → Returns encoded polyline string (most common)
        - "features" structure → GeoJSON Feature format
        - "routes" structure → Direct routes array format
    
    Raises:
        requests.HTTPError: If API request fails
        ValueError: If response format is unexpected
    """
    url = f"{ORS_BASE_URL}/v2/directions/driving-car"
    headers = {
        "Authorization": settings.OPENROUTESERVICE_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "coordinates": [
            start_coords,
            end_coords
        ],
        "units": "mi",
        "format": "geojson"
    }

    response = requests.post(url, json=payload, headers=headers, timeout=15)
    response.raise_for_status()

    data = response.json()

    if "features" in data:
        feature = data["features"][0]
        return {
            "summary": feature["properties"]["summary"],
            "geometry": feature["geometry"],
        }

    if "routes" in data:
        route = data["routes"][0]
        return {
            "summary": route.get("summary", {}),
            "geometry": route.get("geometry"),
        }

    raise ValueError(f"Unexpected route response: {data}")


def _point_line_distance(point: list[float], start: list[float], end: list[float]) -> float:
    """
    Calculate perpendicular distance from point to line segment.
    
    Used by Ramer-Douglas-Peucker simplification algorithm.
    
    Args:
        point: [x, y] coordinate to measure from
        start: [x, y] line segment start
        end: [x, y] line segment end
    
    Returns:
        Euclidean distance from point to line segment
    """
    if start == end:
        dx = point[0] - start[0]
        dy = point[1] - start[1]
        return (dx * dx + dy * dy) ** 0.5

    sx, sy = start
    ex, ey = end
    px, py = point
    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return ((px - sx) ** 2 + (py - sy) ** 2) ** 0.5

    t = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = sx + t * dx
    proj_y = sy + t * dy
    return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5


def simplify_linestring(coords: list[list[float]], tolerance: float) -> list[list[float]]:
    """
    Simplify coordinate array using Ramer-Douglas-Peucker algorithm.
    
    Recursively removes points that are closer than 'tolerance' to the line
    connecting their neighbors. Dramatically reduces coordinate count while
    preserving overall shape.
    
    Example:
        100 coordinates with tolerance=0.01 → ~10 coordinates
    
    Args:
        coords: List of [lon, lat] coordinates
        tolerance: Maximum distance threshold (0.01 recommended for degrees)
    
    Returns:
        Simplified list of [lon, lat] coordinates
    """
    if not coords or len(coords) <= 2:
        return coords

    max_dist = 0.0
    index = 0
    start = coords[0]
    end = coords[-1]

    for i in range(1, len(coords) - 1):
        dist = _point_line_distance(coords[i], start, end)
        if dist > max_dist:
            max_dist = dist
            index = i

    if max_dist > tolerance:
        left = simplify_linestring(coords[: index + 1], tolerance)
        right = simplify_linestring(coords[index:], tolerance)
        return left[:-1] + right

    return [start, end]


def simplify_geojson_linestring(geometry: dict | None, tolerance: float) -> dict | None:
    """
    Simplify GeoJSON LineString by reducing coordinate count.
    
    Wrapper around simplify_linestring() for GeoJSON objects.
    
    Args:
        geometry: GeoJSON LineString {"type": "LineString", "coordinates": [...]}
        tolerance: Simplification threshold (0.01 = good balance)
    
    Returns:
        Simplified GeoJSON LineString or None if invalid input
    """
    if not geometry or not isinstance(geometry, dict):
        return None
    if geometry.get("type") != "LineString":
        return geometry

    coords = geometry.get("coordinates", [])
    simplified = simplify_linestring(coords, tolerance)
    return {
        "type": "LineString",
        "coordinates": simplified,
    }


def encode_polyline(coords: list[list[float]], precision: int = 5) -> str:
    """
    Encode coordinates into Google Polyline Format (compressed string).
    
    Reduces storage/transmission size by ~90% compared to raw JSON.
    Compatible with Google Maps, Mapbox, Leaflet polyline decoders.
    
    Algorithm:
        1. Convert lat/lon to integers (multiply by 10^precision)
        2. Calculate deltas from previous point (differential encoding)
        3. Apply variable-length encoding (fewer bits for small deltas)
        4. Convert to ASCII string
    
    Example:
        [[lon1, lat1], [lon2, lat2]] → "m{hwFtlnbME?eALOB..."
    
    Args:
        coords: List of [lon, lat] coordinates
        precision: Decimal places (5 = ~1 meter accuracy, 6 = ~10cm)
    
    Returns:
        Encoded polyline string
    """
    factor = 10 ** precision
    last_lat = 0
    last_lng = 0
    result: list[str] = []

    def encode_value(value: int) -> None:
        value = ~(value << 1) if value < 0 else (value << 1)
        while value >= 0x20:
            result.append(chr((0x20 | (value & 0x1F)) + 63))
            value >>= 5
        result.append(chr(value + 63))

    for lng, lat in coords:
        lat_i = int(round(lat * factor))
        lng_i = int(round(lng * factor))
        encode_value(lat_i - last_lat)
        encode_value(lng_i - last_lng)
        last_lat = lat_i
        last_lng = lng_i

    return "".join(result)


def decode_polyline(encoded: str, precision: int = 5) -> list[list[float]]:
    """
    Decode Google Polyline Format string into coordinates.
    
    ⭐ CRITICAL FUNCTION: OpenRouteService returns encoded polyline strings,
    not GeoJSON, despite format="geojson" parameter. This function converts
    the encoded string to [[lon, lat], ...] format for map display.
    
    Algorithm (reverse of encode_polyline):
        1. Read variable-length encoded integers from string
        2. Reconstruct deltas between points
        3. Accumulate deltas to get absolute coordinates
        4. Divide by 10^precision to get decimal degrees
    
    Example:
        "m{hwFtlnbME?eALOB..." → [[-74.006, 40.7128], [-74.007, 40.7130], ...]
    
    Args:
        encoded: Polyline string from OpenRouteService
        precision: Must match encoding precision (default 5)
    
    Returns:
        List of [longitude, latitude] coordinates
    """
    factor = 10 ** precision
    coords = []
    index = 0
    lat = 0
    lng = 0

    while index < len(encoded):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lat += ~(result >> 1) if (result & 1) else (result >> 1)

        # Decode longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lng += ~(result >> 1) if (result & 1) else (result >> 1)

        coords.append([lng / factor, lat / factor])

    return coords
