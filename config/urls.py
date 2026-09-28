"""URL configuration for config project."""
from django.http import JsonResponse
from django.urls import include, path


def index(request):
    return JsonResponse(
        {
            "service": "Spotter fuel-route API (coding assessment)",
            "plan_a_trip": "/api/route/?start=Dallas,TX&finish=Chicago,IL",
            "map": "/map/?start=Dallas,TX&finish=Chicago,IL",
        }
    )


urlpatterns = [
    path("", index),
    path("", include("fuelrouter.urls")),
]
