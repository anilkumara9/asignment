"""API view tests with the planner mocked out (no network)."""

import json
from unittest.mock import patch

from django.test import SimpleTestCase

import fuelrouter.views as views_mod
from fuelrouter.services.planner import PlanningError

CANNED_PLAN = {
    "start": {"query": "Dallas,TX", "display_name": "Dallas, TX, USA",
              "lat": 32.78, "lng": -96.80},
    "finish": {"query": "Chicago,IL", "display_name": "Chicago, IL, USA",
               "lat": 41.88, "lng": -87.63},
    "route": {"distance_miles": 925.0, "duration_minutes": 830.0,
              "geometry": [[-96.8, 32.78], [-87.63, 41.88]]},
    "vehicle": {"mpg": 10, "max_range_miles": 500, "tank_gallons": 50.0},
    "fuel_stops": [],
    "summary": {"num_stops": 0, "total_gallons": 92.5,
                "total_cost_usd": 300.0, "avg_price_per_gallon_usd": 3.243},
    "map_path": "/map/?start=Dallas%2CTX&finish=Chicago%2CIL",
    "notes": [],
}


class RoutePlanViewTests(SimpleTestCase):
    @patch.object(views_mod, "plan_trip", return_value=dict(CANNED_PLAN))
    def test_get_returns_plan_with_absolute_map_url(self, mock_plan):
        resp = self.client.get("/api/route/?start=Dallas,TX&finish=Chicago,IL")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data["summary"]["total_cost_usd"], 300.0)
        self.assertTrue(
            data["map_url"].startswith("http://testserver/map/?"),
            data["map_url"],
        )
        self.assertNotIn("map_path", data)

    @patch.object(views_mod, "plan_trip", return_value=dict(CANNED_PLAN))
    def test_post_with_json_body(self, mock_plan):
        resp = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Dallas,TX", "finish": "Chicago,IL"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_missing_params_returns_400(self):
        resp = self.client.get("/api/route/?start=Dallas,TX")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", json.loads(resp.content))

    @patch.object(views_mod, "plan_trip",
                  side_effect=PlanningError("Could not find 'X' inside the USA."))
    def test_planning_error_returns_422(self, mock_plan):
        resp = self.client.get("/api/route/?start=X&finish=Y")
        self.assertEqual(resp.status_code, 422)
        self.assertIn("USA", json.loads(resp.content)["error"])


class MapViewTests(SimpleTestCase):
    @patch.object(views_mod, "plan_trip", return_value=dict(CANNED_PLAN))
    def test_map_page_renders(self, mock_plan):
        resp = self.client.get("/map/?start=Dallas,TX&finish=Chicago,IL")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"leaflet", resp.content.lower())

    def test_map_missing_params_returns_400(self):
        resp = self.client.get("/map/?start=Dallas,TX")
        self.assertEqual(resp.status_code, 400)
