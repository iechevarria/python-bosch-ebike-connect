# Python Bosch eBike Connect

A Python client library for the Bosch eBike Connect API. This library provides a simple and pythonic interface to interact with the Bosch eBike Connect service, allowing you to retrieve information about your eBikes, activities, rides, and trips.

## Features

- **Comprehensive API Coverage**: Implements all endpoints from both [ebike-dl](https://github.com/eMerzh/ebike-dl) and [ebike-connect-js](https://github.com/FlorianCassayre/ebike-connect-js)
- **Type Hints**: Full type annotation support for better IDE integration and type checking
- **Pythonic Design**: Clean, idiomatic Python with minimal dependencies
- **Context Manager Support**: Easy resource management with context managers
- **Well Documented**: Comprehensive docstrings and examples

## Installation

Using `uv`:

```bash
uv add python-bosch-ebike-connect
```

Or using `pip`:

```bash
pip install python-bosch-ebike-connect
```

## Quick Start

```python
from python_bosch_ebike_connect import BoschEBikeClient

# Create client and authenticate
with BoschEBikeClient() as client:
    client.login("your_email@example.com", "your_password")

    # Get your eBikes
    ebikes = client.get_my_ebikes()
    for ebike in ebikes:
        print(f"eBike: {ebike.name}")

    # Get recent activities
    activities = client.get_activity_headers(max_results=10)
    for activity in activities:
        print(f"Trip: {activity.get('name')}")
```

## API Reference

### Authentication

#### `login(username: str, password: str, remember: bool = True) -> dict`

Authenticate with the Bosch eBike Connect service.

**Parameters:**
- `username`: Your email or username
- `password`: Your password
- `remember`: Whether to persist the session (default: True)

**Returns:** User information dictionary

**Raises:**
- `AuthenticationError`: If authentication fails
- `APIError`: If the API request fails

### Service Information

#### `get_version_number() -> str`

Get the service version number.

**Returns:** Version number as a string

#### `get_api_version() -> dict`

Get the API version information.

**Returns:** API version information dictionary

### eBikes

#### `get_my_ebikes() -> list[EBike]`

Get the user's registered eBikes.

**Returns:** List of `EBike` objects containing device information

**Example:**
```python
ebikes = client.get_my_ebikes()
for ebike in ebikes:
    print(f"Name: {ebike.name}")
    print(f"VIN: {ebike.vin}")
    if ebike.drive_unit:
        print(f"Drive Unit: {ebike.drive_unit.get('name')}")
```

### Activities

#### `get_activity_headers(max_results: int = 20, offset: int | None = None) -> list[dict]`

Get activity headers (list of trips/rides).

**Parameters:**
- `max_results`: Maximum number of activities to retrieve (default: 20)
- `offset`: Timestamp in milliseconds for pagination (default: current time)

**Returns:** List of activity header dictionaries

**Example:**
```python
activities = client.get_activity_headers(max_results=5)
for activity in activities:
    print(f"{activity.get('name')}: {activity.get('distance') / 1000:.2f} km")
```

### Rides

#### `get_ride_details(ride_id: str) -> RideDetails`

Get detailed information about a specific ride.

**Parameters:**
- `ride_id`: The ride identifier

**Returns:** `RideDetails` object with complete ride information

**Example:**
```python
ride = client.get_ride_details("ride_id_here")
print(f"Distance: {ride.distance / 1000:.2f} km")
print(f"Average speed: {ride.avg_speed:.1f} km/h")
print(f"Calories: {ride.calories}")
```

### Trips

#### `get_trip_details(trip_id: str) -> TripDetails`

Get detailed information about a specific trip.

**Parameters:**
- `trip_id`: The trip identifier

**Returns:** `TripDetails` object with complete trip information including nested rides

**Example:**
```python
trip = client.get_trip_details("trip_id_here")
print(f"Trip: {trip.name}")
print(f"Duration: {trip.driving_time // 60} minutes")
if trip.rides:
    print(f"Number of rides: {len(trip.rides)}")
```

## Data Types

### `EBike`

Represents an eBike device with the following attributes:
- `id`: Unique identifier
- `name`: eBike name
- `vin`: Vehicle identification number (optional)
- `drive_unit`: Drive unit information (optional)
- `battery_unit`: Battery unit information (optional)
- `bui`: Battery information unit data (optional)
- `assistance_level`: Custom assistance level configuration (optional)

### `RideDetails`

Detailed ride information with attributes:
- `id`: Ride identifier
- `name`: Ride name
- `start_time`: Start timestamp
- `end_time`: End timestamp
- `driving_time`: Duration in seconds
- `distance`: Distance in meters
- `avg_speed`: Average speed in km/h (optional)
- `max_speed`: Maximum speed in km/h (optional)
- `avg_cadence`: Average cadence in RPM (optional)
- `calories`: Calories burned (optional)
- `altitude_up`: Altitude gained in meters (optional)
- `altitude_down`: Altitude descended in meters (optional)
- `segments`: Ride segments data (optional)

### `TripDetails`

Trip information with attributes:
- `id`: Trip identifier
- `name`: Trip name
- `start_time`: Start timestamp
- `end_time`: End timestamp
- `driving_time`: Duration in seconds
- `distance`: Distance in meters
- `rides`: List of `RideDetails` objects (optional)

## Error Handling

The library provides three exception types:

- `EBikeConnectError`: Base exception for all errors
- `AuthenticationError`: Raised when authentication fails
- `APIError`: Raised when API requests fail

**Example:**
```python
from python_bosch_ebike_connect import (
    BoschEBikeClient,
    AuthenticationError,
    APIError,
)

try:
    with BoschEBikeClient() as client:
        client.login("user@example.com", "password")
        ebikes = client.get_my_ebikes()
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except APIError as e:
    print(f"API error: {e} (status code: {e.status_code})")
```

## Examples

See the `examples/` directory for more detailed examples:

- `basic_usage.py`: Demonstrates all major features of the client

To run the example:

```bash
export EBIKE_USERNAME="your_email@example.com"
export EBIKE_PASSWORD="your_password"
uv run examples/basic_usage.py
```

## Development

This project uses `uv` for dependency management.

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/python-bosch-ebike-connect.git
cd python-bosch-ebike-connect

# Install dependencies
uv sync
```

### Testing

**Important**: The Bosch eBike Connect API blocks requests from cloud/datacenter IPs and proxied connections. Testing must be done from a local machine with a residential internet connection.

See [TESTING.md](TESTING.md) for detailed testing instructions.

Quick test:
```bash
export EBIKE_USERNAME="your_email@example.com"
export EBIKE_PASSWORD="your_password"
uv run examples/basic_usage.py
```

## API Endpoints Implemented

This library implements all endpoints from the referenced projects:

### From ebike-dl
-  POST `/ebikeconnect/api/portal/login/public` - Authentication
-  GET `/ebikeconnect/api/portal/activities/trip/headers` - Activity list
-  GET `/ebikeconnect/api/activities/ride/details/{id}` - Ride details

### From ebike-connect-js
-  GET `/versionNumber.txt` - Service version
-  GET `/ebikeconnect/api/api_version` - API version
-  GET `/ebikeconnect/api/activities/trip/details/{id}` - Trip details
-  GET `/ebikeconnect/api/portal/devices/my_ebikes` - User's eBikes

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Disclaimer

This is an unofficial API client and is not affiliated with, endorsed by, or connected to Bosch eBike Systems or Robert Bosch GmbH. Use at your own risk.

## Credits

This project was inspired by and implements endpoints from:
- [ebike-dl](https://github.com/eMerzh/ebike-dl) by eMerzh
- [ebike-connect-js](https://github.com/FlorianCassayre/ebike-connect-js) by FlorianCassayre
