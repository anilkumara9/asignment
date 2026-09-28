"""Planner orchestration tests with external services mocked (no network)."""

import warnings
from unittest.mock import patch

from django.core.cache.backends.base import CacheKeyWarning
from django.test import SimpleTestCase

from fuelrouter.services import planner as planner_mod
from fuelrouter.services.planner import plan_trip


def _station(sid, mile, price):
    return {"id": sid, "name": "S", "address": "", "city": "", "state": "TX",
            "price": price, "lat": 0.0, "lng": 0.0,
            "route_mile": mile, "miles_off_route": 0.0}


class PlanTripOverrideTests(SimpleTestCase):
    """Custom mpg / max_range_miles must reach the optimizer intact.

    Regression test: the override branch once referenced the not-yet-assigned
    local ``max_range`` instead of the ``max_range_miles`` parameter, raising
    UnboundLocalError whenever a caller overrode the range.
    """

    def _run(self, **kwargs):
        station = _station("S1", 10.0, 3.0)
        with patch.object(planner_mod, "geocode",
                          side_effect=[(32.0, -96.0, "Dallas"),
                                       (41.0, -87.0, "Chicago")]), \
             patch.object(planner_mod, "get_route",
                          return_value={"distance_miles": 900.0,
                                        "duration_minutes": 800.0,
                                        "coordinates": [(-96.0, 32.0),
                                                        (-87.0, 41.0)]}), \
             patch.object(planner_mod, "stations_near_route",
                          return_value=[station]), \
             patch.object(planner_mod, "plan_fuel_stops",
                          return_value=[(station, 90.0)]) as mock_fuel:
            plan = plan_trip("Dallas,TX", "Chicago,IL", **kwargs)
        return plan, mock_fuel

    def test_defaults_reach_optimizer(self):
        _, mock_fuel = self._run()
        _, kwargs = mock_fuel.call_args
        self.assertEqual(kwargs["mpg"], 10)
        self.assertEqual(kwargs["max_range_miles"], 500)

    def test_custom_overrides_reach_optimizer(self):
        plan, mock_fuel = self._run(mpg=20, max_range_miles=400)
        _, kwargs = mock_fuel.call_args
        self.assertEqual(kwargs["mpg"], 20)
        self.assertEqual(kwargs["max_range_miles"], 400)
        self.assertEqual(plan["vehicle"]["mpg"], 20)
        self.assertEqual(plan["vehicle"]["max_range_miles"], 400)
        # tank_gallons derives from the overridden range/mpg, not defaults
        self.assertEqual(plan["vehicle"]["tank_gallons"], 20.0)
        self.assertEqual(plan["summary"]["num_stops"], 1)

    def test_cache_keys_with_spaces_raise_no_warning(self):
        # Queries like "New York,NY" must not produce cache keys with
        # characters that break memcached-style backends (CacheKeyWarning).
        station = _station("S1", 10.0, 3.0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", CacheKeyWarning)
            with patch.object(planner_mod, "geocode",
                              side_effect=[(40.7, -74.0, "New York"),
                                           (25.8, -80.2, "Miami")]), \
                 patch.object(planner_mod, "get_route",
                              return_value={"distance_miles": 900.0,
                                            "duration_minutes": 800.0,
                                            "coordinates": [(-74.0, 40.7),
                                                            (-80.2, 25.8)]}), \
                 patch.object(planner_mod, "stations_near_route",
                              return_value=[station]), \
                 patch.object(planner_mod, "plan_fuel_stops",
                              return_value=[(station, 90.0)]):
                plan = plan_trip("New York,NY", "Miami, FL")
        self.assertEqual(plan["summary"]["num_stops"], 1)

    def test_custom_mpg_changes_gallons_math(self):
        # 900 miles at 20 mpg -> 45 gallons total (not 90 at the default 10).
        from fuelrouter.services.optimizer import plan_fuel_stops as real
        stations = [_station("S1", 10.0, 3.0), _station("S2", 400.0, 2.5),
                    _station("S3", 700.0, 2.8)]
        stops = real(900.0, stations, mpg=20, max_range_miles=400)
        total = sum(g for _, g in stops)
        self.assertAlmostEqual(total, 45.0, places=6)
