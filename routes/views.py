from rest_framework.generics import ListAPIView
from .models import FuelStation
from .serializers import FuelStationSerializer , RoutePlanSerializer
from .pagination import FuelStationPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_spectacular.utils import extend_schema, OpenApiExample
from .services.openrouteservice import geocode_place, get_route, is_within_us_bbox, build_state_corridor

class FuelStationListAPIView(ListAPIView):
    queryset = FuelStation.objects.all().order_by('id')
    serializer_class = FuelStationSerializer
    pagination_class = FuelStationPagination



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_spectacular.utils import extend_schema, OpenApiExample

from .serializers import RoutePlanSerializer
from .services.openrouteservice import geocode_place, get_route


class RoutePlanAPIView(APIView):
    """
    Route planning endpoint (USA only).
    """

    @extend_schema(
        request=RoutePlanSerializer,
        responses={200: dict, 400: dict},
        description=(
            "Accepts start and end locations inside the USA and "
            "returns route distance and geometry."
        ),
        examples=[
            OpenApiExample(
                "Valid request",
                value={
                    "start": "New York, NY",
                    "end": "Los Angeles, CA"
                },
                request_only=True,
            ),
        ],
        tags=["Route Planning"],
    )
    def post(self, request):
        serializer = RoutePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_text = serializer.validated_data["start"]
        end_text = serializer.validated_data["end"]

        try:
            # 1️⃣ Geocode inputs
            start_data = geocode_place(start_text)
            end_data = geocode_place(end_text)

            # 2️⃣ Enforce USA-only rule
            if start_data["country_code"] != "US" or not is_within_us_bbox(start_data["coords"]):
                return Response(
                    {"error": "Start location must be inside the USA"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if end_data["country_code"] != "US" or not is_within_us_bbox(end_data["coords"]):
                return Response(
                    {"error": "End location must be inside the USA"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 3️⃣ One routing API call
            route = get_route(
                start_data["coords"],
                end_data["coords"]
            )

            state_corridor = build_state_corridor(
                start_data.get("state"),
                end_data.get("state")
            )

            return Response({
                "start": start_text,
                "end": end_text,
                "states_list_inside_start_to_end": state_corridor,
                "distance_miles": round(route["summary"]["distance"], 2),
                "route_geometry": route["geometry"],
            })

        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
