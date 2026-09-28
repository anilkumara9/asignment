"""HTTP layer: JSON API + interactive map page."""

import math

from django.shortcuts import render
from django.views import View
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.planner import PlanningError, plan_trip

# Sanity bounds for the optional numeric overrides (defense against typos
# like mpg=0.1 or max_range_miles=1e12, which would otherwise produce absurd
# but "valid" plans).
_MPG_MIN, _MPG_MAX = 1, 1000
_RANGE_MIN, _RANGE_MAX = 1, 100_000


def _parse_params(request):
    """Accept params from query string (GET) or JSON body (POST).

    Returns (start, finish, mpg, max_range_miles, errors); ``errors`` lists
    human-readable problems with the optional numeric overrides.
    """
    if request.method == "POST":
        data = request.data if isinstance(request.data, dict) else {}
    else:
        data = request.query_params
    start = (data.get("start") or "").strip()
    finish = (data.get("finish") or "").strip()

    errors = []

    def _float(key, lo, hi, unit):
        raw = data.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return None
        try:
            val = float(raw)
        except (TypeError, ValueError):
            errors.append(
                f"'{key}' must be a number (e.g. ?{key}=10), got {raw!r}.")
            return None
        if not math.isfinite(val) or not lo <= val <= hi:
            errors.append(
                f"'{key}' must be between {lo:g} and {hi:g} {unit}, "
                f"got {raw!r}.")
            return None
        return val

    mpg = _float("mpg", _MPG_MIN, _MPG_MAX, "miles per gallon")
    max_range = _float("max_range_miles", _RANGE_MIN, _RANGE_MAX, "miles")
    return start, finish, mpg, max_range, errors


class RoutePlanView(APIView):
    """GET /api/route/?start=Dallas,TX&finish=Chicago,IL
    POST /api/route/  {"start": "...", "finish": "..."}
    """

    def _handle(self, request):
        start, finish, mpg, max_range, errors = _parse_params(request)
        if not start or not finish:
            return Response(
                {"error": "Both 'start' and 'finish' locations are required, "
                          "e.g. ?start=Dallas,TX&finish=Chicago,IL."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if errors:
            return Response({"error": " ".join(errors)},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            plan = plan_trip(start, finish, mpg=mpg, max_range_miles=max_range)
        except PlanningError as exc:
            return Response({"error": str(exc)},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        plan = dict(plan)
        plan["map_url"] = request.build_absolute_uri(plan.pop("map_path"))
        return Response(plan)

    def get(self, request):
        return self._handle(request)

    def post(self, request):
        return self._handle(request)


class MapView(View):
    """GET /map/?start=...&finish=... — interactive Leaflet map of the plan."""

    def get(self, request):
        start = (request.GET.get("start") or "").strip()
        finish = (request.GET.get("finish") or "").strip()
        if not start or not finish:
            return render(request, "fuelrouter/map_error.html",
                          {"error": "Provide ?start= and ?finish=, e.g. "
                                    "/map/?start=Dallas,TX&finish=Chicago,IL"},
                          status=400)
        try:
            plan = plan_trip(start, finish)
        except PlanningError as exc:
            return render(request, "fuelrouter/map_error.html",
                          {"error": str(exc)}, status=422)
        return render(request, "fuelrouter/map.html", {"plan": plan})
