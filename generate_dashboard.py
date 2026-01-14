#!/usr/bin/env python3
"""Generate an HTML dashboard summarizing eBike ride data."""

import json
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from python_bosch_ebike_connect import BoschEBikeClient
from python_bosch_ebike_connect.types import RideDetails
from utils import CACHE_DIR, OUTPUT_DIR, get_credentials, load_json_cache, save_json_cache

KM_TO_MILES = 0.621371


def meters_to_miles(meters: float) -> float:
    return meters / 1000 * KM_TO_MILES


def kmh_to_mph(kmh: float) -> float:
    return kmh * KM_TO_MILES


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
    return {rid.replace("_details", ""): data for rid, data in load_json_cache("*_details.json").items()}


def ride_details_to_dict(ride: RideDetails) -> dict:
    """Convert RideDetails to a JSON-serializable dict."""
    return {**asdict(ride), "start_time": ride.start_time.isoformat(), "end_time": ride.end_time.isoformat()}


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
    all_rides: list[RideDetails] = []
    new_count = 0

    for activity in client.get_activity_headers(max_results=max_activities):
        for ride_header in activity.get("ride_headers", []):
            if not (ride_id := ride_header.get("id")):
                continue
            if ride_id in cached_details:
                all_rides.append(dict_to_ride_details(cached_details[ride_id]))
                continue
            try:
                ride = client.get_ride_details(ride_id)
                all_rides.append(ride)
                save_json_cache(f"{ride_id}_details.json", ride_details_to_dict(ride))
                new_count += 1
                print(f"  Fetched ride {ride_id}: {ride.distance / 1000:.1f} km")
            except Exception as e:
                print(f"  Error fetching ride {ride_id}: {e}")

    print(f"\nTotal: {len(all_rides)} rides ({new_count} new, {len(all_rides) - new_count} cached)")
    return all_rides


# === DATA AGGREGATION ===

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def aggregate_ride_data(rides: list[RideDetails]) -> DashboardData:
    """Calculate all summary statistics from ride data."""
    if not rides:
        return DashboardData(
            rides=[], total_distance_mi=0, total_rides=0, total_time_hours=0,
            avg_speed_mph=0, avg_distance_mi=0, longest_ride=None, fastest_ride=None,
            best_day=None, distance_by_day={}, distance_by_month={}, distance_by_weekday={},
        )

    total_distance_mi = meters_to_miles(sum(r.distance for r in rides))
    total_time_hours = sum(r.driving_time for r in rides) / 3_600_000
    speeds = [r.avg_speed for r in rides if r.avg_speed]

    one_year_ago = datetime.now().date() - timedelta(days=365)
    distance_by_day: dict[str, float] = defaultdict(float)
    distance_by_month: dict[str, float] = defaultdict(float)
    distance_by_weekday: dict[str, float] = {day: 0.0 for day in WEEKDAYS}

    for ride in rides:
        dist_mi = meters_to_miles(ride.distance)
        ride_date = ride.start_time.date()
        distance_by_weekday[WEEKDAYS[ride.start_time.weekday()]] += dist_mi
        if ride_date >= one_year_ago:
            distance_by_day[ride_date.strftime("%Y-%m-%d")] += dist_mi
            distance_by_month[ride_date.strftime("%Y-%m")] += dist_mi

    best_day = max(distance_by_day.items(), key=lambda x: x[1]) if distance_by_day else None

    return DashboardData(
        rides=rides,
        total_distance_mi=total_distance_mi,
        total_rides=len(rides),
        total_time_hours=total_time_hours,
        avg_speed_mph=kmh_to_mph(sum(speeds) / len(speeds)) if speeds else 0,
        avg_distance_mi=total_distance_mi / len(rides),
        longest_ride=max(rides, key=lambda r: r.distance),
        fastest_ride=max((r for r in rides if r.avg_speed), key=lambda r: r.avg_speed or 0, default=None),
        best_day=best_day,
        distance_by_day=dict(distance_by_day),
        distance_by_month=dict(distance_by_month),
        distance_by_weekday=distance_by_weekday,
    )


# === CALENDAR SVG GENERATION ===

CALENDAR_COLORS = ["#ebedf0", "#ffedd5", "#fed7aa", "#fb923c", "#ea580c"]


