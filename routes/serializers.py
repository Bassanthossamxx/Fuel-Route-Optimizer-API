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
