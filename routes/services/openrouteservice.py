import requests
from django.conf import settings

ORS_BASE_URL = "https://api.openrouteservice.org"

US_BBOXES = [
    (-124.848974, 24.396308, -66.885444, 49.384358),  # Contiguous US
    (-170.0, 51.0, -130.0, 71.0),  # Alaska
    (-161.0, 18.5, -154.0, 22.5),  # Hawaii
]

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

US_STATE_FULL_NAME = {abbr: name for name, abbr in US_STATE_ABBREV.items()}

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
    if not value:
        return None

    value = value.strip().upper()
    if len(value) == 2:
        return value

    return US_STATE_ABBREV.get(value)


def state_code_to_full_name(state_code: str | None) -> str | None:
    if not state_code:
        return None

    return US_STATE_FULL_NAME.get(state_code.upper())


def build_state_corridor(start_state: str | None, end_state: str | None) -> list[str]:
    start_state = normalize_state_code(start_state)
    end_state = normalize_state_code(end_state)

    if not start_state and not end_state:
        return []
    if start_state == end_state:
        return [start_state]
    if not start_state or not end_state:
        return [state for state in [start_state, end_state] if state]

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

    if end_state not in parents:
        return [start_state, end_state]

    path = []
    node = end_state
    while node is not None:
        path.append(node)
        node = parents.get(node)

    return list(reversed(path))


def is_within_us_bbox(coords: list) -> bool:
    if not coords or len(coords) != 2:
        return False

    lon, lat = coords
    for min_lon, min_lat, max_lon, max_lat in US_BBOXES:
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            return True

    return False


def geocode_place(place_name: str, enforce_us: bool = False) -> dict:
    """
    Convert a text location into coordinates, country code, and state.

    Returns:
    {
        "coords": [lon, lat],
        "country_code": "US",
        "state": "NY"
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
    Call OpenRouteService Directions API ONCE.
    Returns summary and geometry.
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
