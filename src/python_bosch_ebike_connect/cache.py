"""On-disk JSON cache of raw ride responses, plus sync helpers.

Layout under the cache directory:
    {ride_id}_raw.json  # the untouched /activities/ride/details response

Details, coordinates and series are all parsed from the raw response when loaded, so one request
per ride covers all three, and a newly parsed field shows up for every cached ride without a
refetch.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from .client import BoschEBikeClient
from .exceptions import APIError, EBikeConnectError
from .types import RideDetails, RideSeries

T = TypeVar("T")


class RideCache:
    """JSON-file cache of raw ride responses, keyed by ride id."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _path(self, ride_id: str) -> Path:
        return self.directory / f"{ride_id}_raw.json"

    def load_raw(self, ride_id: str) -> dict[str, Any] | None:
        path = self._path(ride_id)
        return json.loads(path.read_text()) if path.exists() else None

    def save_raw(self, ride_id: str, data: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(ride_id).write_text(json.dumps(data))

    def load_all_raw(self) -> dict[str, dict[str, Any]]:
        if not self.directory.exists():
            return {}
        return {
            f.stem.removesuffix("_raw"): json.loads(f.read_text())
            for f in self.directory.glob("*_raw.json")
        }


def sync_rides(
    client: BoschEBikeClient,
    cache: RideCache,
    max_activities: int = 200,
) -> dict[str, dict[str, Any]]:
    """Return the raw response for every ride across the most recent activities.

    Only rides missing from the cache hit the API. A ride that fails to fetch is reported and
    skipped, so it is retried on the next run; authentication errors are not caught.
    """
    raw: dict[str, dict[str, Any]] = {}
    new_count = 0
    for activity in client.get_activity_headers(max_results=max_activities):
        for header in activity.get("ride_headers", []):
            if not (rid := header.get("id")):
                continue
            if (data := cache.load_raw(rid)) is None:
                try:
                    data = client.get_ride_raw(rid)
                except APIError as e:
                    print(f"  Error fetching ride {rid}: {e}")
                    continue
                cache.save_raw(rid, data)
                new_count += 1
                if new_count % 25 == 0:
                    print(f"  Fetched {new_count} rides...")
            raw[rid] = data
    print(f"\nTotal: {len(raw)} rides ({new_count} new, {len(raw) - new_count} cached)")
    return raw


def _parse_each(raw: dict[str, dict[str, Any]], parse: Callable[[dict[str, Any]], T]) -> dict[str, T]:
    parsed: dict[str, T] = {}
    for rid, data in raw.items():
        try:
            parsed[rid] = parse(data)
        except (EBikeConnectError, ValueError, TypeError) as e:
            print(f"  Skipping ride {rid}: {e}")
    return parsed


def fetch_ride_details(
    client: BoschEBikeClient,
    cache: RideCache,
    max_activities: int = 200,
) -> list[RideDetails]:
    """Return RideDetails for every ride across the most recent activities, caching new fetches."""
    raw = sync_rides(client, cache, max_activities)
    return list(_parse_each(raw, BoschEBikeClient.parse_ride_details).values())


def fetch_ride_series(
    client: BoschEBikeClient,
    cache: RideCache,
    max_activities: int = 200,
) -> dict[str, RideSeries]:
    """Return the 1 Hz sample series for every ride, caching new fetches."""
    raw = sync_rides(client, cache, max_activities)
    return _parse_each(raw, BoschEBikeClient.parse_ride_series)


def fetch_ride_coords(
    client: BoschEBikeClient,
    cache: RideCache,
    max_activities: int = 200,
) -> dict[str, list[tuple[float, float]]]:
    """Return coordinate tracks for every ride that has GPS data, caching new fetches."""
    raw = sync_rides(client, cache, max_activities)
    tracks = _parse_each(raw, BoschEBikeClient.parse_ride_coordinates)
    return {rid: track for rid, track in tracks.items() if track}
