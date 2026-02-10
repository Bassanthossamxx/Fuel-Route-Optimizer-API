from rest_framework import serializers
from .models import FuelStation


class FuelStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelStation
        fields = [
            'id',
            'station_name',
            'address',
            'city',
            'state',
            'price_per_gallon',
        ]

class RoutePlanSerializer(serializers.Serializer):
    start = serializers.CharField(
        help_text="Start location (must be inside the USA)",
    )
    end = serializers.CharField(
        help_text="End location (must be inside the USA)",
    )
