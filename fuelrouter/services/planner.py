"""High-level trip planner: geocode -> route -> match stations -> optimize.

External API usage per unique (start, finish) pair:
  * Nominatim geocoding: 1 call per unique place name (cached 24h)
  * OSRM routing:       1 call per unique coordinate pair (cached 24h)
Everything else (station matching, price optimization) is local.
"""

from urllib.parse import quote_plus, urlencode

from django.conf import settings
from django.core.cache import cache

from .geocode import GeocodeError, geocode
from .geo import simplify_polyline
from .optimizer import InfeasibleRouteError, plan_fuel_stops
from .routing import RoutingError, get_route
from .stations import stations_near_route


class PlanningError(Exception):
    pass


def plan_trip(start_query, finish_query, mpg=None, max_range_miles=None):
    """Plan the cheapest-fuelled trip; returns a JSON-serializable dict."""
    mpg = settings.MPG if mpg is None else mpg
    max_range = settings.MAX_RANGE_MILES if max_range_miles is None else max_range_miles

    cache_key = (
        f"plan:v2:{quote_plus(start_query.strip().lower())}|"
        f"{quote_plus(finish_query.strip().lower())}|{mpg}|{max_range}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        s_lat, s_lng, s_name = geocode(start_query)
        f_lat, f_lng, f_name = geocode(finish_query)
    except GeocodeError as exc:
        raise PlanningError(str(exc)) from exc

    try:
        route = get_route(s_lat, s_lng, f_lat, f_lng)
    except RoutingError as exc:
        raise PlanningError(str(exc)) from exc

    distance = route["distance_miles"]
    coords = route["coordinates"]
    if distance < 1e-6 or len(coords) < 2:
        raise PlanningError("Start and finish resolve to the same place.")

    nearby = stations_near_route(coords)
    if not nearby:
        raise PlanningError(
            "No fuel stations found near this route in our price data."
        )

    try:
        purchases = plan_fuel_stops(distance, nearby, mpg=mpg,
                                   max_range_miles=max_range)
    except InfeasibleRouteError as exc:
        raise PlanningError(str(exc)) from exc

    stops = []
    total_cost = 0.0
    total_gallons = 0.0
    for station, gallons in purchases:
        gallons = round(gallons, 3)
        cost = round(gallons * station["price"], 2)
        total_gallons += gallons
        total_cost += cost
        stops.append(
            {
                "station_id": station["id"],
                "name": station["name"],
                "address": station["address"],
                "city": station["city"],
                "state": station["state"],
                "price_per_gallon_usd": round(station["price"], 3),
                "lat": station["lat"],
                "lng": station["lng"],
                "route_mile": station["route_mile"],
                "miles_off_route": station["miles_off_route"],
                "gallons": gallons,
                "cost_usd": cost,
            }
        )

    total_cost = round(total_cost, 2)
    total_gallons = round(total_gallons, 3)

    map_path = "/map/?" + urlencode({"start": start_query, "finish": finish_query})
    result = {
        "start": {
            "query": start_query,
            "display_name": s_name,
            "lat": round(s_lat, 6),
            "lng": round(s_lng, 6),
        },
        "finish": {
            "query": finish_query,
            "display_name": f_name,
            "lat": round(f_lat, 6),
            "lng": round(f_lng, 6),
        },
        "route": {
            "distance_miles": round(distance, 1),
            "duration_minutes": round(route["duration_minutes"], 1),
            # Simplified for a compact response; full detail lives on the map.
            "geometry": [
                [round(lng, 5), round(lat, 5)]
                for lng, lat in simplify_polyline(coords, 0.01)
            ],
        },
        "vehicle": {
            "mpg": mpg,
            "max_range_miles": max_range,
            "tank_gallons": round(max_range / mpg, 2),
        },
        "fuel_stops": stops,
        "summary": {
            "num_stops": len(stops),
            "total_gallons": total_gallons,
            "total_cost_usd": total_cost,
            "avg_price_per_gallon_usd": (
                round(total_cost / total_gallons, 3) if total_gallons else 0.0
            ),
        },
        "map_path": map_path,
        "notes": [
            "Fuel prices are retail USD/gallon from the provided OPIS truck-stop data.",
            "The vehicle starts with an empty tank; fuel burned before the "
            "first stop is billed at that stop's price.",
            "Stations are matched within "
            f"{settings.STATION_CAPTURE_MILES:g} miles of the driving route.",
        ],
    }
    cache.set(cache_key, result)
    return result
