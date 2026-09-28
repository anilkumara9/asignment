"""HTTP layer: JSON API + interactive map page."""

from django.shortcuts import render
from django.views import View
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.planner import PlanningError, plan_trip


def _parse_params(request):
    """Accept params from query string (GET) or JSON body (POST)."""
    if request.method == "POST":
        data = request.data if isinstance(request.data, dict) else {}
    else:
        data = request.query_params
    start = (data.get("start") or "").strip()
    finish = (data.get("finish") or "").strip()

    def _float(key):
        try:
            return float(data.get(key)) if data.get(key) is not None else None
        except (TypeError, ValueError):
            return None

    return start, finish, _float("mpg"), _float("max_range_miles")


class RoutePlanView(APIView):
    """GET /api/route/?start=Dallas,TX&finish=Chicago,IL
    POST /api/route/  {"start": "...", "finish": "..."}
    """

    def _handle(self, request):
        start, finish, mpg, max_range = _parse_params(request)
        if not start or not finish:
            return Response(
                {"error": "Both 'start' and 'finish' locations are required, "
                          "e.g. ?start=Dallas,TX&finish=Chicago,IL."},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
