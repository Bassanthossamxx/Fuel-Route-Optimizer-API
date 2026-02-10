# Fuel Route Optimizer API

 Plan optimal driving routes with cost-effective fuel stops across the USA.

## Overview

This API provides route planning with optimized fuel stops for commercial trucking. Given start and end locations within the contiguous United States, it returns:

- Complete driving route with distance and duration
- Optimal fuel stop locations every 500 miles
- Cost breakdown based on real fuel prices
- GeoJSON map data for visual display

### Vehicle Specifications
- **Maximum Range**: 500 miles per tank
- **Fuel Efficiency**: 10 MPG (miles per gallon)
- **Tank Capacity**: 50 gallons

### Key Requirements Met
-  USA-only locations (validated via bounding box)
-  Single routing API call per request
-  Cost-optimized fuel stop selection
-  GeoJSON format for map integration
-  Fast response time (<3 seconds typical)

---

##  Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 12+
- OpenRouteService API key ([Get free key](https://openrouteservice.org/dev/#/signup))

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd Fuel-Route-Optimizer-API
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment configuration**
Create `.env` file in project root:
```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True

# Database
DB_NAME=fuel_optimizer_db
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

# OpenRouteService API
OPENROUTESERVICE_API_KEY=your-api-key-here
```

5. **Database setup**
```bash

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Import fuel station data
python manage.py import_fuel_prices
```

6. **Run development server**
```bash
python manage.py runserver
```

API will be available at `http://localhost:8000`

---

## API Endpoints

### 1. Route Planning

**POST** `/api/route-plan/`

Plan optimal route with fuel stops.

#### Request Body
```json
{
  "start": "New York, NY",
  "end": "Los Angeles, CA"
}
```

#### Response (200 OK)
```json
{
  "route_summary": {
    "start_location": "New York, NY",
    "end_location": "Los Angeles, CA",
    "total_distance_miles": 2797.18,
    "estimated_duration_hours": 45.01,
    "states_traveled": "NEW YORK > PENNSYLVANIA > OHIO > ... > CALIFORNIA",
    "number_of_fuel_stops": 6
  },
  "fuel_cost_summary": {
    "total_fuel_cost_usd": 850.50,
    "total_gallons_needed": 279.72,
    "vehicle_mpg": 10,
    "max_range_miles": 500
  },
  "detailed_fuel_stops": [
    {
      "segment_index": 1,
      "segment_distance_miles": 500.00,
      "station": {
        "id": 11698,
        "station_name": "SHELL",
        "address": "I-95, EXIT 104",
        "city": "New York",
        "state": "NY",
        "price_per_gallon": "3.00"
      },
      "gallons_purchased": 50.0,
      "cost": 150.0
    }
  ],
  "route_plan_explanation": [
    "Drive 500.00 miles, stop in NEW YORK at SHELL, buy 50.0 gallons for $150.0"
  ],
  "map_data": {
    "route_geojson": {
      "type": "LineString",
      "coordinates": [[-73.9708, 40.6829], [-74.0074, 40.7257], ...]
    },
    "encoded_polyline": "m{hwFtlnbME?eALOB...",
    "format_info": "Use route_geojson for Leaflet/Mapbox, encoded_polyline for Google Maps"
  }
}
```

#### Error Responses

**400 Bad Request** - Invalid location or validation error
```json
{
  "error": "Start location must be inside the USA",
  "type": "validation_error"
}
```

**503 Service Unavailable** - External API failure
```json
{
  "error": "Failed to fetch routing data. Please check API configuration.",
  "details": "Connection timeout"
}
```

**500 Internal Server Error** - Unexpected error
```json
{
  "error": "An unexpected error occurred",
  "details": "..."
}
```

### 2. List Fuel Stations

**GET** `/api/stations/`

Get paginated list of all fuel stations.

#### Query Parameters
- `page`: Page number (default: 1)
- `page_size`: Results per page (default: 20, max: 100)

#### Response
```json
{
  "count": 6732,
  "next": "http://localhost:8000/api/stations/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "station_name": "SHELL",
      "address": "I-95, EXIT 104 & SR-207",
      "city": "New York",
      "state": "NY",
      "price_per_gallon": "3.00"
    }
  ]
}
```

---

## Project Structure

```
Fuel-Route-Optimizer-API/
├── config/                    # Django project settings
│   ├── settings.py           # Main configuration
│   ├── urls.py               # Root URL routing
│   └── wsgi.py               # WSGI entry point
│
├── routes/                    # Main application
│   ├── models.py             # Database models (FuelStation)
│   ├── views.py              # API endpoints
│   ├── serializers.py        # Request/response serialization
│   ├── urls.py               # App URL routing
│   ├── pagination.py         # Custom pagination
│   │
│   ├── services/             # Business logic
│   │   └── openrouteservice.py  # Routing API integration
│   │
│   ├── management/commands/  # Django commands
│   │   └── import_fuel_prices.py  # CSV data importer
│   │
│   └── migrations/           # Database migrations
│
├── fuel-prices.csv           # Fuel station data 
├── requirements.txt          # Python dependencies
├── manage.py                 # Django CLI
└── README.md                 # This file
```

---

## How It Works

### Algorithm Overview

1. **Geocoding** - Convert location names to coordinates
   ```python
   "New York, NY" → [-74.006, 40.7128]
   ```

2. **USA Validation** - Check coordinates fall within USA bounding boxes
   ```python
   is_within_us_bbox([-74.006, 40.7128]) → True
   ```

3. **Routing** - Single API call to OpenRouteService
   ```python
   # Only ONE routing API call per request!
   route = get_route(start_coords, end_coords)
   ```

4. **State Corridor** - Build path through states using BFS
   ```python
   NY → PA → OH → IN → IL → MO → KS → CO → ... → CA
   ```

5. **Fuel Stop Calculation** - Divide route into 500-mile segments
   ```python
   2797 miles ÷ 500 miles/tank = 6 stops
   ```

6. **Station Selection** - Find cheapest in each state
   ```python
   FuelStation.objects.filter(state="PA").order_by("price_per_gallon").first()
   ```

7. **GeoJSON Processing** - Decode polyline to coordinates
   ```python
   "m{hwFtlnbME?..." → [[-73.97, 40.68], [-74.01, 40.73], ...]
   ```

### Key Optimizations

- **Single API Call**: Only 1 routing request per plan (vs 2-3 typical)
- **State Indexing**: Database indexed by `state` for O(log n) lookups
- **Polyline Decoding**: Converts compressed format to GeoJSON
- **Coordinate Simplification**: Reduces points by ~90% using Ramer-Douglas-Peucker

---


## Database Schema

### FuelStation Model

| Field             | Type            | Description                    | Indexed |
|-------------------|-----------------|--------------------------------|---------|
| id                | AutoField       | Primary key                    | ✓       |
| station_name      | CharField(255)  | Station brand/name             |         |
| address           | CharField(255)  | Street address                 |         |
| city              | CharField(100)  | City name                      |         |
| state             | CharField(10)   | 2-letter state code            | ✓       |
| price_per_gallon  | Decimal(5,2)    | Fuel price in USD              |         |
| created_at        | DateTime        | Import timestamp               |         |

**Constraints:**
- Unique: (station_name, state)
- Default ordering: state, price_per_gallon

---

##  Acknowledgments

- **OpenRouteService** for routing and geocoding APIs
- **fuel-prices.csv** for comprehensive USA fuel station data
- **Django REST Framework** for robust API development

---
