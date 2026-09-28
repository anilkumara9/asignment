"""Free routing via the public OSRM demo server (no API key required).

Exactly one HTTP call per unique (start, finish) pair — the result is cached
in Django's cache, so repeated requests cost nothing.
"""

import requests
from django.conf import settings
from django.core.cache import cache


class RoutingError(Exception):
    pass


def get_route(start_lat, start_lng, finish_lat, finish_lng):
    """Return dict with distance_miles, duration_minutes and coordinates.

    coordinates is a list of [lng, lat] pairs describing the full route.
    """
    cache_key = (
        f"route:v1:{start_lat:.5f},{start_lng:.5f};{finish_lat:.5f},{finish_lng:.5f}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = (
        f"{settings.OSRM_URL}/"
        f"{start_lng:.6f},{start_lat:.6f};{finish_lng:.6f},{finish_lat:.6f}"
    )
    try:
        resp = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson"},
            headers={"User-Agent": "SpotterFuelRouteAssessment/1.0 (coding assessment demo)"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise RoutingError(f"Routing service unavailable: {exc}") from exc

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError(
            f"Could not find a driving route: {data.get('message', data.get('code'))}"
        )

    route = data["routes"][0]
    result = {
        "distance_miles": route["distance"] / 1609.344,
        "duration_minutes": route["duration"] / 60.0,
        # GeoJSON order: [lng, lat]
        "coordinates": [tuple(pt) for pt in route["geometry"]["coordinates"]],
    }
    cache.set(cache_key, result)
    return result
