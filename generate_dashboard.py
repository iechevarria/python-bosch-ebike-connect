#!/usr/bin/env python3
"""Generate an HTML dashboard summarizing eBike ride data."""

import json
import os
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from python_bosch_ebike_connect import BoschEBikeClient
from python_bosch_ebike_connect.types import RideDetails

CACHE_DIR = Path(__file__).parent / ".ride_cache"
OUTPUT_DIR = Path(__file__).parent


KM_TO_MILES = 0.621371
KMH_TO_MPH = 0.621371


@dataclass
class DashboardData:
    """Aggregated ride data for the dashboard."""

    rides: list[RideDetails]

    # Summary stats
    total_distance_mi: float
    total_rides: int
    total_time_hours: float

    # Averages
    avg_speed_mph: float
    avg_distance_mi: float

    # Records
    longest_ride: RideDetails | None
    fastest_ride: RideDetails | None
    best_day: tuple[str, float] | None  # (date_str, distance_mi)

    # Calendar data: dict[date_str, distance_mi]
    distance_by_day: dict[str, float]

    # Monthly data: dict[month_str, distance_mi]
    distance_by_month: dict[str, float]

    # Weekly patterns: dict[weekday_name, distance_mi]
    distance_by_weekday: dict[str, float]


# === CACHING FUNCTIONS ===


def load_cached_ride_details() -> dict[str, dict]:
    """Load all cached ride details."""
    if not CACHE_DIR.exists():
        return {}

    details = {}
    for file in CACHE_DIR.glob("*_details.json"):
        ride_id = file.stem.replace("_details", "")
        with open(file) as f:
            details[ride_id] = json.load(f)
    return details


def save_ride_details_to_cache(ride_id: str, details: dict) -> None:
    """Save ride details to cache."""
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CACHE_DIR / f"{ride_id}_details.json", "w") as f:
        json.dump(details, f)


def ride_details_to_dict(ride: RideDetails) -> dict:
    """Convert RideDetails to a JSON-serializable dict."""
    data = asdict(ride)
    data["start_time"] = ride.start_time.isoformat()
    data["end_time"] = ride.end_time.isoformat()
    return data


def dict_to_ride_details(data: dict) -> RideDetails:
    """Convert a dict back to RideDetails."""
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


def fetch_all_ride_details(
    client: BoschEBikeClient,
    cached_details: dict[str, dict],
    max_activities: int = 200,
) -> list[RideDetails]:
    """Fetch all ride details, using cache where available."""
    activities = client.get_activity_headers(max_results=max_activities)

    all_rides: list[RideDetails] = []
    new_count = 0
    cached_count = 0

    for activity in activities:
        for ride_header in activity.get("ride_headers", []):
            ride_id = ride_header.get("id")
            if not ride_id:
                continue

            if ride_id in cached_details:
                all_rides.append(dict_to_ride_details(cached_details[ride_id]))
                cached_count += 1
                continue

            # Fetch from API
            try:
                ride = client.get_ride_details(ride_id)
                all_rides.append(ride)
                save_ride_details_to_cache(ride_id, ride_details_to_dict(ride))
                new_count += 1
                print(f"  Fetched ride {ride_id}: {ride.distance / 1000:.1f} km")
            except Exception as e:
                print(f"  Error fetching ride {ride_id}: {e}")

    print(f"\nTotal: {len(all_rides)} rides ({new_count} new, {cached_count} cached)")
    return all_rides


# === DATA AGGREGATION ===


