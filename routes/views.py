from rest_framework.generics import ListAPIView
from .models import FuelStation
from .serializers import FuelStationSerializer
from .pagination import FuelStationPagination


class FuelStationListAPIView(ListAPIView):
    queryset = FuelStation.objects.all().order_by('id')
    serializer_class = FuelStationSerializer
    pagination_class = FuelStationPagination

