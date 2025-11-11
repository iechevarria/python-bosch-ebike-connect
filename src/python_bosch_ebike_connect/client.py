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

    def __exit__(self, *args: Any) -> None:
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

        ebikes = []
        for item in data:
            ebike_data = item.get("ebike", {})
            drive_unit = ebike_data.get("drive_unit")
            battery_unit = ebike_data.get("battery_unit")
            bui = ebike_data.get("bui")
            assistance = ebike_data.get("assistance_level")

            ebikes.append(
                EBike(
                    id=ebike_data.get("id", ""),
                    name=ebike_data.get("name", ""),
                    vin=ebike_data.get("vin"),
                    drive_unit=self._parse_dict(drive_unit) if drive_unit else None,
                    battery_unit=self._parse_dict(battery_unit) if battery_unit else None,
                    bui=self._parse_dict(bui) if bui else None,
                    assistance_level=self._parse_dict(assistance) if assistance else None,
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
            name=data.get("name", ""),
            start_time=self._parse_datetime(data.get("start_time")),
            end_time=self._parse_datetime(data.get("end_time")),
            driving_time=data.get("driving_time", 0),
            distance=data.get("distance", 0),
            avg_speed=data.get("avg_speed"),
            max_speed=data.get("max_speed"),
            avg_cadence=data.get("avg_cadence"),
            calories=data.get("calories"),
            altitude_up=data.get("altitude_up"),
            altitude_down=data.get("altitude_down"),
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

        rides = []
        if "rides" in data:
            for ride_data in data["rides"]:
                rides.append(
                    RideDetails(
                        id=ride_data.get("id", ""),
                        name=ride_data.get("name", ""),
                        start_time=self._parse_datetime(ride_data.get("start_time")),
                        end_time=self._parse_datetime(ride_data.get("end_time")),
                        driving_time=ride_data.get("driving_time", 0),
                        distance=ride_data.get("distance", 0),
                        avg_speed=ride_data.get("avg_speed"),
                        max_speed=ride_data.get("max_speed"),
                        avg_cadence=ride_data.get("avg_cadence"),
                        calories=ride_data.get("calories"),
                        altitude_up=ride_data.get("altitude_up"),
                        altitude_down=ride_data.get("altitude_down"),
                        segments=ride_data.get("segments"),
                    )
                )

        return TripDetails(
            id=data.get("id", ""),
            name=data.get("name", ""),
            start_time=self._parse_datetime(data.get("start_time")),
            end_time=self._parse_datetime(data.get("end_time")),
            driving_time=data.get("driving_time", 0),
            distance=data.get("distance", 0),
            rides=rides if rides else None,
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
    def _parse_datetime(dt_str: str | None) -> datetime:
        """Parse datetime string.

        Args:
            dt_str: Datetime string in ISO format

        Returns:
            Parsed datetime object
        """
        if not dt_str:
            return datetime.now()

        # Try parsing with common formats
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
            return datetime.now()

    @staticmethod
    def _parse_dict(data: dict[str, Any]) -> dict[str, Any]:
        """Parse dictionary data (helper for nested objects).

        Args:
            data: Dictionary to parse

        Returns:
            Parsed dictionary
        """
        return data
