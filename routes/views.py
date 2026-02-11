"""
Routes Views Module

This module contains API endpoints for:
1. Listing fuel stations with pagination
2. Planning optimal routes with fuel stops (USA only)

Assignment Requirements:
- Vehicle range: 500 miles maximum
- Fuel efficiency: 10 MPG
- Single API call to routing service
- Cost-effective fuel stop selection
"""

import math
import logging
import requests

from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_spectacular.utils import extend_schema, OpenApiExample

from .models import FuelStation
from .serializers import FuelStationSerializer, RoutePlanSerializer
from .pagination import FuelStationPagination
from .services.openrouteservice import (
    geocode_place,               # Convert "New York, NY" → coordinates
    get_route,                   # Get route data from OpenRouteService
    is_inside_usa,               # Validate coordinates are in USA
    build_state_corridor,        # Create state-by-state path
    state_code_to_full_name,     # NY → NEW YORK
    simplify_geojson_linestring, # Reduce coordinate count for response
    decode_polyline,             # Decompress polyline → GeoJSON
)

# Initialize logger for debugging and monitoring
logger = logging.getLogger(__name__)

class FuelStationListAPIView(ListAPIView):
    """
    GET /api/stations/
    
    Returns paginated list of all fuel stations in database.
    Loaded from fuel-prices.csv (6,732 stations across USA).
    """
    queryset = FuelStation.objects.all().order_by('id')
    serializer_class = FuelStationSerializer
    pagination_class = FuelStationPagination


