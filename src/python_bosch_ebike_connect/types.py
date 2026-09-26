"""Type definitions for the Bosch eBike Connect API."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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


MOTOR_SYSTEM_EFFICIENCY = 0.75
"""Electrical energy drawn from the pack -> mechanical output at the cranks.

Derived, not documented: on rides ridden entirely in TURBO the API's battery/rider energy
ratio runs well past the drive unit's 340% mechanical assist cap (up to 4.65x), which a
mechanical ratio cannot do. The excess tracks average speed (assist taper toward the cutoff)
rather than time spent not pedaling, which rules out walk assist as the explanation. The
implied efficiency is ~0.73-0.78.
"""


@dataclass
class RideDetails:
    """Detailed ride information.

    Note: driving_time is in milliseconds.

    Field semantics worth knowing, none of them documented by Bosch (all verified against the
    live API across a full ride history):

    - ``assist_pct`` maps assistance level (0=OFF, 1=ECO, 2=TOUR, 3=SPORT, 4=TURBO) to a share
      of **distance**, not time. It cannot be used to split ride time across levels.
    - ``battery_share_pct``/``driver_share_pct`` split ride energy between pack and rider, but
      the battery side is **electrical draw**, so it carries motor and controller losses. Use
      :meth:`battery_wh` / :meth:`motor_energy_j` rather than reading it as mechanical assist.
    - ``avg_driver_power`` is averaged over ``pedaling_time_s`` (seconds with nonzero rider
      power) -- i.e. while pedaling, not over the whole ride.
    - ``elevation_gain`` accumulates at a ~1 m threshold and so is inflated by barometric
      noise; ``elevation_gain_smoothed`` re-accumulates the altitude series at 3 m.
    - ``calories`` is 0.0 and the heart-rate fields are null unless a strap is paired.
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
    elevation_gain: float | None
    elevation_loss: float | None
    segments: list[dict[str, Any]] | None
    operation_time: int = 0  # milliseconds; unlike driving_time this includes time stopped
    max_cadence: float | None = None
    elevation_gain_smoothed: float | None = None  # 3 m threshold, from the altitude series
    assist_pct: dict[int, float] = field(default_factory=dict)  # assist level -> share of distance
    driver_energy_j: float | None = None  # rider's mechanical work over the ride, joules
    avg_driver_power: float | None = None  # watts, averaged over pedaling_time_s only
    pedaling_time_s: int | None = None  # seconds with nonzero rider power
    driver_share_pct: float | None = None  # rider's share of ride energy
    battery_share_pct: float | None = None  # pack's share, as electrical energy drawn

    def battery_wh(self) -> float | None:
        """Electrical energy drawn from the battery over this ride, in watt-hours."""
        if not self.driver_energy_j or not self.driver_share_pct or self.battery_share_pct is None:
            return None
        return self.driver_energy_j / self.driver_share_pct * self.battery_share_pct / 3600

    def motor_energy_j(self) -> float | None:
        """The motor's *mechanical* contribution in joules, after backing out system losses."""
        wh = self.battery_wh()
        return None if wh is None else wh * 3600 * MOTOR_SYSTEM_EFFICIENCY


@dataclass
class RideSeries:
    """The ride's 1 Hz sample series, all three aligned index for index.

    The API returns these alongside the ride summary, as per-segment lists that concatenate to
    roughly one sample per second of ``driving_time``. The clock only advances while the bike is
    moving, so a series has no parked gaps in it -- its x-axis is elapsed riding time, not wall
    clock. Individual samples come back null where the head unit dropped a reading.

    The semantics are undocumented like the rest, but each one pins exactly to a summary field
    (verified across the ride history):

    - ``driver_power_w`` is the **rider's** power, not the motor's: it sums to
      :attr:`RideDetails.driver_energy_j` to the joule, and its nonzero count matches
      :attr:`RideDetails.pedaling_time_s`.
    - ``speed_kmh`` peaks at exactly :attr:`RideDetails.max_speed`. Integrated at 1 Hz it runs
      ~5% over ``distance``, so it is a speedometer trace rather than a distance source.
    - ``altitude_m`` is the series :attr:`RideDetails.elevation_gain_smoothed` re-accumulates.
    """

    speed_kmh: list[float | None]
    altitude_m: list[float | None]
    driver_power_w: list[float | None]


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
