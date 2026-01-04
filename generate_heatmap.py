#!/usr/bin/env python3
"""Generate a Strava-style heatmap from Bosch eBike Connect ride data."""

import argparse
import json
import os
from pathlib import Path

import folium
from folium.plugins import HeatMap

from python_bosch_ebike_connect import BoschEBikeClient

CACHE_DIR = Path(__file__).parent / ".ride_cache"
OUTPUT_DIR = Path(__file__).parent


def load_cached_rides() -> dict[str, list[tuple[float, float]]]:
    """Load all cached ride coordinates."""
    if not CACHE_DIR.exists():
        return {}

    rides = {}
    for file in CACHE_DIR.glob("*.json"):
        # Skip _details.json files (used by dashboard)
        if file.stem.endswith("_details"):
            continue
        ride_id = file.stem
        with open(file) as f:
            rides[ride_id] = [tuple(coord) for coord in json.load(f)]
    return rides


def save_ride_to_cache(ride_id: str, coords: list[tuple[float, float]]) -> None:
    """Save ride coordinates to cache."""
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CACHE_DIR / f"{ride_id}.json", "w") as f:
        json.dump(coords, f)


def fetch_rides(
    client: BoschEBikeClient,
    cached_rides: dict[str, list],
    max_activities: int = 200,
) -> dict[str, list[tuple[float, float]]]:
    """Fetch rides, using cache where available."""
    activities = client.get_activity_headers(max_results=max_activities)

    all_rides = dict(cached_rides)
    new_count = 0
    cached_count = 0

    for activity in activities:
        for ride in activity.get("ride_headers", []):
            ride_id = ride.get("id")
            if not ride_id:
                continue

            if ride_id in all_rides:
                cached_count += 1
                continue

            coords = client.get_ride_coordinates(ride_id)
            if coords:
                all_rides[ride_id] = coords
                save_ride_to_cache(ride_id, coords)
                new_count += 1
                print(f"  Fetched ride {ride_id}: {len(coords)} points")

    print(f"\nTotal: {len(all_rides)} rides ({new_count} new, {cached_count} cached)")
    return all_rides


def generate_heatmap(
    rides: dict[str, list[tuple[float, float]]],
    mode: str = "gradient",
) -> None:
    """Generate the heatmap HTML file."""
    all_coords = [coord for coords in rides.values() for coord in coords]

    if not all_coords:
        print("No coordinates to map!")
        return

    # Center map on the data
    center_lat = sum(c[0] for c in all_coords) / len(all_coords)
    center_lng = sum(c[1] for c in all_coords) / len(all_coords)

    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=13,
        tiles="cartodbpositron",
    )

    if mode == "lines":
        # Draw each ride as a polyline with low opacity
        for coords in rides.values():
            folium.PolyLine(
                coords,
                weight=2,
                color="#ff4500",
                opacity=0.1,
            ).add_to(m)
        output_file = OUTPUT_DIR / "heatmap_lines.html"
    else:
        # Gradient heatmap: orange -> yellow -> white
        gradient = {
            0.0: "#000000",
            0.2: "#ff4500",
            0.4: "#ff6a00",
            0.6: "#ffa500",
            0.8: "#ffcc00",
            1.0: "#ffffff",
        }
        HeatMap(
            all_coords,
            radius=8,
            blur=12,
            max_zoom=17,
            gradient=gradient,
        ).add_to(m)
        output_file = OUTPUT_DIR / "heatmap_gradient.html"

    m.save(output_file)
    print(f"\nSaved heatmap to {output_file}")
    print(f"Total points: {len(all_coords)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a heatmap from eBike rides")
    parser.add_argument(
        "--mode",
        choices=["gradient", "lines"],
        default="gradient",
        help="Heatmap style: 'gradient' (orange->white) or 'lines' (stacked polylines)",
    )
    args = parser.parse_args()

    username = os.getenv("EBIKE_USERNAME")
    password = os.getenv("EBIKE_PASSWORD")

    if not username or not password:
        print("Please set EBIKE_USERNAME and EBIKE_PASSWORD environment variables")
        return

    print("Loading cached rides...")
    cached_rides = load_cached_rides()
    print(f"Found {len(cached_rides)} cached rides")

    print("\nFetching rides from API...")
    with BoschEBikeClient() as client:
        client.login(username, password)
        all_rides = fetch_rides(client, cached_rides)

    print(f"\nGenerating {args.mode} heatmap...")
    generate_heatmap(all_rides, mode=args.mode)


if __name__ == "__main__":
    main()
