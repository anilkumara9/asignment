"""Unit tests for geometry helpers (no network)."""

from django.test import SimpleTestCase

from fuelrouter.services.geo import cumulative_miles, haversine_miles, simplify_polyline


class GeoTests(SimpleTestCase):
    def test_haversine_nyc_to_la(self):
        d = haversine_miles(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertGreater(d, 2440)
        self.assertLess(d, 2450)

    def test_haversine_zero(self):
        self.assertAlmostEqual(haversine_miles(40.0, -100.0, 40.0, -100.0), 0.0)

    def test_cumulative_miles(self):
        # 1 degree of latitude ~= 69 miles
        cum = cumulative_miles([(0.0, 40.0), (0.0, 41.0), (0.0, 42.0)])
        self.assertAlmostEqual(cum[0], 0.0)
        self.assertAlmostEqual(cum[1], 69.0, delta=0.5)
        self.assertAlmostEqual(cum[2], 138.0, delta=1.0)

    def test_simplify_straight_line(self):
        line = [(float(i), 0.0) for i in range(100)]
        self.assertEqual(len(simplify_polyline(line, 0.01)), 2)

    def test_simplify_keeps_endpoints_and_shape(self):
        # A "V" shape: the corner must survive simplification.
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 1.0), (3.0, 0.0), (4.0, 0.0)]
        out = simplify_polyline(pts, 0.01)
        self.assertEqual(out[0], (0.0, 0.0))
        self.assertEqual(out[-1], (4.0, 0.0))
        self.assertIn((2.0, 1.0), out)
