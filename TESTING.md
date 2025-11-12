# Testing the Bosch eBike Connect Client

## Important Note

The Bosch eBike Connect API implements security measures that prevent access from:
- Datacenter/cloud IP addresses
- Proxied connections
- TLS-inspected traffic

This means the client **cannot be tested from cloud/containerized environments** but should work fine from:
- Your local machine
- Residential internet connections
- VPN connections (sometimes)

## Testing from Your Local Machine

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/python-bosch-ebike-connect.git
cd python-bosch-ebike-connect
uv sync
```

### 2. Run the Example Script

```bash
export EBIKE_USERNAME="your_email@example.com"
export EBIKE_PASSWORD="your_password"
uv run examples/basic_usage.py
```

### 3. Test Individual Features

Create a test script:

```python
from python_bosch_ebike_connect import BoschEBikeClient

with BoschEBikeClient() as client:
    # Test authentication
    print("Logging in...")
    user_info = client.login("your_email", "your_password")
    print(f"Logged in as: {user_info.get('user', {}).get('email')}")

    # Test getting eBikes
    print("\nGetting eBikes...")
    ebikes = client.get_my_ebikes()
    for ebike in ebikes:
        print(f"  - {ebike.name}")

    # Test getting activities
    print("\nGetting recent activities...")
    activities = client.get_activity_headers(max_results=5)
    print(f"Found {len(activities)} activities")
```

## Expected Behavior

### Successful Authentication

When authentication succeeds, you should see:
- Status code 200
- A `REMEMBER` cookie in the response
- User information in the JSON response

### Accessing Protected Endpoints

After successful authentication, you should be able to:
- Get your eBikes with `get_my_ebikes()`
- List activities with `get_activity_headers()`
- Get ride details with `get_ride_details(ride_id)`
- Get trip details with `get_trip_details(trip_id)`

## Common Issues

### 403 Forbidden

If you get "Access denied" errors:

1. **From Cloud/Container**: This is expected - see note above
2. **From Local Machine**:
   - Check your credentials are correct
   - Ensure you can access https://www.ebike-connect.com in your browser
   - Try using a different network (some corporate networks may be blocked)

### Authentication Errors

If authentication fails with correct credentials:
- The API might have changed - check if the website works in your browser
- Your account might be locked - try logging in via the website first
- Rate limiting might be in effect - wait a few minutes and try again

## Debugging

Enable verbose HTTP logging:

```python
import logging
import httpx

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or for httpx specifically
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)
```

## Testing Status

✅ **Successfully tested with real Bosch eBike Connect account** (November 2025)
- Authentication working correctly
- eBike data retrieval (Riese & Müller Packster 70 with Performance Line CX)
- Activity/trip listing and details
- Ride details including speed, cadence, altitude data

**Note:** The client has been updated to handle the actual API response format, which differs from some initial assumptions:
- Timestamps are in milliseconds (Unix epoch × 1000)
- Numeric values may be returned as strings and are automatically converted
- eBike data structure includes arrays for batteries and BUIs

## Contributing Test Results

If you successfully test the client, please consider:
1. Opening an issue to report your results
2. Contributing test cases
3. Documenting any new endpoints you discover

## API Coverage

The client currently implements:

- ✅ Authentication (`POST /portal/login/public`)
- ✅ Service version (`GET /versionNumber.txt`)
- ✅ API version (`GET /api_version`)
- ✅ User eBikes (`GET /portal/devices/my_ebikes`)
- ✅ Activity list (`GET /portal/activities/trip/headers`)
- ✅ Ride details (`GET /activities/ride/details/{id}`)
- ✅ Trip details (`GET /activities/trip/details/{id}`)

### Potential Additional Endpoints to Test

If you have access to the API, try exploring:
- User profile endpoints
- Activity CRUD operations (create, update, delete)
- Statistics/aggregation endpoints
- Export formats (GPX, TCX)
- Device management endpoints
- Settings endpoints
