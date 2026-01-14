"""Example usage of the Bosch eBike Connect client."""

import os

from python_bosch_ebike_connect import BoschEBikeClient


def main() -> None:
    """Demonstrate basic usage of the client."""
    username, password = os.getenv("EBIKE_USERNAME"), os.getenv("EBIKE_PASSWORD")
    if not username or not password:
        print("Please set EBIKE_USERNAME and EBIKE_PASSWORD environment variables")
        return

    with BoschEBikeClient() as client:
        user_info = client.login(username, password)
        print(f"Logged in as: {user_info.get('user', {}).get('email')}")
        print(f"\nService version: {client.get_version_number()}")
        print(f"API version: {client.get_api_version().get('api_version')}")

        print("\nYour eBikes:")
        for ebike in client.get_my_ebikes():
            print(f"  - {ebike.name} (ID: {ebike.id})")
            if ebike.drive_unit:
                print(f"    Drive Unit: {ebike.drive_unit.get('product_line_name', 'Unknown')}")
            if ebike.battery_unit:
                print(f"    Battery: {ebike.battery_unit.get('device_name', 'Unknown')}")

        print("\nRecent Activities:")
        activities = client.get_activity_headers(max_results=5)
        for activity in activities:
            trip_id = activity.get("id", "")
            distance_km = activity.get("total_distance", 0) / 1000
            print(f"  - {activity.get('title', 'Unnamed')}: {distance_km:.2f} km")

            if trip_id:
                trip = client.get_trip_details(trip_id)
                print(f"    Start: {trip.start_time}, Duration: {trip.driving_time // 60000} min")
                if rides := activity.get("ride_headers", []):
                    print(f"    Rides: {len(rides)}")

        if activities and (rides := activities[0].get("ride_headers", [])):
            if ride_id := rides[0].get("id"):
                ride = client.get_ride_details(ride_id)
                print(f"\nFirst Ride Details (ID: {ride_id}):")
                print(f"  Distance: {ride.distance / 1000:.2f} km")
                if ride.avg_speed:
                    print(f"  Avg/Max speed: {ride.avg_speed:.1f} / {ride.max_speed:.1f} km/h")
                if ride.calories:
                    print(f"  Calories: {ride.calories:.0f}")
                if ride.altitude_up:
                    print(f"  Altitude gain: {ride.altitude_up} m")


if __name__ == "__main__":
    main()
