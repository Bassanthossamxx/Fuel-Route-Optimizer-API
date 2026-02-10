import requests
from django.conf import settings

ORS_BASE_URL = "https://api.openrouteservice.org"

US_BBOXES = [
    (-124.848974, 24.396308, -66.885444, 49.384358),  # Contiguous US
    (-170.0, 51.0, -130.0, 71.0),  # Alaska
    (-161.0, 18.5, -154.0, 22.5),  # Hawaii
]


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
    Convert a text location into coordinates and country code.

    Returns:
    {
        "coords": [lon, lat],
        "country_code": "US"
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

    # Fallback normalization
    if not country_code and "united states" in country_name:
        country_code = "US"

    return {
        "coords": feature["geometry"]["coordinates"],  # [lon, lat]
        "country_code": country_code,
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
        "units": "mi"
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
