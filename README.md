# Python Bosch eBike Connect

An unofficial Python client for the Bosch eBike Connect API, inspired by [ebike-dl](https://github.com/eMerzh/ebike-dl) and [ebike-connect-js](https://github.com/FlorianCassayre/ebike-connect-js).


## Quick Start

```python
from python_bosch_ebike_connect import BoschEBikeClient

with BoschEBikeClient() as client:
    client.login("your_email@example.com", "your_password")

    for ebike in client.get_my_ebikes():
        print(f"eBike: {ebike.name}")

    for activity in client.get_activity_headers(max_results=10):
        print(f"Trip: {activity.get('title')}")
```

## API Reference

### Authentication

- `login(username, password, remember=True)` - Authenticate with the service

### Service Info

- `get_version_number()` - Get service version
- `get_api_version()` - Get API version info

### Data

- `get_my_ebikes()` - Get user's registered eBikes (returns `list[EBike]`)
- `get_activity_headers(max_results=20, offset=None)` - Get activity list
- `get_ride_coordinates(ride_id)` - Get GPS coordinates for a ride (returns `list[tuple[float, float]]`)
- `get_all_coordinates(max_activities=100)` - Get all GPS coordinates (useful for heatmaps)
- `get_ride_details(ride_id)` - Get detailed ride info (returns `RideDetails`)
- `get_trip_details(trip_id)` - Get detailed trip info (returns `TripDetails`)

### Caching helpers

For scripts that pull data repeatedly, the library ships a JSON-file cache:

```python
from python_bosch_ebike_connect import BoschEBikeClient, RideCache, fetch_ride_details, fetch_ride_coords

cache = RideCache(".ride_cache")
with BoschEBikeClient() as client:
    client.login(username, password)
    rides = fetch_ride_details(client, cache)        # list[RideDetails]
    coords = fetch_ride_coords(client, cache)        # dict[ride_id, list[(lat, lon)]]
```

`fetch_ride_details` and `fetch_ride_coords` return everything from the cache and only hit the API for new rides. Unit helpers `meters_to_miles` and `kmh_to_mph` are also exported.

## Data Types

- **`EBike`**: `id`, `name`, `vin`, `drive_unit`, `battery_unit`, `bui`, `assistance_level`
- **`RideDetails`**: `id`, `name`, `start_time`, `end_time`, `driving_time` (ms), `distance` (m), `avg_speed`, `max_speed`, `avg_cadence`, `calories`, `altitude_up`, `altitude_down`, `segments`
- **`TripDetails`**: `id`, `name`, `start_time`, `end_time`, `driving_time` (ms), `distance` (m), `rides`

## Error Handling

Three exception types: `EBikeConnectError` (base), `AuthenticationError`, `APIError` (has `status_code`).

## Examples

See `examples/` directory:
- `basic_usage.py` - Basic client usage
- `generate_heatmap.py` - Generate a Strava-style heatmap
- `generate_dashboard.py` - Generate an HTML dashboard with stats

```bash
export EBIKE_USERNAME="your_email@example.com"
export EBIKE_PASSWORD="your_password"
uv run examples/basic_usage.py
```

## Development

```bash
git clone https://github.com/iechevarria/python-bosch-ebike-connect.git
cd python-bosch-ebike-connect
uv sync
```

**Note**: It looks like the Bosch API blocks requests from cloud/datacenter IPs. Test from a local machine with residential internet.
