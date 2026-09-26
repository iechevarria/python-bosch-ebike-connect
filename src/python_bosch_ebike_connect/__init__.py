"""Python client for the Bosch eBike Connect API.

This package provides a simple and pythonic interface to interact with
the Bosch eBike Connect service, allowing you to retrieve information
about your eBikes, activities, rides, and trips.

Example:
    >>> from python_bosch_ebike_connect import BoschEBikeClient
    >>> client = BoschEBikeClient()
    >>> client.login("your_email@example.com", "your_password")
    >>> ebikes = client.get_my_ebikes()
    >>> for ebike in ebikes:
    ...     print(f"eBike: {ebike.name}")
"""

from .cache import RideCache, fetch_ride_coords, fetch_ride_details, fetch_ride_series, sync_rides
from .client import BoschEBikeClient
from .exceptions import APIError, AuthenticationError, EBikeConnectError
from .types import EBike, RideDetails, RideSeries, TripDetails
from .units import KM_TO_MILES, kmh_to_mph, meters_to_miles

__version__ = "0.1.0"

__all__ = [
    "BoschEBikeClient",
    "EBikeConnectError",
    "AuthenticationError",
    "APIError",
    "EBike",
    "RideDetails",
    "RideSeries",
    "TripDetails",
    "RideCache",
    "fetch_ride_details",
    "fetch_ride_coords",
    "fetch_ride_series",
    "sync_rides",
    "KM_TO_MILES",
    "meters_to_miles",
    "kmh_to_mph",
]
