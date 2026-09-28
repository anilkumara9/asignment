from django.urls import path

from .views import MapView, RoutePlanView

urlpatterns = [
    path("api/route/", RoutePlanView.as_view(), name="route-plan"),
    path("map/", MapView.as_view(), name="map"),
]