def aggregate_ride_data(rides: list[RideDetails]) -> DashboardData:
    """Calculate all summary statistics from ride data."""
    if not rides:
        return DashboardData(
            rides=[],
            total_distance_mi=0,
            total_rides=0,
            total_time_hours=0,
            avg_speed_mph=0,
            avg_distance_mi=0,
            longest_ride=None,
            fastest_ride=None,
            best_day=None,
            distance_by_day={},
            distance_by_month={},
            distance_by_weekday={},
        )

    # Summary stats (convert to miles)
    total_distance_mi = sum(r.distance for r in rides) / 1000 * KM_TO_MILES
    total_time_hours = sum(r.driving_time for r in rides) / 1000 / 3600

    # Averages (convert to mph)
    speeds = [r.avg_speed for r in rides if r.avg_speed]
    avg_speed_mph = (sum(speeds) / len(speeds) * KMH_TO_MPH) if speeds else 0
    avg_distance_mi = total_distance_mi / len(rides)

    # Records
    longest_ride = max(rides, key=lambda r: r.distance)
    fastest_ride = max(
        (r for r in rides if r.avg_speed), key=lambda r: r.avg_speed or 0, default=None
    )

    # Calendar data (last 12 months) - in miles
    today = datetime.now().date()
    one_year_ago = today - timedelta(days=365)
    distance_by_day: dict[str, float] = defaultdict(float)
    for ride in rides:
        ride_date = ride.start_time.date()
        if ride_date >= one_year_ago:
            date_str = ride_date.strftime("%Y-%m-%d")
            distance_by_day[date_str] += ride.distance / 1000 * KM_TO_MILES

    # Best day record
    best_day = None
    if distance_by_day:
        best_date = max(distance_by_day, key=lambda d: distance_by_day[d])
        best_day = (best_date, distance_by_day[best_date])

    # Monthly data (last 12 months) - in miles
    distance_by_month: dict[str, float] = defaultdict(float)
    for ride in rides:
        ride_date = ride.start_time.date()
        if ride_date >= one_year_ago:
            month_str = ride_date.strftime("%Y-%m")
            distance_by_month[month_str] += ride.distance / 1000 * KM_TO_MILES

    # Weekly patterns (all time) - in miles
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    distance_by_weekday: dict[str, float] = {day: 0.0 for day in weekdays}
    for ride in rides:
        weekday_idx = ride.start_time.weekday()
        distance_by_weekday[weekdays[weekday_idx]] += ride.distance / 1000 * KM_TO_MILES

    return DashboardData(
        rides=rides,
        total_distance_mi=total_distance_mi,
        total_rides=len(rides),
        total_time_hours=total_time_hours,
        avg_speed_mph=avg_speed_mph,
        avg_distance_mi=avg_distance_mi,
        longest_ride=longest_ride,
        fastest_ride=fastest_ride,
        best_day=best_day,
        distance_by_day=dict(distance_by_day),
        distance_by_month=dict(distance_by_month),
        distance_by_weekday=distance_by_weekday,
    )


# === CALENDAR SVG GENERATION ===


def generate_calendar_svg(distance_by_day: dict[str, float]) -> str:
    """Generate GitHub-style contribution calendar SVG."""
    today = datetime.now().date()
    start_date = today - timedelta(days=365)

    # Find max distance for color scaling
    max_distance = max(distance_by_day.values()) if distance_by_day else 1.0

    def get_color(distance: float) -> str:
        if distance == 0:
            return "#ebedf0"  # Light gray for empty
        ratio = distance / max_distance
        if ratio < 0.25:
            return "#ffedd5"  # Lightest orange
        elif ratio < 0.5:
            return "#fed7aa"
        elif ratio < 0.75:
            return "#fb923c"
        return "#ea580c"  # Darkest orange

    cell_size = 12
    cell_gap = 3
    margin_left = 40
    margin_top = 25

    # Calculate dimensions
    weeks = 53
    svg_width = weeks * (cell_size + cell_gap) + margin_left + 10
    svg_height = 7 * (cell_size + cell_gap) + margin_top + 10

    rects = []
    month_labels = []

    # Track months for labels
    current_month = None

    # Start from the first Sunday on or before start_date
    current = start_date
    while current.weekday() != 6:  # 6 = Sunday
        current -= timedelta(days=1)

    week_col = 0
    while current <= today:
        day_of_week = current.weekday()
        # Adjust: GitHub shows Sun at top, we'll show Mon at top
        row = day_of_week

        date_str = current.strftime("%Y-%m-%d")
        distance = distance_by_day.get(date_str, 0)

        x = week_col * (cell_size + cell_gap) + margin_left
        y = row * (cell_size + cell_gap) + margin_top

        if current >= start_date:
            rects.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                f'fill="{get_color(distance)}" rx="2" '
                f'data-date="{date_str}" data-distance="{distance:.1f}">'
                f"<title>{date_str}: {distance:.1f} mi</title></rect>"
            )

        # Month label at the start of each month
        if current.month != current_month and current >= start_date:
            current_month = current.month
            month_name = current.strftime("%b")
            month_labels.append(
                f'<text x="{x}" y="{margin_top - 8}" '
                f'class="month-label">{month_name}</text>'
            )

        if day_of_week == 6:  # Sunday, move to next week
            week_col += 1
        current += timedelta(days=1)

    weekday_labels = """
        <text x="0" y="{y1}" class="weekday-label">Mon</text>
        <text x="0" y="{y2}" class="weekday-label">Wed</text>
        <text x="0" y="{y3}" class="weekday-label">Fri</text>
    """.format(
        y1=margin_top + cell_size,
        y2=margin_top + 2 * (cell_size + cell_gap) + cell_size,
        y3=margin_top + 4 * (cell_size + cell_gap) + cell_size,
    )

    return f"""
    <svg width="{svg_width}" height="{svg_height}" class="calendar-svg">
        <style>
            .month-label {{ font-size: 10px; fill: #666; }}
            .weekday-label {{ font-size: 10px; fill: #666; }}
        </style>
        {weekday_labels}
        {''.join(month_labels)}
        {''.join(rects)}
    </svg>
    """


