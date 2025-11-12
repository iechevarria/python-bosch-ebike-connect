"""Type definitions for the Bosch eBike Connect API."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ActivityType:
    """Activity type enumeration."""

    BIKE_RIDE = "BIKE_RIDE"


@dataclass
class DriveUnit:
    """Drive unit information."""

    manufacturer: str
    name: str
    version_hardware: str
    version_software: str
    assistance_levels: int
    max_assistance: int


@dataclass
class BatteryUnit:
    """Battery unit information."""

    manufacturer: str
    name: str
    version_hardware: str
    version_software: str


@dataclass
class BatteryInformationUnit:
    """Battery information unit data."""

    manufacturer: str
    name: str
    version_hardware: str
    version_software: str
    last_synchronization: str | None
    number_of_uploads: int


@dataclass
class AssistanceLevel:
    """Custom assistance level configuration."""

    eco_assistance: int
    tour_assistance: int
    sport_assistance: int
    turbo_assistance: int


@dataclass
class EBike:
    """eBike device information.

    Note: drive_unit, battery_unit, bui, and assistance_level are stored as
    raw dictionaries from the API response rather than strongly-typed objects,
    as the API structure is complex and may vary.
    """

    id: str
    name: str
    vin: str | None
    drive_unit: dict[str, Any] | None
    battery_unit: dict[str, Any] | None
    bui: dict[str, Any] | None
    assistance_level: dict[str, Any] | None


@dataclass
class ActivityHeader:
    """Activity header information."""

    id: str
    name: str
    start_time: datetime
    end_time: datetime
    driving_time: int
    distance: int


@dataclass
class RideDetails:
    """Detailed ride information.

    Note: driving_time is in milliseconds.
    """

    id: str
    name: str
    start_time: datetime
    end_time: datetime
    driving_time: int  # in milliseconds
    distance: float
    avg_speed: float | None
    max_speed: float | None
    avg_cadence: float | None
    calories: float | None
    altitude_up: float | None
    altitude_down: float | None
    segments: list[dict[str, Any]] | None


@dataclass
class TripDetails:
    """Detailed trip information.

    Note: driving_time is in milliseconds.
    """

    id: str
    name: str
    start_time: datetime
    end_time: datetime
    driving_time: int  # in milliseconds
    distance: float
    rides: list[RideDetails] | None
