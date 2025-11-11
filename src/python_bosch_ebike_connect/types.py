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
    """eBike device information."""

    id: str
    name: str
    vin: str | None
    drive_unit: DriveUnit | None
    battery_unit: BatteryUnit | None
    bui: BatteryInformationUnit | None
    assistance_level: AssistanceLevel | None


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
    """Detailed ride information."""

    id: str
    name: str
    start_time: datetime
    end_time: datetime
    driving_time: int
    distance: int
    avg_speed: float | None
    max_speed: float | None
    avg_cadence: float | None
    calories: int | None
    altitude_up: int | None
    altitude_down: int | None
    segments: list[dict[str, Any]] | None


@dataclass
class TripDetails:
    """Detailed trip information."""

    id: str
    name: str
    start_time: datetime
    end_time: datetime
    driving_time: int
    distance: int
    rides: list[RideDetails] | None
