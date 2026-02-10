"""
OpenRouteService Integration Module

This module handles all interactions with the OpenRouteService API:
1. Geocoding: Convert location names to coordinates
2. Routing: Calculate driving routes between two points
3. Geometry Processing: Decode polylines, simplify GeoJSON
4. State Management: Build state corridors for USA routes

OpenRouteService API Docs: https://openrouteservice.org/dev/#/api-docs

Key Optimizations:
- Single routing API call per request (minimize API usage)
- Polyline decoding for GeoJSON conversion
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


def is_inside_usa(coords: list) -> bool:
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
    
    Args:
        place_name: Text description of location
        enforce_us: If True, restricts search to USA only
    
    Returns:
        {
            "coords": [lon, lat],      # [longitude, latitude]
            "country_code": "US",       # ISO country code
            "state": "NY"               # 2-letter state code
        }
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
    
    # This is the ONLY routing API call per request!
    
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
    
    Visual explanation:
         point (px, py)
            |
            |  <- perpendicular distance
            |
    start ●--------● end
         (sx,sy)  (ex,ey)
    
    algorithm to decide if a point is
    "close enough" to the line connecting its neighbors.
    
    Args:
        point: [x, y] coordinate to measure from
        start: [x, y] line segment start
        end: [x, y] line segment end
    
    Returns:
        Euclidean distance from point to line segment
    """
    # If start and end are the same point, just measure direct distance
    if start == end:
        dx = point[0] - start[0]
        dy = point[1] - start[1]
        return (dx * dx + dy * dy) ** 0.5  

    # Extract coordinates for clarity
    sx, sy = start
    ex, ey = end
    px, py = point
    
    # STEP 1: Calculate line segment direction vector
    dx = ex - sx  # horizontal component
    dy = ey - sy  # vertical component
    
    # EDGE CASE 2: Double-check for zero-length segment
    if dx == 0 and dy == 0:
        return ((px - sx) ** 2 + (py - sy) ** 2) ** 0.5

    # STEP 2: Project point onto the infinite line (find closest point on line)
    t = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    
    # STEP 3: Clamp to [0, 1] to stay within the segment
    t = max(0.0, min(1.0, t))  # If t < 0, use start. If t > 1, use end.
    
    # STEP 4: Calculate the projection point on the segment
    proj_x = sx + t * dx 
    proj_y = sy + t * dy
    
    # STEP 5: Return distance from original point to projection point
    return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5


def simplify_linestring(coords: list[list[float]], tolerance: float) -> list[list[float]]:
    """
    Simplify coordinate array using Ramer-Douglas-Peucker algorithm.
    how it works?:
    Imagine drawing a line from first to last point. Any point in between that's
    "close enough" to this line can be removed. If a point is far from the line,
    we keep it and recursively simplify the segments on either side.
    
    Visual example:
    Before:  ●--●--●--●--●--●--●     (7 points)
    After:   ●--------------●        (2 points) - middle points were too close to line
    Real-world benefit:
        Faster map rendering, smaller JSON responses
    
    Returns:
        Simplified list of [lon, lat] coordinates
    """
    # If 2 or fewer points, can't simplify further
    if not coords or len(coords) <= 2:
        return coords

    # STEP 1: Draw imaginary line from first to last point
    start = coords[0]
    end = coords[-1]
    
    # STEP 2: Find the point FARTHEST from this line (the "peak")
    max_dist = 0.0
    index = 0
    for i in range(1, len(coords) - 1):  # Skip first and last (they're the line endpoints)
        dist = _point_line_distance(coords[i], start, end)
        if dist > max_dist:
            max_dist = dist
            index = i  # Remember which point is farthest

    # STEP 3: Decide if the farthest point is "significant"
    if max_dist > tolerance:
        # Point is far enough - it's important! Keep it and recursively simplify both sides
        left = simplify_linestring(coords[: index + 1], tolerance)   # Simplify left segment
        right = simplify_linestring(coords[index:], tolerance)        # Simplify right segment
        return left[:-1] + right  # Merge (remove duplicate middle point)

    # STEP 4: All middle points are too close - just keep start and end
    return [start, end]


def simplify_geojson_linestring(geometry: dict | None, tolerance: float) -> dict | None:
    """
    Simplify GeoJSON LineString by reducing coordinate count.
    
    Args:
        geometry: GeoJSON LineString {"type": "LineString", "coordinates": [...]}
    
    Returns:
        Simplified GeoJSON LineString
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

# this is for google polyline format, not coded by me, but used in some ORS responses
def decode_polyline(encoded: str, precision: int = 5) -> list[list[float]]:
    """
    Decode Google Polyline Format string into coordinates.

    Google Polyline Format compresses GPS coordinates into a short string.
    Instead of "40.7128,-74.0060" (16 chars), we get "m{hwF" (5 chars).
    
    Algorithm:
        1. Read variable-length encoded integers from string
        2. Reconstruct deltas between consecutive points
        3. Accumulate deltas to get absolute coordinates
        4. Divide by 10^precision to get decimal degrees

    Returns:
        List of [longitude, latitude] coordinates
    """
    # SETUP: Factor for converting integers back to decimal degrees
    factor = 10 ** precision  # precision=5 → factor=100000
    coords = []
    index = 0
    
    # Accumulated coordinates (starts at 0,0 then we add deltas)
    lat = 0
    lng = 0

    # Read pairs of (latitude, longitude) deltas until string ends
    while index < len(encoded):
        # STEP 1: Decode latitude delta
        shift = 0
        result = 0
        while True:
            # Read each character as a 5-bit chunk
            b = ord(encoded[index]) - 63  # Convert ASCII to 0-63 range
            index += 1
            
            # Add this chunk's bits to the result
            result |= (b & 0x1F) << shift  # 0x1F = 31 (bitmask for lower 5 bits)
            shift += 5
            
            # If bit 6 is 0, this is the last chunk for this number
            if b < 0x20:  # 0x20 = 32 (bit 6 set)
                break
        
        # Convert from zig-zag encoding (handles negative numbers)
        # If LSB is 1, number is negative: invert all bits
        # If LSB is 0, number is positive: shift right by 1
        lat += ~(result >> 1) if (result & 1) else (result >> 1)

        # STEP 2: Decode longitude delta (same process)
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

        # STEP 3: Convert accumulated integers to decimal degrees and store
        coords.append([lng / factor, lat / factor])

    return coords
