"""Example usage of the Bosch eBike Connect client."""

import os

from python_bosch_ebike_connect import BoschEBikeClient


def main() -> None:
    """Demonstrate basic usage of the client."""
    # Get credentials from environment variables
    username = os.getenv("EBIKE_USERNAME")
    password = os.getenv("EBIKE_PASSWORD")

    if not username or not password:
        print("Please set EBIKE_USERNAME and EBIKE_PASSWORD environment variables")
        return

    # Create client using context manager for automatic cleanup
    with BoschEBikeClient() as client:
        # Authenticate
        print("Authenticating...")
        user_info = client.login(username, password)
        print(f"Logged in as: {user_info.get('user', {}).get('email')}")

        # Get service version
        print("\nService Information:")
        version = client.get_version_number()
        print(f"Service version: {version}")

        api_version = client.get_api_version()
        print(f"API version: {api_version.get('api_version')}")

        # Get user's eBikes
        print("\nYour eBikes:")
        ebikes = client.get_my_ebikes()
        for ebike in ebikes:
            print(f"  - {ebike.name} (ID: {ebike.id})")
            if ebike.vin:
                print(f"    VIN: {ebike.vin}")
            if ebike.drive_unit:
                print(f"    Drive Unit: {ebike.drive_unit.get('product_line_name', 'Unknown')}")
            if ebike.battery_unit:
                print(f"    Battery: {ebike.battery_unit.get('device_name', 'Unknown')}")

        # Get recent activities
        print("\nRecent Activities:")
        activities = client.get_activity_headers(max_results=5)
        for activity in activities:
            trip_id = activity.get("id", "")
            name = activity.get("title", "Unnamed")
            distance = activity.get("total_distance", 0) / 1000  # Convert to km
            print(f"  - {name}: {distance:.2f} km (ID: {trip_id})")

            # Get detailed trip information
            if trip_id:
                trip = client.get_trip_details(trip_id)
                print(f"    Start: {trip.start_time}")
                print(f"    Duration: {trip.driving_time // 60000} minutes")
                ride_headers = activity.get("ride_headers", [])
                if ride_headers:
                    print(f"    Number of rides: {len(ride_headers)}")

        # Get detailed ride information (if any activities exist)
        if activities:
            # Get the first ride from the most recent trip
            first_trip = activities[0]
            ride_headers = first_trip.get("ride_headers", [])
            if ride_headers:
                first_ride_id = ride_headers[0].get("id")
                if first_ride_id:
                    print(f"\nDetailed Ride Information (ID: {first_ride_id}):")
                    ride = client.get_ride_details(first_ride_id)
                    print(f"  Name: {ride.name}")
                    print(f"  Distance: {ride.distance / 1000:.2f} km")
                    if ride.avg_speed:
                        print(f"  Average speed: {ride.avg_speed:.1f} km/h")
                    if ride.max_speed:
                        print(f"  Max speed: {ride.max_speed:.1f} km/h")
                    if ride.calories:
                        print(f"  Calories: {ride.calories:.0f}")
                    if ride.altitude_up:
                        print(f"  Altitude gain: {ride.altitude_up} m")


if __name__ == "__main__":
    main()
