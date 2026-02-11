from django.urls import path
from .views import FuelStationListAPIView , RoutePlanAPIView

urlpatterns = [
    path('stations/', FuelStationListAPIView.as_view(), name='fuel-stations'),
    path('route/', RoutePlanAPIView.as_view(), name='route-plan'),
]
