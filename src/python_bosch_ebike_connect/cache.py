"""On-disk JSON cache for ride coordinates and details, plus sync helpers.

Layout under the cache directory:
    {ride_id}.json          # coordinate track  (list[[lat, lon]])
    {ride_id}_details.json  # serialized RideDetails
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .client import BoschEBikeClient
from .types import RideDetails


class RideCache:
    """JSON-file cache for ride coordinates and details."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _read(self, name: str) -> Any | None:
        path = self.directory / name
        return json.loads(path.read_text()) if path.exists() else None

    def _write(self, name: str, data: Any) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / name).write_text(json.dumps(data))

    def load_coords(self, ride_id: str) -> list[tuple[float, float]] | None:
        data = self._read(f"{ride_id}.json")
        return [tuple(c) for c in data] if data else None

    def save_coords(self, ride_id: str, coords: list[tuple[float, float]]) -> None:
        self._write(f"{ride_id}.json", coords)

    def load_all_coords(self) -> dict[str, list[tuple[float, float]]]:
        if not self.directory.exists():
            return {}
        return {
            f.stem: [tuple(c) for c in json.loads(f.read_text())]
            for f in self.directory.glob("*.json")
            if not f.stem.endswith("_details")
        }

    def load_details(self, ride_id: str) -> RideDetails | None:
        data = self._read(f"{ride_id}_details.json")
        return _dict_to_ride_details(data) if data else None

    def save_details(self, ride: RideDetails) -> None:
        self._write(f"{ride.id}_details.json", _ride_details_to_dict(ride))

    def load_all_details(self) -> dict[str, RideDetails]:
        if not self.directory.exists():
            return {}
        return {
            f.stem.removesuffix("_details"): _dict_to_ride_details(json.loads(f.read_text()))
            for f in self.directory.glob("*_details.json")
        }


def _ride_details_to_dict(ride: RideDetails) -> dict[str, Any]:
    return {
        **asdict(ride),
        "start_time": ride.start_time.isoformat(),
        "end_time": ride.end_time.isoformat(),
    }


def _dict_to_ride_details(data: dict[str, Any]) -> RideDetails:
    return RideDetails(
        id=data["id"],
        name=data["name"],
        start_time=datetime.fromisoformat(data["start_time"]),
        end_time=datetime.fromisoformat(data["end_time"]),
        driving_time=data["driving_time"],
        distance=data["distance"],
        avg_speed=data.get("avg_speed"),
        max_speed=data.get("max_speed"),
        avg_cadence=data.get("avg_cadence"),
        calories=data.get("calories"),
        altitude_up=data.get("altitude_up"),
        altitude_down=data.get("altitude_down"),
        segments=data.get("segments"),
    )


def fetch_ride_details(
    client: BoschEBikeClient,
    cache: RideCache,
    max_activities: int = 200,
) -> list[RideDetails]:
    """Return RideDetails for every ride across the most recent activities, caching new fetches."""
    cached = cache.load_all_details()
    rides: list[RideDetails] = []
    new_count = 0
    for activity in client.get_activity_headers(max_results=max_activities):
        for header in activity.get("ride_headers", []):
            if not (rid := header.get("id")):
                continue
            if rid in cached:
                rides.append(cached[rid])
                continue
            try:
                ride = client.get_ride_details(rid)
                cache.save_details(ride)
                rides.append(ride)
                new_count += 1
                print(f"  Fetched ride {rid}: {ride.distance / 1000:.1f} km")
            except Exception as e:
                print(f"  Error fetching ride {rid}: {e}")
    print(f"\nTotal: {len(rides)} rides ({new_count} new, {len(rides) - new_count} cached)")
    return rides


def fetch_ride_coords(
    client: BoschEBikeClient,
    cache: RideCache,
    max_activities: int = 200,
) -> dict[str, list[tuple[float, float]]]:
    """Return coordinate tracks for every ride, caching new fetches."""
    coords = cache.load_all_coords()
    new_count = 0
    for activity in client.get_activity_headers(max_results=max_activities):
        for header in activity.get("ride_headers", []):
            if not (rid := header.get("id")) or rid in coords:
                continue
            if track := client.get_ride_coordinates(rid):
                cache.save_coords(rid, track)
                coords[rid] = track
                new_count += 1
                print(f"  Fetched ride {rid}: {len(track)} points")
    print(f"\nTotal: {len(coords)} rides ({new_count} new, {len(coords) - new_count} cached)")
    return coords