# === HTML GENERATION ===


def generate_dashboard_html(data: DashboardData, heatmap_path: str) -> str:
    """Generate the complete HTML dashboard."""

    # Format records
    longest_info = ""
    if data.longest_ride:
        distance_mi = data.longest_ride.distance / 1000 * KM_TO_MILES
        longest_info = f"""
            <div class="record">
                <span class="record-label">Longest Ride</span>
                <span class="record-value">{distance_mi:.1f} mi</span>
                <span class="record-date">{data.longest_ride.start_time.strftime('%b %d, %Y')}</span>
            </div>
        """

    fastest_info = ""
    if data.fastest_ride and data.fastest_ride.avg_speed:
        speed_mph = data.fastest_ride.avg_speed * KMH_TO_MPH
        fastest_info = f"""
            <div class="record">
                <span class="record-label">Fastest Avg Speed</span>
                <span class="record-value">{speed_mph:.1f} mph</span>
                <span class="record-date">{data.fastest_ride.start_time.strftime('%b %d, %Y')}</span>
            </div>
        """

    best_day_info = ""
    if data.best_day:
        date_str, distance_mi = data.best_day
        formatted_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d, %Y")
        best_day_info = f"""
            <div class="record">
                <span class="record-label">Most Distance in a Day</span>
                <span class="record-value">{distance_mi:.1f} mi</span>
                <span class="record-date">{formatted_date}</span>
            </div>
        """

    # Generate calendar
    calendar_svg = generate_calendar_svg(data.distance_by_day)

    # Prepare chart data
    # Sort months chronologically
    sorted_months = sorted(data.distance_by_month.keys())
    month_labels_list = [
        datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in sorted_months
    ]
    month_values = [round(data.distance_by_month[m], 1) for m in sorted_months]

    weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_values = [round(data.distance_by_weekday[d], 1) for d in weekday_order]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>eBike Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f8f9fa;
            color: #1a1a2e;
            line-height: 1.6;
            padding: 2rem;
        }}

        header {{
            text-align: center;
            margin-bottom: 2rem;
        }}

        header h1 {{
            font-size: 2rem;
            font-weight: 600;
            color: #1a1a2e;
        }}

        header .subtitle {{
            color: #666;
            font-size: 0.9rem;
            margin-top: 0.5rem;
        }}

        .dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            max-width: 1400px;
            margin: 0 auto;
        }}

        .card {{
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .card-full-width {{
            grid-column: 1 / -1;
        }}

        .card h2 {{
            font-size: 1rem;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 1rem;
        }}

        /* Heatmap iframe */
        .heatmap-container {{
            border-radius: 8px;
            overflow: hidden;
        }}

        .heatmap-container iframe {{
            width: 100%;
            height: 500px;
            border: none;
        }}

        /* Stats grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 1rem;
        }}

        .stat {{
            text-align: center;
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 8px;
        }}

        .stat-value {{
            display: block;
            font-size: 1.75rem;
            font-weight: 700;
            color: #ea580c;
        }}

        .stat-label {{
            display: block;
            font-size: 0.8rem;
            color: #666;
            margin-top: 0.25rem;
        }}

        /* Records */
        .records-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}

        .record {{
            display: flex;
            flex-wrap: wrap;
            align-items: baseline;
            padding: 0.75rem;
            background: #f8f9fa;
            border-radius: 8px;
        }}

        .record-label {{
            font-weight: 500;
            color: #666;
            flex: 1;
        }}

        .record-value {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #ea580c;
            margin-right: 0.5rem;
        }}

        .record-date {{
            font-size: 0.8rem;
            color: #999;
        }}

        /* Calendar */
        .calendar-container {{
            overflow-x: auto;
            padding: 0.5rem 0;
        }}

        .calendar-svg rect {{
            cursor: pointer;
            transition: opacity 0.2s;
        }}

        .calendar-svg rect:hover {{
            opacity: 0.8;
            stroke: #ea580c;
            stroke-width: 1;
        }}

        /* Charts */
        .chart-container {{
            position: relative;
            height: 250px;
        }}

        /* Legend */
        .calendar-legend {{
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 0.25rem;
            margin-top: 1rem;
            font-size: 0.75rem;
            color: #666;
        }}

        .legend-box {{
            width: 12px;
            height: 12px;
            border-radius: 2px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>eBike Dashboard</h1>
        <p class="subtitle">Generated on {datetime.now().strftime('%B %d, %Y')}</p>
    </header>

    <main class="dashboard">
        <!-- Heatmap -->
        <section class="card card-full-width">
            <h2>Ride Heatmap</h2>
            <div class="heatmap-container">
                <iframe src="{heatmap_path}"></iframe>
            </div>
        </section>

        <!-- Activity Calendar -->
        <section class="card card-full-width">
            <h2>Activity Calendar (Last 12 Months)</h2>
            <div class="calendar-container">
                {calendar_svg}
            </div>
            <div class="calendar-legend">
                <span>Less</span>
                <span class="legend-box" style="background: #ebedf0;"></span>
                <span class="legend-box" style="background: #ffedd5;"></span>
                <span class="legend-box" style="background: #fed7aa;"></span>
                <span class="legend-box" style="background: #fb923c;"></span>
                <span class="legend-box" style="background: #ea580c;"></span>
                <span>More</span>
            </div>
        </section>

        <!-- Summary Stats -->
        <section class="card">
            <h2>Summary</h2>
            <div class="stats-grid">
                <div class="stat">
                    <span class="stat-value">{data.total_distance_mi:,.0f}</span>
                    <span class="stat-label">Total miles</span>
                </div>
                <div class="stat">
                    <span class="stat-value">{data.total_rides}</span>
                    <span class="stat-label">Rides</span>
                </div>
                <div class="stat">
                    <span class="stat-value">{data.total_time_hours:.0f}</span>
                    <span class="stat-label">Hours</span>
                </div>
            </div>
        </section>

        <!-- Records -->
        <section class="card">
            <h2>Records</h2>
            <div class="records-list">
                {longest_info}
                {fastest_info}
                {best_day_info}
            </div>
        </section>

        <!-- Monthly Distance Chart -->
        <section class="card">
            <h2>Monthly Distance</h2>
            <div class="chart-container">
                <canvas id="monthlyChart"></canvas>
            </div>
        </section>

        <!-- Weekly Patterns Chart -->
        <section class="card">
            <h2>Weekly Patterns</h2>
            <div class="chart-container">
                <canvas id="weeklyChart"></canvas>
            </div>
        </section>
    </main>

    <script>
        // Monthly chart
        new Chart(document.getElementById('monthlyChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(month_labels_list)},
                datasets: [{{
                    label: 'Distance (mi)',
                    data: {json.dumps(month_values)},
                    backgroundColor: '#fb923c',
                    borderRadius: 4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        grid: {{ color: '#eee' }}
                    }},
                    x: {{
                        grid: {{ display: false }}
                    }}
                }}
            }}
        }});

        // Weekly chart
        new Chart(document.getElementById('weeklyChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(weekday_order)},
                datasets: [{{
                    label: 'Total Distance (mi)',
                    data: {json.dumps(weekday_values)},
                    backgroundColor: '#fb923c',
                    borderRadius: 4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        grid: {{ color: '#eee' }}
                    }},
                    x: {{
                        grid: {{ display: false }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""


def ensure_heatmap_exists() -> str:
    """Ensure the heatmap file exists, generate if needed."""
    heatmap_path = OUTPUT_DIR / "heatmap_lines.html"
    if not heatmap_path.exists():
        print("Heatmap not found, generating...")
        subprocess.run(
            ["python", str(OUTPUT_DIR / "generate_heatmap.py"), "--mode", "lines"],
            check=True,
        )
    return "heatmap_lines.html"


def main() -> None:
    """Main entry point."""
    username = os.getenv("EBIKE_USERNAME")
    password = os.getenv("EBIKE_PASSWORD")

    if not username or not password:
        print("Please set EBIKE_USERNAME and EBIKE_PASSWORD environment variables")
        return

    print("Loading cached ride details...")
    cached_details = load_cached_ride_details()
    print(f"Found {len(cached_details)} cached ride details")

    print("\nFetching ride details from API...")
    with BoschEBikeClient() as client:
        client.login(username, password)
        rides = fetch_all_ride_details(client, cached_details)

    print("\nAggregating ride data...")
    data = aggregate_ride_data(rides)

    print("\nEnsuring heatmap exists...")
    heatmap_path = ensure_heatmap_exists()

    print("\nGenerating dashboard...")
    html = generate_dashboard_html(data, heatmap_path)

    output_file = OUTPUT_DIR / "dashboard.html"
    with open(output_file, "w") as f:
        f.write(html)

    print(f"\nDashboard saved to {output_file}")
    print(f"Total rides: {data.total_rides}")
    print(f"Total distance: {data.total_distance_mi:.1f} mi")


if __name__ == "__main__":
    main()
