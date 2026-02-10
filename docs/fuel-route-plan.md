# Fuel Route Optimizer Plan

Job title: Django Developer | Remote

Successful completion of this task will result in a $100 USD reward. To claim this reward, you must satisfy all requirements listed below.

Assignment:
- Build an API that takes inputs of start and finish location both within the USA.
- Return a map of the route along with optimal location to fuel up along the route. Optimal mostly means cost effective based on fuel prices.
- Assume the vehicle has a maximum range of 500 miles so multiple fuel ups might need to be displayed on the route.
- Also return the total money spent on fuel assuming the vehicle achieves 10 miles per gallon.
- Use the attached file for a list of fuel prices.
- Find a free API yourself for the map and routing.

Requirements:
- Build the app in latest stable Django.
- Send your results for this project within 3 days of receiving the exercise.
- The API should return results quickly, the quicker the better.
- The API should not need to call the free map/routing API too much. One call to the map/route API is ideal; two or three is acceptable.
- Make a loom where you use Postman or similar API platform to demonstrate the API working while also giving a quick overview of your code. 5 minutes max.
- Share the code with us.

## Updated Plan (state-based filtering, max 2 API calls)

We keep at most one ORS routing call per request, and optionally a second ORS geocode call if we cannot extract state from the routing response. No station geocoding is used.

### Step 1: Get start/end states with a single call
- Use the ORS geocode response to extract the US state for start and end in the same request cycle.
- If the routing response already includes both states, do not make a second call.

### Step 2: Prefilter stations by state
- Use the station state field to prefilter candidates based on start and end states.
- Apply a simple state corridor strategy: include start and end states plus intermediary states derived from a predefined adjacency or straight-line state list.
- This avoids scanning all stations and keeps requests fast.

### Step 3: Assign fuel stops without station coordinates
- Use the filtered station list as candidates and place stops by distance along the route using only the route distance.
- The optimization assumes stops are available within the selected states at each 500-mile segment.
- Choose the lowest-price station in each segment to minimize cost.

### Step 4: Optimal fueling logic (min-cost)
- Max range is 500 miles and fuel economy is 10 mpg (tank capacity assumed 50 gallons).
- Compute gallons per leg as distance divided by 10.
- Sum leg costs using the selected station price per segment.

### Step 5: API response shape
Return both a short customer-friendly summary and a detailed section for developers:
- customer_summary (short, readable steps + total cost)
- route_geometry_geojson
- fuel_stops (station info, segment distance, gallons bought, cost)
- fuel_plan_summary (totals and readable steps)

### External API usage
- ORS routing: 1 call per request.
- Optional ORS geocode: 1 call per request only if state is missing.

## Next Implementation Notes
- Add a service module for state-based station selection and fuel optimization.
- Update the route endpoint to return the expanded response.

## Sample API Response (for demo video)

Example request:
POST /api/route-plan/
{
	"start": "New York, NY",
	"end": "Los Angeles, CA"
}

Example response:
```
{
	"start": "New York, NY",
	"end": "Los Angeles, CA",
	"distance_miles": 2797.18,
	"customer_summary": {
		"total_fuel_cost": 799.79,
		"stops": [
			"After 500 miles: MI, TA SAGINAW I 75 TRAVEL CENTER ($163.50)",
			"After 1000 miles: NE, SAPP BROS TRAVEL CENTER ($173.00)",
			"After 1500 miles: CO, CIRCLE K #2744095 ($164.50)",
			"After 2000 miles: AZ, PILOT TRAVEL CENTER #328 ($198.00)",
			"After 2297.18 miles: AZ, CIRCLE K #2702885 ($100.79)"
		]
	},
	"fuel_plan_summary": {
		"total_distance_miles": 2797.18,
		"max_range_miles": 500,
		"mpg": 10,
		"total_gallons": 229.72,
		"total_fuel_cost": 799.79,
		"stops_explained": [
			"Drive 500 miles, stop in MI at TA SAGINAW I 75 TRAVEL CENTER, buy 50.0 gallons for $163.50.",
			"Drive 500 miles, stop in NE at SAPP BROS TRAVEL CENTER, buy 50.0 gallons for $173.00.",
			"Drive 500 miles, stop in CO at CIRCLE K #2744095, buy 50.0 gallons for $164.50.",
			"Drive 500 miles, stop in AZ at PILOT TRAVEL CENTER #328, buy 50.0 gallons for $198.00.",
			"Drive 297.18 miles, stop in AZ at CIRCLE K #2702885, buy 29.72 gallons for $100.79."
		]
	},
	"route_geometry_geojson": {
		"type": "LineString",
		"coordinates": [
			[-73.9857, 40.7484],
			[-87.6298, 41.8781],
			[-104.9903, 39.7392],
			[-118.2437, 34.0522]
		]
	},
	"fuel_stops": [
		{
			"segment_index": 1,
			"segment_distance_miles": 500.0,
			"station": {
				"station_name": "TA SAGINAW I 75 TRAVEL CENTER",
				"city": "Bridgeport",
				"state": "MI",
				"price_per_gallon": 3.27
			},
			"gallons_purchased": 50.0,
			"cost": 163.50
		},
		{
			"segment_index": 2,
			"segment_distance_miles": 500.0,
			"station": {
				"station_name": "SAPP BROS TRAVEL CENTER",
				"city": "Ogallala",
				"state": "NE",
				"price_per_gallon": 3.46
			},
			"gallons_purchased": 50.0,
			"cost": 173.00
		},
		{
			"segment_index": 3,
			"segment_distance_miles": 500.0,
			"station": {
				"station_name": "CIRCLE K #2744095",
				"city": "Denver",
				"state": "CO",
				"price_per_gallon": 3.29
			},
			"gallons_purchased": 50.0,
			"cost": 164.50
		},
		{
			"segment_index": 4,
			"segment_distance_miles": 500.0,
			"station": {
				"station_name": "PILOT TRAVEL CENTER #328",
				"city": "Quartzsite",
				"state": "AZ",
				"price_per_gallon": 3.96
			},
			"gallons_purchased": 50.0,
			"cost": 198.00
		},
		{
			"segment_index": 5,
			"segment_distance_miles": 297.18,
			"station": {
				"station_name": "CIRCLE K #2702885",
				"city": "Phoenix",
				"state": "AZ",
				"price_per_gallon": 3.39
			},
			"gallons_purchased": 29.72,
			"cost": 100.79
		}
	]
}
```

Notes for demo:
- Start and end are validated as USA locations.
- Route geometry is returned for map rendering.
- Fuel stops are selected to keep each leg within 500 miles.
- Total cost uses 10 mpg and station prices from the CSV.
- External calls are limited (routing once, optional geocode once).

## Implementation Checklist
- Add state extraction in the ORS geocode response.
- Build state corridor list for candidate station filtering.
- Implement segment-based fuel stop selection (500-mile legs).
- Compute gallons and total cost using 10 mpg.
- Return response with customer_summary, fuel_plan_summary, route_geometry_geojson, fuel_stops.
- Validate with a long route and confirm only 1 to 2 external API calls.
- Record the Postman demo and brief code walkthrough.
