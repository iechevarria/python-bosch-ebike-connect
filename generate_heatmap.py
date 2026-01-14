#!/usr/bin/env python3
"""Generate a Strava-style heatmap from Bosch eBike Connect ride data."""

import argparse

import folium
from folium.plugins import HeatMap

from python_bosch_ebike_connect import BoschEBikeClient
from utils import CACHE_DIR, OUTPUT_DIR, get_credentials, load_json_cache, save_json_cache

GRADIENT = {0.0: "#000000", 0.2: "#ff4500", 0.4: "#ff6a00", 0.6: "#ffa500", 0.8: "#ffcc00", 1.0: "#ffffff"}


def load_cached_rides() -> dict[str, list[tuple[float, float]]]:
    """Load all cached ride coordinates (excluding _details.json files)."""
    if not CACHE_DIR.exists():
        return {}
    return {
        rid: [tuple(c) for c in coords]
        for rid, coords in load_json_cache("*.json").items()
        if not rid.endswith("_details")
    }


def fetch_rides(
    client: BoschEBikeClient,
    cached_rides: dict[str, list],
    max_activities: int = 200,
) -> dict[str, list[tuple[float, float]]]:
    """Fetch rides, using cache where available."""
    all_rides = dict(cached_rides)
    new_count = 0

    for activity in client.get_activity_headers(max_results=max_activities):
        for ride in activity.get("ride_headers", []):
            if not (ride_id := ride.get("id")) or ride_id in all_rides:
                continue
            if coords := client.get_ride_coordinates(ride_id):
                all_rides[ride_id] = coords
                save_json_cache(f"{ride_id}.json", coords)
                new_count += 1
                print(f"  Fetched ride {ride_id}: {len(coords)} points")

    print(f"\nTotal: {len(all_rides)} rides ({new_count} new, {len(all_rides) - new_count} cached)")
    return all_rides


def generate_heatmap(rides: dict[str, list[tuple[float, float]]], mode: str = "gradient") -> None:
    """Generate the heatmap HTML file."""
    all_coords = [coord for coords in rides.values() for coord in coords]
    if not all_coords:
        print("No coordinates to map!")
        return

    center = [sum(c[i] for c in all_coords) / len(all_coords) for i in range(2)]
    m = folium.Map(location=center, zoom_start=13, tiles="cartodbpositron")

    if mode == "lines":
        for coords in rides.values():
            folium.PolyLine(coords, weight=2, color="#ff4500", opacity=0.1).add_to(m)
        output_file = OUTPUT_DIR / "heatmap_lines.html"
    else:
        HeatMap(all_coords, radius=8, blur=12, max_zoom=17, gradient=GRADIENT).add_to(m)
        output_file = OUTPUT_DIR / "heatmap_gradient.html"

    m.save(output_file)
    print(f"\nSaved heatmap to {output_file}\nTotal points: {len(all_coords)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a heatmap from eBike rides")
    parser.add_argument("--mode", choices=["gradient", "lines"], default="gradient",
                        help="Heatmap style: 'gradient' or 'lines'")
    args = parser.parse_args()

    if not (creds := get_credentials()):
        return

    print("Loading cached rides...")
    cached_rides = load_cached_rides()
    print(f"Found {len(cached_rides)} cached rides")

    print("\nFetching rides from API...")
    with BoschEBikeClient() as client:
        client.login(*creds)
        all_rides = fetch_rides(client, cached_rides)

    print(f"\nGenerating {args.mode} heatmap...")
    generate_heatmap(all_rides, mode=args.mode)


if __name__ == "__main__":
    main()
