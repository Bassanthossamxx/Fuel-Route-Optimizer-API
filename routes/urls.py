from django.urls import path
from .views import FuelStationListAPIView

urlpatterns = [
    path('stations/', FuelStationListAPIView.as_view(), name='fuel-stations'),
]