def generate_calendar_svg(distance_by_day: dict[str, float]) -> str:
    """Generate GitHub-style contribution calendar SVG."""
    today, cell_size, cell_gap, margin_left, margin_top = datetime.now().date(), 12, 3, 40, 25
    start_date = today - timedelta(days=365)
    max_dist = max(distance_by_day.values(), default=1.0)

    def get_color(dist: float) -> str:
        if dist == 0:
            return CALENDAR_COLORS[0]
        idx = min(int(dist / max_dist * 4) + 1, 4)
        return CALENDAR_COLORS[idx]

    svg_width = 53 * (cell_size + cell_gap) + margin_left + 10
    svg_height = 7 * (cell_size + cell_gap) + margin_top + 10
    rects, month_labels, current_month = [], [], None

    current = start_date - timedelta(days=(start_date.weekday() + 1) % 7)
    week_col = 0
    while current <= today:
        x = week_col * (cell_size + cell_gap) + margin_left
        y = current.weekday() * (cell_size + cell_gap) + margin_top
        date_str = current.strftime("%Y-%m-%d")
        dist = distance_by_day.get(date_str, 0)

        if current >= start_date:
            rects.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                f'fill="{get_color(dist)}" rx="2"><title>{date_str}: {dist:.1f} mi</title></rect>'
            )
            if current.month != current_month:
                current_month = current.month
                month_labels.append(f'<text x="{x}" y="{margin_top - 8}" class="month-label">{current.strftime("%b")}</text>')

        if current.weekday() == 6:
            week_col += 1
        current += timedelta(days=1)

    step = cell_size + cell_gap
    weekday_labels = "".join(
        f'<text x="0" y="{margin_top + i * step + cell_size}" class="weekday-label">{day}</text>'
        for i, day in [(0, "Mon"), (2, "Wed"), (4, "Fri")]
    )
    return f'''<svg width="{svg_width}" height="{svg_height}" class="calendar-svg">
        <style>.month-label, .weekday-label {{ font-size: 10px; fill: #666; }}</style>
        {weekday_labels}{"".join(month_labels)}{"".join(rects)}
    </svg>'''


# === HTML GENERATION ===


def _record_html(label: str, value: str, date: str) -> str:
    return f'''<div class="record"><span class="record-label">{label}</span>
        <span class="record-value">{value}</span><span class="record-date">{date}</span></div>'''


def generate_dashboard_html(data: DashboardData, heatmap_path: str) -> str:
    """Generate the complete HTML dashboard."""
    records = []
    if data.longest_ride:
        records.append(_record_html(
            "Longest Ride", f"{meters_to_miles(data.longest_ride.distance):.1f} mi",
            data.longest_ride.start_time.strftime('%b %d, %Y')
        ))
    if data.fastest_ride and data.fastest_ride.avg_speed:
        records.append(_record_html(
            "Fastest Avg Speed", f"{kmh_to_mph(data.fastest_ride.avg_speed):.1f} mph",
            data.fastest_ride.start_time.strftime('%b %d, %Y')
        ))
    if data.best_day:
        records.append(_record_html(
            "Most Distance in a Day", f"{data.best_day[1]:.1f} mi",
            datetime.strptime(data.best_day[0], "%Y-%m-%d").strftime("%b %d, %Y")
        ))

    sorted_months = sorted(data.distance_by_month.keys())
    month_labels_list = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in sorted_months]
    month_values = [round(data.distance_by_month[m], 1) for m in sorted_months]
    weekday_values = [round(data.distance_by_weekday[d], 1) for d in WEEKDAYS]
    calendar_svg = generate_calendar_svg(data.distance_by_day)

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
                {"".join(f'<span class="legend-box" style="background: {c};"></span>' for c in CALENDAR_COLORS)}
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
                {"".join(records)}
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
                labels: {json.dumps(WEEKDAYS)},
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


def generate_heatmap() -> str:
    """Generate the heatmap file."""
    print("Generating heatmap...")
    subprocess.run(["python", str(OUTPUT_DIR / "generate_heatmap.py"), "--mode", "lines"], check=True)
    return "heatmap_lines.html"


def main() -> None:
    """Main entry point."""
    if not (creds := get_credentials()):
        return

    print("Loading cached ride details...")
    cached_details = load_cached_ride_details()
    print(f"Found {len(cached_details)} cached ride details")

    print("\nFetching ride details from API...")
    with BoschEBikeClient() as client:
        client.login(*creds)
        rides = fetch_all_ride_details(client, cached_details)

    print("\nAggregating and generating...")
    data = aggregate_ride_data(rides)
    html = generate_dashboard_html(data, generate_heatmap())
    (OUTPUT_DIR / "dashboard.html").write_text(html)

    print(f"\nDashboard saved. Total: {data.total_rides} rides, {data.total_distance_mi:.1f} mi")


if __name__ == "__main__":
    main()
