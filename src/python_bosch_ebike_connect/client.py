"""Bosch eBike Connect API client."""

from datetime import datetime
from typing import Any

import httpx

from .exceptions import APIError, AuthenticationError, EBikeConnectError
from .types import EBike, RideDetails, TripDetails


class BoschEBikeClient:
    """Client for interacting with the Bosch eBike Connect API.

    This client provides methods to authenticate and interact with the
    Bosch eBike Connect service, including retrieving activities, rides,
    trips, and eBike device information.

    Example:
        >>> client = BoschEBikeClient()
        >>> client.login("username", "password")
        >>> ebikes = client.get_my_ebikes()
        >>> activities = client.get_activity_headers()
    """

    BASE_URL = "https://www.ebike-connect.com"
    API_BASE = f"{BASE_URL}/ebikeconnect/api"

    def __init__(self) -> None:
        """Initialize the client."""
        self._client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; python-bosch-ebike-connect)",
                "Protect-from": "CSRF",
            },
            follow_redirects=True,
        )
        self._authenticated = False

    def __enter__(self) -> "BoschEBikeClient":
        """Context manager entry."""
        return self

    def __exit__(self, *_: object) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def login(self, username: str, password: str, remember: bool = True) -> dict[str, Any]:
        """Authenticate with the Bosch eBike Connect service.

        Args:
            username: User's email or username
            password: User's password
            remember: Whether to persist the session (default: True)

        Returns:
            User information from the login response

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        try:
            response = self._client.post(
                f"{self.API_BASE}/portal/login/public",
                json={
                    "username": username,
                    "password": password,
                    "rememberme": remember,
                },
            )

            if response.status_code >= 400:
                raise AuthenticationError(
                    f"Authentication failed: {response.text}",
                    status_code=response.status_code,
                )

            self._authenticated = True
            return response.json()

        except httpx.HTTPError as e:
            raise APIError(f"HTTP error during authentication: {e}") from e

    def get_version_number(self) -> str:
        """Get the service version number.

        Returns:
            Version number as a string

        Raises:
            APIError: If the API request fails
        """
        response = self._request("GET", f"{self.BASE_URL}/versionNumber.txt")
        try:
            data = response.json()
            return data.get("version", response.text.strip())
        except Exception:
            return response.text.strip()

    def get_api_version(self) -> dict[str, Any]:
        """Get the API version information.

        Returns:
            API version information

        Raises:
            APIError: If the API request fails
        """
        return self._request_json("GET", f"{self.API_BASE}/api_version")

    def get_my_ebikes(self) -> list[EBike]:
        """Get the user's registered eBikes.

        Returns:
            List of EBike objects

        Raises:
            APIError: If the API request fails
            EBikeConnectError: If not authenticated
        """
        self._ensure_authenticated()
        data = self._request_json("GET", f"{self.API_BASE}/portal/devices/my_ebikes")

        # The API returns a dict with "my_ebikes" key containing the list
        ebike_list = data.get("my_ebikes", []) if isinstance(data, dict) else data

        ebikes = []
        for ebike_data in ebike_list:
            drive_unit = ebike_data.get("drive_unit")
            batteries = ebike_data.get("batteries", [])
            battery_unit = batteries[0] if batteries else None
            buis = ebike_data.get("buis", [])
            bui = buis[0] if buis else None

            # Extract a name from drive_unit device_name if available
            name = drive_unit.get("device_name", "eBike") if drive_unit else "eBike"

            # Use the drive unit serial as ID if available
            ebike_id = drive_unit.get("serial", "") if drive_unit else ""

            ebikes.append(
                EBike(
                    id=ebike_id,
                    name=name,
                    vin=None,  # VIN not present in this API response structure
                    drive_unit=drive_unit,
                    battery_unit=battery_unit,
                    bui=bui,
                    assistance_level=None,  # Not directly available in response
                )
            )

        return ebikes

    def get_activity_headers(
        self,
        max_results: int = 20,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get activity headers (list of trips/rides).

        Args:
            max_results: Maximum number of activities to retrieve (default: 20)
            offset: Timestamp in milliseconds for pagination (default: current time)

        Returns:
            List of activity header dictionaries

        Raises:
            APIError: If the API request fails
            EBikeConnectError: If not authenticated
        """
        self._ensure_authenticated()

        if offset is None:
            offset = int(datetime.now().timestamp() * 1000)

        params = {
            "max": max_results,
            "offset": offset,
        }

        return self._request_json(
            "GET",
            f"{self.API_BASE}/portal/activities/trip/headers",
            params=params,
        )

    def get_ride_coordinates(self, ride_id: str) -> list[tuple[float, float]]:
        """Get GPS coordinates for a specific ride.

        Args:
            ride_id: The ride identifier

        Returns:
            List of (latitude, longitude) tuples for the ride track.
            Points with missing GPS data are filtered out.

        Raises:
            APIError: If the API request fails
            EBikeConnectError: If not authenticated
        """
        self._ensure_authenticated()
        data = self._request_json(
            "GET",
            f"{self.API_BASE}/activities/ride/details/{ride_id}",
        )

        coords = []
        for segment in data.get("coordinates", []):
            for point in segment:
                if point and point[0] is not None and point[1] is not None:
                    coords.append((float(point[0]), float(point[1])))
        return coords

    def get_all_coordinates(
        self,
        max_activities: int = 100,
    ) -> list[tuple[float, float]]:
        """Get GPS coordinates from all rides across multiple activities.

        Convenience method for building heatmaps or analyzing ride patterns.

        Args:
            max_activities: Maximum number of activities to fetch (default: 100)

        Returns:
            List of (latitude, longitude) tuples from all rides.

        Raises:
            APIError: If the API request fails
            EBikeConnectError: If not authenticated
        """
        self._ensure_authenticated()
        activities = self.get_activity_headers(max_results=max_activities)

        all_coords = []
        for activity in activities:
            for ride in activity.get("ride_headers", []):
                ride_id = ride.get("id")
                if ride_id:
                    coords = self.get_ride_coordinates(ride_id)
                    all_coords.extend(coords)
        return all_coords

    def get_ride_details(self, ride_id: str) -> RideDetails:
        """Get detailed information about a specific ride.

        Args:
            ride_id: The ride identifier

        Returns:
            RideDetails object with complete ride information

        Raises:
            APIError: If the API request fails
            EBikeConnectError: If not authenticated
        """
        self._ensure_authenticated()
        data = self._request_json(
            "GET",
            f"{self.API_BASE}/activities/ride/details/{ride_id}",
        )

        return RideDetails(
            id=data.get("id", ""),
            name=data.get("title", ""),
            start_time=self._parse_datetime(data.get("start_time")),
            end_time=self._parse_datetime(data.get("end_time")),
            driving_time=self._parse_int(data.get("driving_time"), 0),
            distance=self._parse_float(data.get("total_distance"), 0.0),
            avg_speed=self._parse_float(data.get("avg_speed")),
            max_speed=self._parse_float(data.get("max_speed")),
            avg_cadence=self._parse_float(data.get("avg_cadence")),
            calories=self._parse_float(data.get("calories")),
            altitude_up=self._parse_float(data.get("altitude_up")),
            altitude_down=self._parse_float(data.get("altitude_down")),
            segments=data.get("segments"),
        )

    def get_trip_details(self, trip_id: str) -> TripDetails:
        """Get detailed information about a specific trip.

        Args:
            trip_id: The trip identifier

        Returns:
            TripDetails object with complete trip information

        Raises:
            APIError: If the API request fails
            EBikeConnectError: If not authenticated
        """
        self._ensure_authenticated()
        data = self._request_json(
            "GET",
            f"{self.API_BASE}/activities/trip/details/{trip_id}",
        )

        # Note: The trip details API doesn't include nested rides.
        # Rides are available as 'ride_headers' in get_activity_headers() response.
        return TripDetails(
            id=data.get("id", ""),
            name=data.get("title", ""),
            start_time=self._parse_datetime(data.get("start_time")),
            end_time=self._parse_datetime(data.get("end_time")),
            driving_time=self._parse_int(data.get("driving_time"), 0),
            distance=self._parse_float(data.get("total_distance"), 0.0),
            rides=None,
        )

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional arguments to pass to httpx

        Returns:
            Response object

        Raises:
            APIError: If the request fails
        """
        try:
            response = self._client.request(method, url, **kwargs)

            if response.status_code >= 400:
                raise APIError(
                    f"API request failed: {response.text}",
                    status_code=response.status_code,
                )

            return response

        except httpx.HTTPError as e:
            raise APIError(f"HTTP error: {e}") from e

    def _request_json(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any] | list[Any]:
        """Make an HTTP request and return JSON response.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional arguments to pass to httpx

        Returns:
            Parsed JSON response

        Raises:
            APIError: If the request fails or response is not JSON
        """
        response = self._request(method, url, **kwargs)
        try:
            return response.json()
        except Exception as e:
            raise APIError(f"Failed to parse JSON response: {e}") from e

    def _ensure_authenticated(self) -> None:
        """Ensure the client is authenticated.

        Raises:
            EBikeConnectError: If not authenticated
        """
        if not self._authenticated:
            raise EBikeConnectError("Not authenticated. Please call login() first.")

    @staticmethod
    def _parse_datetime(dt_str: str | int | None) -> datetime:
        """Parse datetime string or timestamp.

        Args:
            dt_str: Datetime string in ISO format or timestamp in milliseconds

        Returns:
            Parsed datetime object
        """
        if not dt_str:
            return datetime.now()

        # If it's a timestamp (int or numeric string), convert from milliseconds
        if isinstance(dt_str, int) or (isinstance(dt_str, str) and dt_str.isdigit()):
            try:
                timestamp_ms = int(dt_str)
                return datetime.fromtimestamp(timestamp_ms / 1000)
            except (ValueError, OSError):
                pass

        # If it's a string, try parsing with common formats
        if isinstance(dt_str, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
            ]:
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue

            # Fallback to fromisoformat
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return datetime.now()

    @staticmethod
    def _parse_int(value: Any, default: int = 0) -> int:
        """Parse integer value that might be a string.

        Args:
            value: Value to parse (can be str, int, or None)
            default: Default value if parsing fails

        Returns:
            Parsed integer value
        """
        if value is None:
            return default
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _parse_float(value: Any, default: float | None = None) -> float | None:
        """Parse float value that might be a string.

        Args:
            value: Value to parse (can be str, float, or None)
            default: Default value if parsing fails

        Returns:
            Parsed float value or None
        """
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
