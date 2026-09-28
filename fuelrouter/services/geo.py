"""Small geometry helpers: haversine distance, cumulative route mileage,
and polyline simplification (Douglas-Peucker)."""

import math

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def cumulative_miles(coords):
    """coords: list of (lng, lat). Returns cumulative miles at each point."""
    cum = [0.0]
    for i in range(1, len(coords)):
        lng1, lat1 = coords[i - 1]
        lng2, lat2 = coords[i]
        cum.append(cum[-1] + haversine_miles(lat1, lng1, lat2, lng2))
    return cum


def _perp_distance_sq(point, start, end):
    """Squared planar distance from point to the segment start->end.

    Points are (x, y) tuples; good enough for simplification purposes.
    """
    px, py = point
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    if dx == 0 and dy == 0:
        return (px - sx) ** 2 + (py - sy) ** 2
    t = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = sx + t * dx, sy + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def simplify_polyline(coords, epsilon):
    """Douglas-Peucker simplification. coords: list of (lng, lat).

    epsilon is in degrees. Returns a reduced list of points.
    """
    n = len(coords)
    if n < 3:
        return list(coords)
    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    eps_sq = epsilon * epsilon
    while stack:
        first, last = stack.pop()
        max_d, idx = 0.0, -1
        for i in range(first + 1, last):
            d = _perp_distance_sq(coords[i], coords[first], coords[last])
            if d > max_d:
                max_d, idx = d, i
        if max_d > eps_sq:
            keep[idx] = True
            stack.append((first, idx))
            stack.append((idx, last))
    return [p for p, k in zip(coords, keep) if k]
