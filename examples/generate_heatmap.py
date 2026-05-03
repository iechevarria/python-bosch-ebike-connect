#!/usr/bin/env python3
import argparse

import folium
from folium.plugins import HeatMap

from python_bosch_ebike_connect import BoschEBikeClient, fetch_ride_coords
from utils import OUTPUT_DIR, RIDE_CACHE, get_credentials

GRADIENT = {0.0: "#000000", 0.2: "#ff4500", 0.4: "#ff6a00", 0.6: "#ffa500", 0.8: "#ffcc00", 1.0: "#ffffff"}


def generate_heatmap(rides: dict[str, list[tuple[float, float]]], mode: str = "gradient") -> None:
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

    print("Fetching rides from API...")
    with BoschEBikeClient() as client:
        client.login(*creds)
        all_rides = fetch_ride_coords(client, RIDE_CACHE)

    print(f"\nGenerating {args.mode} heatmap...")
    generate_heatmap(all_rides, mode=args.mode)


if __name__ == "__main__":
    main()
