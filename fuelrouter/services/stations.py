"""Fuel-station data and matching stations to a route.

Station coordinates come from ``fuelrouter/data/stations.json`` (built offline:
US Census gazetteer for the city of each truck stop, Nominatim fallback for
the remainder — see ``scripts/build_stations.py``).

Matching uses a coarse lat/lng grid index so a cross-country route with
thousands of geometry points is matched against ~7k stations in well under a
second, with zero external API calls.
"""

import json
import math
from pathlib import Path

from django.conf import settings

from .geo import cumulative_miles, haversine_miles

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "stations.json"

_stations = None
_grid = None
_CELL_DEG = 0.25  # ~17 miles; 3x3 cells comfortably cover the capture radius


def _cell(lat, lng):
    return (math.floor(lat / _CELL_DEG), math.floor(lng / _CELL_DEG))


def load_stations():
    """Load (and grid-index) the station list once per process."""
    global _stations, _grid
    if _stations is None:
        with open(DATA_PATH) as f:
            _stations = json.load(f)
        _grid = {}
        for s in _stations:
            _grid.setdefault(_cell(s["lat"], s["lng"]), []).append(s)
    return _stations, _grid


def _subsample(coords, max_points=2000):
    if len(coords) <= max_points:
        return coords
    step = math.ceil(len(coords) / max_points)
    pts = coords[::step]
    if pts[-1] != coords[-1]:
        pts.append(coords[-1])
    return pts


def stations_near_route(route_coords, capture_miles=None):
    """Return stations within ``capture_miles`` of the route.

    Each returned dict is a station plus ``route_mile`` (distance along the
    route of its closest point) and ``miles_off_route`` (how far the station
    sits from the route). Sorted by (route_mile, price).
    """
    capture_miles = (
        settings.STATION_CAPTURE_MILES if capture_miles is None else capture_miles
    )
    stations, grid = load_stations()

    pts = _subsample(route_coords)
    cum = cumulative_miles(pts)

    # cell radius needed to cover the capture distance
    cell_radius = max(1, math.ceil((capture_miles / 69.0) / _CELL_DEG) + 1)

    best = {}  # station id -> (off_route_miles, route_mile)
    for (lng, lat), mile in zip(pts, cum):
        clat, clng = _cell(lat, lng)
        for dlat in range(-cell_radius, cell_radius + 1):
            for dlng in range(-cell_radius, cell_radius + 1):
                for s in grid.get((clat + dlat, clng + dlng), ()):
                    d = haversine_miles(lat, lng, s["lat"], s["lng"])
                    if d <= capture_miles:
                        prev = best.get(s["id"])
                        if prev is None or d < prev[0]:
                            best[s["id"]] = (d, mile)

    by_id = {s["id"]: s for s in stations}
    matched = []
    for sid, (off, mile) in best.items():
        s = by_id[sid]
        matched.append(
            {
                "id": s["id"],
                "name": s["name"],
                "address": s["address"],
                "city": s["city"],
                "state": s["state"],
                "price": s["price"],
                "lat": s["lat"],
                "lng": s["lng"],
                "route_mile": round(mile, 2),
                "miles_off_route": round(off, 2),
            }
        )
    matched.sort(key=lambda s: (s["route_mile"], s["price"]))
    return matched
