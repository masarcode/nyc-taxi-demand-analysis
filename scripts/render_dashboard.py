"""Render a compact, deterministic SVG dashboard from pipeline outputs."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

import pandas as pd


BLUE = "#2563eb"
NAVY = "#0f172a"
SLATE = "#475569"
GRID = "#dbe4ef"
PANEL = "#ffffff"


def compact(value: float) -> str:
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"


def text(
    x: float,
    y: float,
    value: object,
    size: int = 14,
    fill: str = SLATE,
    weight: int = 400,
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def blue_scale(value: float, minimum: float, maximum: float) -> str:
    if maximum <= minimum:
        fraction = 0.5
    else:
        fraction = (value - minimum) / (maximum - minimum)
    fraction = max(0.0, min(1.0, fraction))
    light = (239, 246, 255)
    dark = (30, 64, 175)
    rgb = tuple(round(a + (b - a) * fraction) for a, b in zip(light, dark))
    return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"


def build_svg(monthly: pd.DataFrame, zones: pd.DataFrame, hourly: pd.DataFrame) -> str:
    total_raw = monthly["raw_rows"].sum()
    total_accepted = monthly["accepted_rows"].sum()
    total_value = monthly["gross_booking_value_usd"].sum()
    average_total = total_value / monthly["trip_count"].sum()

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">',
        '<rect width="1400" height="900" fill="#f8fafc"/>',
        '<style>text{font-family:Inter,Arial,sans-serif} .panel{fill:#fff;stroke:#e2e8f0;stroke-width:1}</style>',
        text(60, 62, "NYC Yellow Taxi Demand & Revenue", 30, NAVY, 700),
        text(60, 91, "January-June 2025 | Validated reporting outputs from 24.1M raw trips", 15),
        '<rect class="panel" x="60" y="125" width="650" height="320" rx="12"/>',
        '<rect class="panel" x="735" y="125" width="605" height="320" rx="12"/>',
        '<rect class="panel" x="60" y="470" width="650" height="360" rx="12"/>',
        '<rect class="panel" x="735" y="470" width="605" height="360" rx="12"/>',
        text(88, 163, "Accepted trips by month", 18, NAVY, 700),
        text(765, 163, "Pipeline summary", 18, NAVY, 700),
        text(88, 508, "Top pickup zones", 18, NAVY, 700),
        text(765, 508, "Demand by weekday and hour", 18, NAVY, 700),
    ]

    chart_x, chart_y, chart_w, chart_h = 110, 195, 565, 190
    maximum = monthly["trip_count"].max() * 1.12
    for index in range(5):
        value = maximum * index / 4
        y = chart_y + chart_h - chart_h * index / 4
        parts.append(f'<line x1="{chart_x}" y1="{y:.1f}" x2="{chart_x + chart_w}" y2="{y:.1f}" stroke="{GRID}"/>')
        parts.append(text(chart_x - 12, y + 5, compact(value), 11, SLATE, anchor="end"))

    points = []
    for index, row in monthly.reset_index(drop=True).iterrows():
        x = chart_x + chart_w * index / max(len(monthly) - 1, 1)
        y = chart_y + chart_h - row["trip_count"] / maximum * chart_h
        points.append((x, y, row))
    parts.append(
        '<polyline fill="none" stroke="#2563eb" stroke-width="4" points="'
        + " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
        + '"/>'
    )
    for x, y, row in points:
        parts.extend(
            [
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{BLUE}"/>',
                text(x, y - 13, compact(row["trip_count"]), 11, NAVY, 600, "middle"),
                text(x, chart_y + chart_h + 28, row["pickup_month"], 11, SLATE, anchor="middle"),
            ]
        )

    kpis = [
        ("RAW RECORDS", compact(total_raw)),
        ("ACCEPTED TRIPS", compact(total_accepted)),
        ("GROSS BOOKING VALUE", f"${compact(total_value)}"),
        ("AVERAGE TOTAL", f"${average_total:,.2f}"),
    ]
    for (label, value), (x, y) in zip(kpis, [(775, 225), (1055, 225), (775, 340), (1055, 340)]):
        parts.append(text(x, y, label, 12, SLATE, 700))
        parts.append(text(x, y + 43, value, 34, NAVY, 700))

    zones = zones.head(10).sort_values("trip_count")
    zone_max = zones["trip_count"].max()
    bar_x, bar_y, bar_w, bar_h = 290, 540, 365, 24
    for index, (_, row) in enumerate(zones.iterrows()):
        y = bar_y + index * 27
        label = row.get("pickup_zone") or str(row["PULocationID"])
        width = row["trip_count"] / zone_max * bar_w
        parts.extend(
            [
                text(bar_x - 12, y + 17, label, 12, SLATE, anchor="end"),
                f'<rect x="{bar_x}" y="{y}" width="{width:.1f}" height="{bar_h}" rx="3" fill="{BLUE}"/>',
                text(bar_x + width + 8, y + 17, compact(row["trip_count"]), 11, NAVY, 600),
            ]
        )

    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    matrix = (
        hourly.pivot_table(index="pickup_weekday", columns="pickup_hour", values="trip_count", aggfunc="sum")
        .reindex(weekday_order)
        .reindex(columns=range(24), fill_value=0)
        .fillna(0)
    )
    heat_x, heat_y, cell_w, cell_h = 850, 548, 18, 32
    heat_min, heat_max = float(matrix.to_numpy().min()), float(matrix.to_numpy().max())
    for row_index, weekday in enumerate(matrix.index):
        parts.append(text(835, heat_y + row_index * cell_h + 21, weekday, 11, SLATE, anchor="end"))
        for hour in range(24):
            value = float(matrix.loc[weekday, hour])
            parts.append(
                f'<rect x="{heat_x + hour * cell_w}" y="{heat_y + row_index * cell_h}" '
                f'width="{cell_w}" height="{cell_h}" fill="{blue_scale(value, heat_min, heat_max)}"/>'
            )
    for hour in range(0, 24, 3):
        parts.append(text(heat_x + hour * cell_w + cell_w / 2, heat_y + 7 * cell_h + 23, hour, 10, SLATE, anchor="middle"))
    parts.append(text(heat_x + 12 * cell_w, heat_y + 7 * cell_h + 48, "Pickup hour", 12, SLATE, 600, "middle"))
    parts.append(text(60, 872, "Source: NYC Taxi & Limousine Commission. Gross booking value is the sum of total_amount for accepted trips.", 11, SLATE))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("outputs/tables"))
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/figures/portfolio_dashboard.svg")
    )
    args = parser.parse_args()

    monthly = pd.read_csv(args.input_dir / "monthly_summary.csv")
    zones = pd.read_csv(args.input_dir / "pickup_zone_summary.csv")
    hourly = pd.read_csv(args.input_dir / "hourly_demand.csv")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_svg(monthly, zones, hourly))
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
