"""Free geocoding via OpenStreetMap Nominatim (no API key required).

Results are cached in Django's cache so a repeated query never hits the
network again.
"""

import requests
from urllib.parse import quote_plus

from django.conf import settings
from django.core.cache import cache


class GeocodeError(Exception):
    pass


def geocode(query):
    """Resolve a place name to (lat, lng, display_name).

    Only matches inside the USA; raises GeocodeError otherwise.
    """
    query = (query or "").strip()
    if not query:
        raise GeocodeError("Empty location query.")

    cache_key = f"geocode:v2:{quote_plus(query.lower())}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            settings.NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "us",  # assignment: both locations within the USA
                "addressdetails": 1,
            },
            headers={
                # Nominatim usage policy requires an identifying User-Agent.
                "User-Agent": "SpotterFuelRouteAssessment/1.0 (coding assessment demo)",
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise GeocodeError(f"Geocoding service unavailable: {exc}") from exc

    if not results:
        raise GeocodeError(
            f"Could not find '{query}' inside the USA. "
            "Try a 'City, ST' format, e.g. 'Dallas, TX'."
        )

    best = results[0]
    country = (best.get("address") or {}).get("country_code", "").lower()
    if country != "us":
        raise GeocodeError(f"'{query}' does not appear to be inside the USA.")

    result = (float(best["lat"]), float(best["lon"]), best.get("display_name", query))
    cache.set(cache_key, result)
    return result
