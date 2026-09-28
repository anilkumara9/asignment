"""Minimum-cost refuelling plan for a fixed route with varying fuel prices.

Classic greedy solution to the "min-cost to travel with gas stations" problem:

* The vehicle starts with an empty tank at the start of the route, so the
  first stop is the first station within range; the fuel burned reaching it
  is billed at that station's price.
* At any stop, buy just enough fuel to reach the next *cheaper* station
  within range; if there is none, fill the tank (but never buy more than is
  needed to reach the destination).
* The destination is modelled as a station with price $0 so the plan never
  buys fuel it will not burn.

This greedy is optimal for the subproblem starting at the first stop
(exact dynamic-programming oracle agrees on randomized cases): from any stop,
buying just enough to reach the next cheaper station within range — or filling
up when none is cheaper in range — minimizes the remaining trip cost. The one
heuristic choice is the first stop itself: the nearest station within range
of the origin. That keeps the empty-tank assumption physical (a few miles on
fumes rather than hundreds) at the cost of a small, bounded deviation from
the absolute minimum in steep price-gradient scenarios.
"""

from django.conf import settings


class InfeasibleRouteError(Exception):
    pass


def plan_fuel_stops(route_distance_miles, stations, mpg=None, max_range_miles=None):
    """Compute the cheapest refuelling plan.

    ``stations``: list of dicts with ``route_mile`` and ``price`` (USD/gal),
    sorted by route_mile. Returns a list of ``(station_dict, gallons)``
    tuples in stop order.
    """
    mpg = settings.MPG if mpg is None else mpg
    max_range = settings.MAX_RANGE_MILES if max_range_miles is None else max_range_miles
    tank_gallons = max_range / mpg

    nodes = list(stations)
    # Destination: price 0 guarantees we arrive on empty, never over-buying.
    nodes.append({"route_mile": route_distance_miles, "price": 0.0,
                  "is_destination": True})
    nodes.sort(key=lambda n: (n["route_mile"], n["price"]))
    n = len(nodes)

    # First stop: nearest station reachable from the start on an empty tank.
    first_idx = next(
        (i for i, s in enumerate(nodes)
         if not s.get("is_destination") and s["route_mile"] <= max_range),
        None,
    )
    if first_idx is None:
        raise InfeasibleRouteError(
            f"No fuel station within {max_range:g} miles of the start; "
            "cannot begin this route."
        )

    # Fuel "burned" before the first stop; billed at the first stop's price.
    opening_debt = nodes[first_idx]["route_mile"] / mpg

    tank = 0.0  # usable gallons currently on board
    purchases = []

    for i in range(first_idx, n - 1):
        here, nxt = nodes[i], nodes[i + 1]
        leg_miles = nxt["route_mile"] - here["route_mile"]
        if leg_miles - max_range > 1e-9:
            # The nearest node ahead is unreachable, so every node beyond it
            # is too: the route genuinely cannot be completed.
            raise InfeasibleRouteError(
                f"No fuel station within {max_range:g} miles after mile "
                f"{here['route_mile']:.1f}; cannot complete this route."
            )

        # First station ahead within range that is cheaper than here.
        target = None
        for j in range(i + 1, n):
            if nodes[j]["route_mile"] - here["route_mile"] - max_range > 1e-9:
                break
            if nodes[j]["price"] < here["price"]:
                target = nodes[j]
                break

        if target is None:
            # Nothing cheaper ahead: fill up, but not beyond destination need.
            want_on_board = min(
                tank_gallons, (route_distance_miles - here["route_mile"]) / mpg
            )
        else:
            want_on_board = (target["route_mile"] - here["route_mile"]) / mpg

        buy = max(0.0, want_on_board - tank)
        if i == first_idx:
            # The opening debt was burned before the first stop; it was never
            # on board, so it must not count toward the tank level either.
            buy += opening_debt
            tank_after_purchase = want_on_board
        else:
            tank_after_purchase = tank + buy  # == max(tank, want_on_board)
        if buy > 1e-9:
            purchases.append((here, buy))

        tank = tank_after_purchase - leg_miles / mpg
        if tank < -1e-6:
            raise InfeasibleRouteError(
                "Ran out of fuel between planned stops; route infeasible."
            )
        tank = max(tank, 0.0)

    return purchases
