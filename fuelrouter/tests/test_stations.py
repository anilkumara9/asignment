"""Unit tests for station-to-route matching with injected stations (no network)."""

from django.test import SimpleTestCase, override_settings

import fuelrouter.services.stations as stations_mod
from fuelrouter.services.stations import _cell, stations_near_route


def fake_station(sid, lat, lng, price=3.0):
    return {"id": sid, "name": f"Stop {sid}", "address": "I-80",
            "city": "Testville", "state": "TS", "price": price,
            "lat": lat, "lng": lng}


class StationMatchingTests(SimpleTestCase):
    def setUp(self):
        # Inject a tiny fake station list + grid instead of the real data file.
        fake = [
            fake_station("NEAR", 40.05, -99.50, 3.10),   # ~3.5 mi off route
            fake_station("FAR", 42.00, -99.50, 2.00),     # ~140 mi off route
            fake_station("NEAR2", 40.02, -99.70, 2.90),  # on-route, cheaper
        ]
        grid = {}
        for s in fake:
            grid.setdefault(_cell(s["lat"], s["lng"]), []).append(s)
        self._old = (stations_mod._stations, stations_mod._grid)
        stations_mod._stations, stations_mod._grid = fake, grid

    def tearDown(self):
        stations_mod._stations, stations_mod._grid = self._old

    @override_settings(STATION_CAPTURE_MILES=10)
    def test_matches_only_stations_within_capture_radius(self):
        # Dense geometry (~13 miles between points), heading straight east.
        route = [(-100.0 + 0.25 * i, 40.0) for i in range(5)]
        matched = stations_near_route(route)
        ids = [s["id"] for s in matched]
        self.assertIn("NEAR", ids)
        self.assertIn("NEAR2", ids)
        self.assertNotIn("FAR", ids)

    @override_settings(STATION_CAPTURE_MILES=10)
    def test_sorted_by_route_mile_then_price(self):
        route = [(-100.0 + 0.25 * i, 40.0) for i in range(5)]
        matched = stations_near_route(route)
        miles = [s["route_mile"] for s in matched]
        self.assertEqual(miles, sorted(miles))
        # NEAR2 (-99.70) comes before NEAR (-99.50) along the route
        self.assertLess(matched[0]["route_mile"], matched[1]["route_mile"])
        for s in matched:
            self.assertLessEqual(s["miles_off_route"], 10)
