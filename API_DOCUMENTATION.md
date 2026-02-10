# API Documentation

Complete reference for the Fuel Route Optimizer API endpoints.

## Base URL

```
http://localhost:8000/api
```

For production, replace `localhost:8000` with your deployed domain.

---

## Authentication

Currently, the API does not require authentication. For production deployment, consider adding:
- API key authentication
- JWT tokens
- Rate limiting per IP/user

---

## Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/route-plan/` | Plan route with fuel stops | No |
| GET | `/api/stations/` | List all fuel stations | No |
| GET | `/api/stations/?page=2` | Paginated fuel stations | No |

---

## 1. Route Planning

### POST `/api/route-plan/`

Calculate optimal driving route with cost-effective fuel stops.

#### Request Headers
```http
Content-Type: application/json
```

#### Request Body

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| start | string | Yes | Starting location (city, state) | "New York, NY" |
| end | string | Yes | Ending location (city, state) | "Los Angeles, CA" |

**JSON Schema:**
```json
{
  "type": "object",
  "properties": {
    "start": {
      "type": "string",
      "description": "Starting location within USA",
      "example": "New York, NY"
    },
    "end": {
      "type": "string",
      "description": "Ending location within USA",
      "example": "Los Angeles, CA"
    }
  },
  "required": ["start", "end"]
}
```

#### Success Response (200 OK)

**Response Structure:**

```json
{
  "route_summary": {
    "start_location": "string",
    "end_location": "string",
    "total_distance_miles": "number",
    "estimated_duration_hours": "number",
    "states_traveled": "string",
    "number_of_fuel_stops": "integer"
  },
  "fuel_cost_summary": {
    "total_fuel_cost_usd": "number",
    "total_gallons_needed": "number",
    "vehicle_mpg": "integer",
    "max_range_miles": "integer",
    "fuel_stops_breakdown": ["string"]
  },
  "detailed_fuel_stops": [
    {
      "segment_index": "integer",
      "segment_distance_miles": "number",
      "station": {
        "id": "integer",
        "station_name": "string",
        "address": "string",
        "city": "string",
        "state": "string",
        "price_per_gallon": "string"
      },
      "gallons_purchased": "number",
      "cost": "number"
    }
  ],
  "route_plan_explanation": ["string"],
  "map_data": {
    "route_geojson": {
      "type": "LineString",
      "coordinates": [["number", "number"]]
    },
    "encoded_polyline": "string",
    "format_info": "string"
  }
}
```

**Example Response:**

```json
{
  "route_summary": {
    "start_location": "New York, NY",
    "end_location": "Philadelphia, PA",
    "total_distance_miles": 100.55,
    "estimated_duration_hours": 1.68,
    "states_traveled": "NEW YORK > NEW JERSEY > PENNSYLVANIA",
    "number_of_fuel_stops": 1
  },
  "fuel_cost_summary": {
    "total_fuel_cost_usd": 30.15,
    "total_gallons_needed": 10.06,
    "vehicle_mpg": 10,
    "max_range_miles": 500,
    "fuel_stops_breakdown": [
      "After 100.55 miles: NEW YORK, SHELL ($ 30.15)"
    ]
  },
  "detailed_fuel_stops": [
    {
      "segment_index": 1,
      "segment_distance_miles": 100.55,
      "station": {
        "id": 11698,
        "station_name": "SHELL",
        "address": "I-95, EXIT 104 & SR-207",
        "city": "New York",
        "state": "NY",
        "price_per_gallon": "3.00"
      },
      "gallons_purchased": 10.06,
      "cost": 30.15
    }
  ],
  "route_plan_explanation": [
    "Drive 100.55 miles, stop in NEW YORK at SHELL, buy 10.06 gallons for $ 30.15."
  ],
  "map_data": {
    "route_geojson": {
      "type": "LineString",
      "coordinates": [
        [-73.97083, 40.68295],
        [-74.00745, 40.7257],
        [-74.06492, 40.73958]
      ]
    },
    "encoded_polyline": "m{hwFtlnbME?eALOB...",
    "format_info": "Use route_geojson for Leaflet/Mapbox, encoded_polyline for Google Maps"
  }
}
```

#### Error Responses

**400 Bad Request** - Validation error

```json
{
  "error": "Start location must be inside the USA",
  "type": "validation_error"
}
```

**Possible validation errors:**
- `"Start location must be inside the USA"`
- `"End location must be inside the USA"`
- `"Could not geocode location: [location]"`
- `"Invalid request format"`

---

**503 Service Unavailable** - External API failure

```json
{
  "error": "Failed to fetch routing data. Please check API configuration.",
  "details": "Connection timeout to OpenRouteService"
}
```

