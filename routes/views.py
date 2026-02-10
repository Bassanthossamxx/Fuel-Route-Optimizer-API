import math

from rest_framework.generics import ListAPIView
from .models import FuelStation
from .serializers import FuelStationSerializer , RoutePlanSerializer
from .pagination import FuelStationPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_spectacular.utils import extend_schema, OpenApiExample
from .services.openrouteservice import (
    geocode_place,
    get_route,
    is_within_us_bbox,
    build_state_corridor,
    state_code_to_full_name,
    simplify_geojson_linestring,
    encode_polyline,
)

class FuelStationListAPIView(ListAPIView):
    queryset = FuelStation.objects.all().order_by('id')
    serializer_class = FuelStationSerializer
    pagination_class = FuelStationPagination


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

            geometry = route.get("geometry")
            simplified_geometry = simplify_geojson_linestring(geometry, tolerance=0.01)
            encoded_polyline = None
            if geometry:
                if isinstance(geometry, str):
                    encoded_polyline = geometry
                elif isinstance(geometry, dict):
                    encoded_polyline = encode_polyline(geometry.get("coordinates", []))

            state_corridor = build_state_corridor(
                start_data.get("state"),
                end_data.get("state")
            )

            total_distance = route["summary"]["distance"]
            leg_count = max(1, math.ceil(total_distance / 500.0))
            fuel_stops = []
            total_cost = 0.0

            for leg_index in range(leg_count):
                leg_start = leg_index * 500.0
                leg_end = min(total_distance, (leg_index + 1) * 500.0)
                leg_distance = leg_end - leg_start

                leg_state = None
                if state_corridor:
                    leg_state = state_corridor[min(leg_index, len(state_corridor) - 1)]

                station = None
                if leg_state:
                    station = FuelStation.objects.filter(
                        state=leg_state
                    ).order_by("price_per_gallon").first()

                if not station and state_corridor:
                    station = FuelStation.objects.filter(
                        state__in=state_corridor
                    ).order_by("price_per_gallon").first()

                gallons = round(leg_distance / 10.0, 2)
                cost = None
                station_data = None

                if station:
                    price = float(station.price_per_gallon)
                    cost = round(gallons * price, 2)
                    total_cost += cost
                    station_data = FuelStationSerializer(station).data

                fuel_stops.append({
                    "segment_index": leg_index + 1,
                    "segment_distance_miles": round(leg_distance, 2),
                    "station": station_data,
                    "gallons_purchased": gallons,
                    "cost": cost,
                })

            customer_stops = []
            stops_explained = []
            miles_so_far = 0.0
            for stop in fuel_stops:
                miles_so_far += stop["segment_distance_miles"]
                station_info = stop.get("station") or {}
                station_state = station_info.get("state")
                state_name = state_code_to_full_name(station_state) or "N/A"
                station_name = station_info.get("station_name", "No station available")
                cost_value = stop.get("cost") if stop.get("cost") is not None else "N/A"
                gallons_value = stop.get("gallons_purchased")

                customer_stops.append(
                    "After {miles:.2f} miles: {state}, {name} ($ {cost})".format(
                        miles=miles_so_far,
                        state=state_name,
                        name=station_name,
                        cost=cost_value,
                    )
                )

                stops_explained.append(
                    "Drive {miles:.2f} miles, stop in {state} at {name}, buy {gallons} gallons for $ {cost}."
                    .format(
                        miles=stop["segment_distance_miles"],
                        state=state_name,
                        name=station_name,
                        gallons=gallons_value,
                        cost=cost_value,
                    )
                )

            state_movement = " > ".join(
                [name for name in (
                    state_code_to_full_name(state_code) for state_code in state_corridor
                ) if name]
            )

            return Response({
                "start": start_text,
                "end": end_text,
                "state_movement": state_movement,
                "distance_miles": round(route["summary"]["distance"], 2),
                "customer_summary": {
                    "total_fuel_cost": round(total_cost, 2),
                    "stops": customer_stops,
                },
                "fuel_plan_summary": {
                    "total_distance_miles": round(total_distance, 2),
                    "max_range_miles": 500,
                    "mpg": 10,
                    "total_gallons": round(total_distance / 10.0, 2),
                    "total_fuel_cost": round(total_cost, 2),
                    "stops_explained": stops_explained,
                },
                "fuel_stops": fuel_stops,
                "route_geometry_polyline": encoded_polyline
            })

        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