class RoutePlanAPIView(APIView):
    """
    POST /api/route/
    
    Plan optimal driving route with cost-effective fuel stops.
    
    Vehicle Specifications:
    - Maximum range: 500 miles per tank
    - Fuel efficiency: 10 MPG (miles per gallon)
    - Tank capacity: 50 gallons
    
    Geographic Restrictions:
    - USA locations only (validated via bounding box)
    
    Optimization Strategy:
    - Minimize total fuel cost
    - Select cheapest station in each state along route
    - Respect 500-mile range constraint
    
    API Usage:
    - Single routing API call (OpenRouteService)
    - Geocoding calls for start/end locations
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
        """
        Process route planning request.
        
        Flow:
        1. Validate input (start/end locations)
        2. Geocode locations to coordinates
        3. Verify USA-only requirement
        4. Fetch route (SINGLE API CALL - key requirement!)
        5. Calculate fuel stops every 500 miles
        6. Find cheapest station in each state
        7. Return comprehensive response with GeoJSON map data
        """
        # Validate Request
        serializer = RoutePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_text = serializer.validated_data["start"]
        end_text = serializer.validated_data["end"]

        try:
            #  Geocode Start and End Locations 
            # Convert text like "New York, NY" → [longitude, latitude]
            start_data = geocode_place(start_text)
            end_data = geocode_place(end_text)

            # Enforce USA-Only Rule
            if start_data["country_code"] != "US" or not is_inside_usa(start_data["coords"]):
                return Response(
                    {"error": "Start location must be inside the USA"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if end_data["country_code"] != "US" or not is_inside_usa(end_data["coords"]):
                return Response(
                    {"error": "End location must be inside the USA"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Fetch Route (SINGLE API CALL)
            # This is the ONLY routing API call we make (requirement: minimize API calls)
            route = get_route(
                start_data["coords"],
                end_data["coords"]
            )

            # 
            # Process Geometry for Map Display
            # OpenRouteService returns encoded polyline string (compressed coordinates)
            # We need to decode it to GeoJSON format for map libraries (Leaflet/Mapbox)
            geometry = route.get("geometry")
            route_geojson = None
            
            if geometry:
                if isinstance(geometry, dict):
                    # Case 1: Geometry is already GeoJSON format (dict with "type" and "coordinates")
                    # Skip simplification for speed - map libraries can handle it
                    route_geojson = geometry
                    
                elif isinstance(geometry, str):
                    # Case 2: Geometry is encoded polyline string (most common from OpenRouteService)
                    # Example: "m{hwFtlnbME?eALOB..." → [[lon, lat], [lon, lat], ...]
                    decoded_coords = decode_polyline(geometry)
                    
                    # Create GeoJSON LineString from decoded coordinates
                    route_geojson = {
                        "type": "LineString",
                        "coordinates": decoded_coords  # [[lon, lat], [lon, lat], ...]
                    }

            # Build State Corridor
            # Create path through states using BFS algorithm
            state_corridor = build_state_corridor(
                start_data.get("state"),
                end_data.get("state")
            )

            # Extract Route Summary Data
            total_distance = route["summary"]["distance"]  # in miles
            duration_seconds = route["summary"].get("duration", 0)
            duration_hours = round(duration_seconds / 3600.0, 2) if duration_seconds else None
            
            # Calculate Fuel Stops
            # Vehicle range: 500 miles, so divide route into 500-mile segments
            leg_count = max(1, math.ceil(total_distance / 500.0))
            fuel_stops = []
            total_cost = 0.0

            # Fetch all cheapest stations in ONE query with only needed fields
            cheapest_stations = {}
            if state_corridor:
                corridor_stations = FuelStation.objects.filter(
                    state__in=state_corridor
                ).values('state', 'station_name', 'address', 'city', 'price_per_gallon').order_by('state', 'price_per_gallon')
                
                # Build dictionary: state -> cheapest station (as dict, not model instance)
                for station in corridor_stations:
                    if station['state'] not in cheapest_stations:
                        cheapest_stations[station['state']] = station

            # Cache state name conversions to avoid repeated function calls
            state_name_cache = {s: state_code_to_full_name(s) for s in state_corridor}

            # Loop through each 500-mile segment
            for leg_index in range(leg_count):
                # Calculate segment boundaries
                leg_start = leg_index * 500.0
                leg_end = min(total_distance, (leg_index + 1) * 500.0)  # Don't exceed total distance
                leg_distance = leg_end - leg_start

                # Determine which state this segment is in
                leg_state = None
                if state_corridor:
                    # Map segment to state in corridor (prevent index out of bounds)
                    leg_state = state_corridor[min(leg_index, len(state_corridor) - 1)]

                # Find Cheapest Station from pre-fetched dictionary
                station = cheapest_stations.get(leg_state) if leg_state else None
                
                # Fallback: Use any station from corridor if specific state not found
                if not station and cheapest_stations:
                    station = next(iter(cheapest_stations.values()))

                # Calculate Fuel Cost
                # Vehicle efficiency: 10 MPG
                gallons = round(leg_distance / 10.0, 2)
                cost = None
                station_data = None

                if station:
                    price = float(station['price_per_gallon'])
                    cost = round(gallons * price, 2)  # gallons × price = total cost
                    total_cost += cost
                    # Manual dict creation (10x faster than serializer)
                    station_data = {
                        'state': station['state'],
                        'station_name': station['station_name'],
                        'address': station['address'],
                        'city': station['city'],
                        'price_per_gallon': str(price)
                    }

                # Store fuel stop details
                fuel_stops.append({
                    "segment_index": leg_index + 1,
                    "segment_distance_miles": round(leg_distance, 2),
                    "station": station_data,
                    "gallons_purchased": gallons,
                    "cost": cost,
                })

            # Format Response Data 
            # Generate both summaries in single loop (faster than 2 separate loops)
            customer_stops = []
            stops_explained = []
            miles_so_far = 0.0
            
            for stop in fuel_stops:
                miles_so_far += stop["segment_distance_miles"]
                station_info = stop.get("station") or {}
                state_name = state_name_cache.get(station_info.get("state"), "N/A")
                station_name = station_info.get("station_name", "N/A")
                cost_val = stop.get("cost", "N/A")
                gallons_val = stop.get("gallons_purchased", 0)
                segment_miles = stop["segment_distance_miles"]
                
                # Use f-strings (faster than .format())
                customer_stops.append(
                    f"After {miles_so_far:.0f} mi: {state_name}, {station_name} (${cost_val})"
                )
                stops_explained.append(
                    f"Drive {segment_miles:.2f} miles, stop in {state_name} at {station_name}, buy {gallons_val} gallons for ${cost_val}."
                )

            # Convert state codes to full names (use cached lookups)
            state_movement = " > ".join(state_name_cache.get(s, s) for s in state_corridor)

            #  Build Comprehensive Response
            response_data = {
                "route_summary": {
                    "start_location": start_text,
                    "end_location": end_text,
                    "total_distance_miles": round(total_distance, 2),
                    "estimated_duration_hours": duration_hours,
                    "states_traveled": state_movement,
                    "number_of_fuel_stops": leg_count,
                },
                "fuel_cost_summary": {
                    "total_fuel_cost_usd": round(total_cost, 2),
                    "total_gallons_needed": round(total_distance / 10.0, 2),
                    "vehicle_mpg": 10,
                    "max_range_miles": 500,
                    "fuel_stops_breakdown": customer_stops,
                },
                "detailed_fuel_stops": fuel_stops,
                "route_plan_explanation": stops_explained,
                "map_data": {
                    "route_geojson": route_geojson
                }
            }
            
            return Response(response_data)
        
        except ValueError as ve:
            return Response(
                {"error": str(ve), "type": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except requests.exceptions.RequestException as re:
            return Response(
                {"error": "Failed to fetch routing data", "details": str(re)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
        except Exception as exc:
            logger.error(f"Error: {str(exc)}")
            return Response(
                {"error": "An unexpected error occurred", "details": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