**Common causes:**
- OpenRouteService API down
- Invalid API key
- Rate limit exceeded (40 requests/minute)
- Network timeout

---

**500 Internal Server Error** - Unexpected server error

```json
{
  "error": "An unexpected error occurred",
  "details": "Database connection failed"
}
```

---

### cURL Examples

**Basic request:**
```bash
curl -X POST http://localhost:8000/api/route-plan/ \
  -H "Content-Type: application/json" \
  -d '{
    "start": "New York, NY",
    "end": "Philadelphia, PA"
  }'
```

**Long-distance route:**
```bash
curl -X POST http://localhost:8000/api/route-plan/ \
  -H "Content-Type: application/json" \
  -d '{
    "start": "New York, NY",
    "end": "Los Angeles, CA"
  }'
```

**With jq for pretty output:**
```bash
curl -X POST http://localhost:8000/api/route-plan/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Boston, MA", "end": "Miami, FL"}' \
  | jq '.'
```

---

## 2. List Fuel Stations

### GET `/api/stations/`

Retrieve paginated list of all fuel stations in database.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| page | integer | No | 1 | Page number |
| page_size | integer | No | 20 | Results per page (max: 100) |

#### Success Response (200 OK)

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
    },
    {
      "id": 2,
      "station_name": "EXXON",
      "address": "US-1 & SR-11",
      "city": "Newark",
      "state": "NJ",
      "price_per_gallon": "3.15"
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| count | integer | Total number of stations |
| next | string/null | URL for next page |
| previous | string/null | URL for previous page |
| results | array | Array of fuel station objects |

#### Fuel Station Object

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique station identifier |
| station_name | string | Station brand/name |
| address | string | Street address |
| city | string | City name |
| state | string | 2-letter state code |
| price_per_gallon | string | Fuel price in USD |

---

### cURL Examples

**Get first page (default 20 results):**
```bash
curl http://localhost:8000/api/stations/
```

**Get specific page:**
```bash
curl http://localhost:8000/api/stations/?page=5
```

**Custom page size:**
```bash
curl http://localhost:8000/api/stations/?page_size=50
```

**Maximum results per page:**
```bash
curl http://localhost:8000/api/stations/?page_size=100
```

---

## Response Field Reference

### route_summary Object

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| start_location | string | Starting location name | "New York, NY" |
| end_location | string | Ending location name | "Los Angeles, CA" |
| total_distance_miles | number | Total route distance in miles | 2797.18 |
| estimated_duration_hours | number | Estimated driving time in hours | 45.01 |
| states_traveled | string | State-by-state path | "NEW YORK > PENNSYLVANIA > ..." |
| number_of_fuel_stops | integer | Total fuel stops needed | 6 |

### fuel_cost_summary Object

| Field | Type | Description |
|-------|------|-------------|
| total_fuel_cost_usd | number | Total fuel cost in USD |
| total_gallons_needed | number | Total gallons required for trip |
| vehicle_mpg | integer | Vehicle fuel efficiency (always 10) |
| max_range_miles | integer | Maximum range per tank (always 500) |
| fuel_stops_breakdown | array[string] | Human-readable stop summaries |

### detailed_fuel_stops Array

Each fuel stop object contains:

| Field | Type | Description |
|-------|------|-------------|
| segment_index | integer | Stop number (1-indexed) |
| segment_distance_miles | number | Distance to this stop |
| station | object | Fuel station details |
| gallons_purchased | number | Gallons needed for this segment |
| cost | number | Cost for this fuel stop in USD |

### map_data Object

| Field | Type | Description |
|-------|------|-------------|
| route_geojson | object | GeoJSON LineString geometry |
| encoded_polyline | string | Google-encoded polyline |
| format_info | string | Usage instructions |

**GeoJSON Structure:**
```json
{
  "type": "LineString",
  "coordinates": [
    [longitude, latitude],
    [longitude, latitude]
  ]
}
```

---



## Testing Endpoints

## Changelog

### Version 1.0.0 (Current)

**Features:**
- Route planning with fuel stop optimization
- GeoJSON and encoded polyline support
- Pagination for fuel stations
- Comprehensive error handling

**Optimizations:**
- Single API call per route plan
- Database indexing on state field
- Coordinate simplification (~90% reduction)
- BFS algorithm for state corridor

---

## Support

For issues or questions:
1. Check [README.md](README.md) for setup instructions
2. Review [Troubleshooting](README.md#-troubleshooting) section
3. Check OpenRouteService API status
4. Verify environment variables in `.env`

---

**Last Updated**: February 2026  
**API Version**: 1.0.0  
**Django Version**: 5.x  
**Python Version**: 3.10+
