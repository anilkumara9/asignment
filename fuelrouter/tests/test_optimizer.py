"""Unit tests for the minimum-cost refuelling optimizer (no network)."""

from django.test import SimpleTestCase

from fuelrouter.services.optimizer import InfeasibleRouteError, plan_fuel_stops


def station(mile, price, sid="S"):
    return {"id": sid, "route_mile": float(mile), "price": float(price)}


class OptimizerTests(SimpleTestCase):
    def test_buys_just_enough_to_reach_cheaper_station(self):
        # 1000-mile trip, 10 mpg, 500-mile range (50 gal tank).
        stations = [station(100, 4.00, "A"), station(400, 3.00, "B"),
                    station(700, 3.50, "C")]
        stops = plan_fuel_stops(1000, stations, mpg=10, max_range_miles=500)

        by_id = {s["id"]: g for s, g in stops}
        # A: 30 gal to reach B + 10 gal burned getting to A
        self.assertAlmostEqual(by_id["A"], 40.0)
        # B: nothing cheaper within 500 -> fill the 50-gal tank
        self.assertAlmostEqual(by_id["B"], 50.0)
        # C: only what's needed to reach the destination
        self.assertAlmostEqual(by_id["C"], 10.0)

        total_gallons = sum(g for _, g in stops)
        # Arrive on empty: total bought == trip distance / mpg.
        self.assertAlmostEqual(total_gallons, 100.0)

        total_cost = sum(g * s["price"] for s, g in stops)
        self.assertAlmostEqual(total_cost, 40 * 4.0 + 50 * 3.0 + 10 * 3.5)

    def test_skips_expensive_station_when_cheaper_is_in_range(self):
        stations = [station(100, 5.00, "EXP"), station(150, 2.50, "CHEAP")]
        stops = plan_fuel_stops(600, stations, mpg=10, max_range_miles=500)
        by_id = {s["id"]: g for s, g in stops}
        # At EXP: cheaper station 50 miles ahead -> buy only to reach it
        # (5 gal) plus the 10 gal burned getting to EXP.
        self.assertAlmostEqual(by_id["EXP"], 15.0)
        # At CHEAP: destination 450 miles away at price $0 -> buy exactly
        # what's needed to arrive on empty.
        self.assertAlmostEqual(by_id["CHEAP"], 45.0)

    def test_single_stop_short_trip(self):
        stations = [station(100, 3.00, "A")]
        stops = plan_fuel_stops(400, stations, mpg=10, max_range_miles=500)
        self.assertEqual(len(stops), 1)
        self.assertAlmostEqual(stops[0][1], 40.0)  # 30 + 10 debt

    def test_infeasible_gap_raises(self):
        stations = [station(100, 3.00, "A")]
        with self.assertRaises(InfeasibleRouteError):
            plan_fuel_stops(1200, stations, mpg=10, max_range_miles=500)

    def test_no_station_near_start_raises(self):
        stations = [station(600, 3.00, "A")]
        with self.assertRaises(InfeasibleRouteError):
            plan_fuel_stops(1000, stations, mpg=10, max_range_miles=500)

    def test_never_buys_more_than_tank_holds(self):
        stations = [station(490, 4.00, "A"), station(600, 3.00, "B")]
        stops = plan_fuel_stops(1000, stations, mpg=10, max_range_miles=500)
        for _, gallons in stops:
            self.assertLessEqual(gallons, 50.0 + 49.0)  # debt only at 1st stop
        # first stop: debt 49 gal + 11 to reach B = 60 total purchased there
        self.assertAlmostEqual(stops[0][1], 60.0)

    def test_fuel_never_vanishes_between_stops(self):
        # Regression test: arriving at a stop with MORE fuel than needed to
        # reach the next cheaper station must not discard the surplus.
        # A->$3, M->$4, X->$3.5, B->$1 over an 800-mile trip.
        stations = [station(100, 3.00, "A"), station(200, 4.00, "M"),
                    station(300, 3.50, "X"), station(400, 1.00, "B")]
        stops = plan_fuel_stops(800, stations, mpg=10, max_range_miles=500)
        by_id = {s["id"]: g for s, g in stops}
        # At A: buy to reach B ($1) + 10 gal burned getting to A.
        self.assertAlmostEqual(by_id["A"], 40.0)
        # M and X are passed with enough on board; nothing bought there.
        self.assertNotIn("M", by_id)
        self.assertNotIn("X", by_id)
        # At B: fill exactly what's needed to reach the destination.
        self.assertAlmostEqual(by_id["B"], 40.0)
        # Fuel conservation: bought == burned, arrive on empty.
        self.assertAlmostEqual(sum(g for _, g in stops), 80.0)
