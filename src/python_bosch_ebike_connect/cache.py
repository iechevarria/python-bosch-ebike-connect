"""On-disk JSON cache of raw ride responses, plus sync helpers.

Layout under the cache directory:
    {ride_id}_raw.json  # the untouched /activities/ride/details response

Details, coordinates and series are all parsed from the raw response when loaded, so one request
per ride covers all three, and a newly parsed field shows up for every cached ride without a
refetch.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, TypeVar

import orjson

from .client import BoschEBikeClient
from .exceptions import APIError, EBikeConnectError
from .types import RideDetails, RideSeries

T = TypeVar("T")


class RideCache:
    """JSON-file cache of raw ride responses, keyed by ride id.

    Reads go through orjson: every run loads every cached ride, 1 Hz series included, and
    orjson parses them about 1.5x faster than the stdlib, to identical objects. Writes stay on
    the stdlib so the files on disk keep their exact bytes.
    """

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _path(self, ride_id: str) -> Path:
        return self.directory / f"{ride_id}_raw.json"

    def load_raw(self, ride_id: str) -> dict[str, Any] | None:
        path = self._path(ride_id)
        return orjson.loads(path.read_bytes()) if path.exists() else None

    def save_raw(self, ride_id: str, data: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(ride_id).write_text(json.dumps(data))

    def load_all_raw(self) -> dict[str, dict[str, Any]]:
        if not self.directory.exists():
            return {}
        return {
            f.stem.removesuffix("_raw"): orjson.loads(f.read_bytes())
            for f in self.directory.glob("*_raw.json")
        }


def iter_activity_headers(client: BoschEBikeClient, page_size: int = 1000) -> Iterator[dict[str, Any]]:
    """Yield every activity header, newest first, paging back until the API runs out.

    The API is one activity per day and caps a page at ``page_size``, so a single page silently
    drops the oldest days once there are more of them. ``offset`` is exclusive: passing the
    oldest activity's ``start_time`` returns the activities strictly before it.

    Each page is a round trip of around half a second, so the default is large: the API
    honoured ``max=1000`` when probed (all 228 days of an account in one page, where 200 took
    three requests). Paging still runs until an empty page, so a server-side cap below
    ``page_size`` costs a request rather than the oldest days.
    """
    offset: int | None = None
    while page := client.get_activity_headers(max_results=page_size, offset=offset):
        yield from page
        oldest = min(int(a["start_time"]) for a in page)
        if offset is not None and oldest >= offset:
            break  # the API ignored the offset; stop rather than loop forever
        offset = oldest


def sync_rides(
    client: BoschEBikeClient,
    cache: RideCache,
    page_size: int = 1000,
) -> dict[str, dict[str, Any]]:
    """Return the raw response for every ride in the account's full history.

    Only rides missing from the cache hit the API. A ride that fails to fetch is reported and
    skipped, so it is retried on the next run; authentication errors are not caught.
    """
    raw: dict[str, dict[str, Any]] = {}
    new_count = 0
    for activity in iter_activity_headers(client, page_size):
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
    page_size: int = 1000,
) -> list[RideDetails]:
    """Return RideDetails for every ride, caching new fetches."""
    raw = sync_rides(client, cache, page_size)
    return list(_parse_each(raw, BoschEBikeClient.parse_ride_details).values())


def fetch_ride_series(
    client: BoschEBikeClient,
    cache: RideCache,
    page_size: int = 1000,
) -> dict[str, RideSeries]:
    """Return the 1 Hz sample series for every ride, caching new fetches."""
    raw = sync_rides(client, cache, page_size)
    return _parse_each(raw, BoschEBikeClient.parse_ride_series)


def fetch_ride_coords(
    client: BoschEBikeClient,
    cache: RideCache,
    page_size: int = 1000,
) -> dict[str, list[tuple[float, float]]]:
    """Return coordinate tracks for every ride that has GPS data, caching new fetches."""
    raw = sync_rides(client, cache, page_size)
    tracks = _parse_each(raw, BoschEBikeClient.parse_ride_coordinates)
    return {rid: track for rid, track in tracks.items() if track}


def parse_rides(
    raw: dict[str, dict[str, Any]],
) -> tuple[list[RideDetails], dict[str, list[tuple[float, float]]], dict[str, RideSeries]]:
    """Details, coordinate tracks (rides with GPS only) and series, all from one ``sync_rides``.

    The three ``fetch_ride_*`` helpers each run their own sync, so calling all three pages the
    activity headers and reads the whole cache three times over; this does it once.
    """
    details = list(_parse_each(raw, BoschEBikeClient.parse_ride_details).values())
    tracks = _parse_each(raw, BoschEBikeClient.parse_ride_coordinates)
    series = _parse_each(raw, BoschEBikeClient.parse_ride_series)
    return details, {rid: track for rid, track in tracks.items() if track}, series
