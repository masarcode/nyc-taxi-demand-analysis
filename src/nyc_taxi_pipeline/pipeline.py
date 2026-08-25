"""Stream NYC TLC Parquet partitions into validated reporting tables.

The pipeline intentionally processes one Parquet row group at a time. This
keeps memory use bounded and avoids the cross-row-group schema mismatch that
affected the original prototype.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


SOURCE_COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "tip_amount",
    "tolls_amount",
    "total_amount",
]

MEASURE_COLUMNS = [
    "trip_count",
    "total_amount_sum",
    "fare_amount_sum",
    "tip_amount_sum",
    "trip_distance_sum",
    "trip_duration_sum",
]

PAYMENT_LABELS = {
    0: "Not reported",
    1: "Credit card",
    2: "Cash",
    3: "No charge",
    4: "Dispute",
    5: "Unknown",
    6: "Voided trip",
}

DISTANCE_BINS = [-np.inf, 1, 3, 5, 10, 20, np.inf]
DISTANCE_LABELS = ["0-1 mi", "1-3 mi", "3-5 mi", "5-10 mi", "10-20 mi", "20+ mi"]

CLEANED_COLUMNS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "tip_amount",
    "tolls_amount",
    "total_amount",
    "trip_duration_min",
    "speed_mph",
    "pickup_date",
    "pickup_hour",
    "pickup_weekday",
    "pickup_weekday_num",
    "pickup_month",
]

CLEANED_SCHEMA = pa.schema(
    [
        ("tpep_pickup_datetime", pa.timestamp("us")),
        ("tpep_dropoff_datetime", pa.timestamp("us")),
        ("passenger_count", pa.int16()),
        ("trip_distance", pa.float64()),
        ("PULocationID", pa.int16()),
        ("DOLocationID", pa.int16()),
        ("payment_type", pa.int16()),
        ("fare_amount", pa.float64()),
        ("tip_amount", pa.float64()),
        ("tolls_amount", pa.float64()),
        ("total_amount", pa.float64()),
        ("trip_duration_min", pa.float64()),
        ("speed_mph", pa.float64()),
        ("pickup_date", pa.date32()),
        ("pickup_hour", pa.int8()),
        ("pickup_weekday", pa.string()),
        ("pickup_weekday_num", pa.int8()),
        ("pickup_month", pa.string()),
    ]
)


def month_from_path(path: Path) -> str:
    """Extract a YYYY-MM partition label from a TLC filename."""
    match = re.search(r"(20\d{2}-\d{2})", path.name)
    if not match:
        raise ValueError(f"Could not infer a YYYY-MM partition from {path.name}")
    return match.group(1)


def clean_chunk(frame: pd.DataFrame, month: str) -> tuple[pd.DataFrame, Counter[str]]:
    """Clean one row group and return accepted rows plus rejection counts."""
    missing = sorted(set(SOURCE_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Input is missing required columns: {', '.join(missing)}")

    data = frame[SOURCE_COLUMNS].copy()
    for column in ("tpep_pickup_datetime", "tpep_dropoff_datetime"):
        data[column] = pd.to_datetime(data[column], errors="coerce")

    numeric_columns = [column for column in SOURCE_COLUMNS if column not in {
        "tpep_pickup_datetime", "tpep_dropoff_datetime"
    }]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    duration = (
        data["tpep_dropoff_datetime"] - data["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60
    month_start = pd.Period(month, freq="M").start_time
    month_end = month_start + pd.offsets.MonthBegin(1)

    accepted = pd.Series(True, index=data.index)
    rejected: Counter[str] = Counter()

    def reject(mask: pd.Series, reason: str) -> None:
        newly_rejected = mask.fillna(True) & accepted
        rejected[reason] += int(newly_rejected.sum())
        accepted.loc[newly_rejected] = False

    reject(
        data["tpep_pickup_datetime"].isna()
        | data["tpep_dropoff_datetime"].isna()
        | (data["tpep_dropoff_datetime"] <= data["tpep_pickup_datetime"])
        | (data["tpep_pickup_datetime"] < month_start)
        | (data["tpep_pickup_datetime"] >= month_end),
        "invalid_timestamp_or_partition",
    )
    reject((duration < 1) | (duration > 180), "invalid_duration")
    reject(
        data["trip_distance"].isna()
        | (data["trip_distance"] <= 0)
        | (data["trip_distance"] > 100),
        "invalid_distance",
    )
    reject(
        data["fare_amount"].isna()
        | (data["fare_amount"] <= 0)
        | (data["fare_amount"] > 1000),
        "invalid_fare",
    )
    reject(
        data["total_amount"].isna()
        | (data["total_amount"] <= 0)
        | (data["total_amount"] > 2000),
        "invalid_total_amount",
    )
    reject(
        data["PULocationID"].isna()
        | data["DOLocationID"].isna()
        | ~data["PULocationID"].between(1, 265)
        | ~data["DOLocationID"].between(1, 265),
        "invalid_location",
    )
    reject(
        data["passenger_count"].notna()
        & ~data["passenger_count"].between(1, 8),
        "invalid_passenger_count",
    )

    clean = data.loc[accepted].copy()
    clean["trip_duration_min"] = duration.loc[accepted]
    clean["speed_mph"] = clean["trip_distance"] / (clean["trip_duration_min"] / 60)

    unrealistic_speed = clean["speed_mph"] > 80
    rejected["invalid_speed"] += int(unrealistic_speed.sum())
    clean = clean.loc[~unrealistic_speed].copy()

    clean["passenger_count"] = clean["passenger_count"].round().astype("Int16")
    clean["PULocationID"] = clean["PULocationID"].round().astype("int16")
    clean["DOLocationID"] = clean["DOLocationID"].round().astype("int16")
    clean["payment_type"] = clean["payment_type"].fillna(0).round().astype("int16")
    clean["tip_amount"] = clean["tip_amount"].fillna(0).clip(lower=0)
    clean["tolls_amount"] = clean["tolls_amount"].fillna(0).clip(lower=0)
    clean["pickup_date"] = clean["tpep_pickup_datetime"].dt.date
    clean["pickup_hour"] = clean["tpep_pickup_datetime"].dt.hour.astype("int8")
    clean["pickup_weekday"] = clean["tpep_pickup_datetime"].dt.day_name()
    clean["pickup_weekday_num"] = clean["tpep_pickup_datetime"].dt.dayofweek.astype("int8")
    clean["pickup_month"] = month

    return clean[CLEANED_COLUMNS], rejected


def _summarize(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (
        frame.groupby(keys, observed=True, dropna=False)
        .agg(
            trip_count=("total_amount", "size"),
            total_amount_sum=("total_amount", "sum"),
            fare_amount_sum=("fare_amount", "sum"),
            tip_amount_sum=("tip_amount", "sum"),
            trip_distance_sum=("trip_distance", "sum"),
            trip_duration_sum=("trip_duration_min", "sum"),
        )
        .reset_index()
    )


def _combine(frames: list[pd.DataFrame], keys: list[str]) -> pd.DataFrame:
    combined = pd.concat(frames, ignore_index=True)
    return combined.groupby(keys, observed=True, dropna=False)[MEASURE_COLUMNS].sum().reset_index()


def _finish_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    trips = frame["trip_count"].replace(0, np.nan)
    frame = frame.copy()
    frame["avg_total_amount_usd"] = frame["total_amount_sum"] / trips
    frame["avg_fare_amount_usd"] = frame["fare_amount_sum"] / trips
    frame["avg_trip_distance_miles"] = frame["trip_distance_sum"] / trips
    frame["avg_trip_duration_min"] = frame["trip_duration_sum"] / trips
    frame["tip_share_pct"] = np.where(
        frame["fare_amount_sum"] > 0,
        frame["tip_amount_sum"] / frame["fare_amount_sum"] * 100,
        np.nan,
    )
    frame = frame.rename(
        columns={
            "total_amount_sum": "gross_booking_value_usd",
            "fare_amount_sum": "fare_revenue_usd",
            "tip_amount_sum": "tips_usd",
            "trip_distance_sum": "total_trip_distance_miles",
            "trip_duration_sum": "total_trip_duration_min",
        }
    )
    float_columns = frame.select_dtypes(include=["float", "float64"]).columns
    frame[float_columns] = frame[float_columns].round(2)
    return frame


def _load_zones(path: Path | None) -> pd.DataFrame | None:
    if path is None or not path.exists():
        return None
    zones = pd.read_csv(path)
    required = {"LocationID", "Borough", "Zone"}
    if not required.issubset(zones.columns):
        raise ValueError(f"Zone lookup must contain {sorted(required)}")
    return zones[["LocationID", "Borough", "Zone"]].drop_duplicates("LocationID")


def _add_zone_names(
    pickup: pd.DataFrame, routes: pd.DataFrame, zones: pd.DataFrame | None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if zones is None:
        return pickup, routes

    pickup = pickup.merge(zones, left_on="PULocationID", right_on="LocationID", how="left")
    pickup = pickup.drop(columns="LocationID").rename(
        columns={"Borough": "pickup_borough", "Zone": "pickup_zone"}
    )

    pickup_zones = zones.rename(
        columns={
            "LocationID": "PULocationID",
            "Borough": "pickup_borough",
            "Zone": "pickup_zone",
        }
    )
    dropoff_zones = zones.rename(
        columns={
            "LocationID": "DOLocationID",
            "Borough": "dropoff_borough",
            "Zone": "dropoff_zone",
        }
    )
    routes = routes.merge(pickup_zones, on="PULocationID", how="left")
    routes = routes.merge(dropoff_zones, on="DOLocationID", how="left")
    return pickup, routes


def run_pipeline(
    input_files: Iterable[Path],
    output_dir: Path,
    zone_lookup: Path | None = None,
    minimum_route_trips: int = 10000,
    cleaned_dir: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Process TLC partitions and write eight analysis-ready CSV tables."""
    input_files = sorted(Path(path) for path in input_files)
    if not input_files:
        raise ValueError("No Parquet input files were supplied")
    output_dir.mkdir(parents=True, exist_ok=True)
    if cleaned_dir:
        cleaned_dir.mkdir(parents=True, exist_ok=True)

    table_frames: dict[str, list[pd.DataFrame]] = {
        "monthly_summary": [],
        "daily_demand": [],
        "hourly_demand": [],
        "pickup_zone_summary": [],
        "route_summary": [],
        "distance_band_summary": [],
        "payment_summary": [],
    }
    quality_rows: list[dict[str, object]] = []

    for source_path in input_files:
        month = month_from_path(source_path)
        parquet = pq.ParquetFile(source_path)
        raw_rows = 0
        accepted_rows = 0
        monthly_rejections: Counter[str] = Counter()
        writer: pq.ParquetWriter | None = None

        if cleaned_dir:
            output_path = cleaned_dir / f"cleaned_yellow_tripdata_{month}.parquet"
            writer = pq.ParquetWriter(output_path, CLEANED_SCHEMA, compression="snappy")

        try:
            for row_group in range(parquet.num_row_groups):
                frame = parquet.read_row_group(row_group, columns=SOURCE_COLUMNS).to_pandas()
                raw_rows += len(frame)
                clean, rejected = clean_chunk(frame, month)
                accepted_rows += len(clean)
                monthly_rejections.update(rejected)

                if writer is not None:
                    table = pa.Table.from_pandas(
                        clean,
                        schema=CLEANED_SCHEMA,
                        preserve_index=False,
                        safe=False,
                    )
                    writer.write_table(table)

                table_frames["monthly_summary"].append(_summarize(clean, ["pickup_month"]))
                table_frames["daily_demand"].append(_summarize(clean, ["pickup_date"]))
                table_frames["hourly_demand"].append(
                    _summarize(clean, ["pickup_weekday_num", "pickup_weekday", "pickup_hour"])
                )
                table_frames["pickup_zone_summary"].append(_summarize(clean, ["PULocationID"]))
                table_frames["route_summary"].append(
                    _summarize(clean, ["PULocationID", "DOLocationID"])
                )

                with_distance_band = clean.assign(
                    distance_band=pd.cut(
                        clean["trip_distance"],
                        bins=DISTANCE_BINS,
                        labels=DISTANCE_LABELS,
                        right=False,
                    )
                )
                table_frames["distance_band_summary"].append(
                    _summarize(with_distance_band, ["distance_band"])
                )

                with_payment = clean.assign(
                    payment_method=clean["payment_type"].map(PAYMENT_LABELS).fillna("Other")
                )
                table_frames["payment_summary"].append(
                    _summarize(with_payment, ["payment_type", "payment_method"])
                )
        finally:
            if writer is not None:
                writer.close()

        rejected_rows = raw_rows - accepted_rows
        quality_rows.extend(
            [
                {"month": month, "metric": "raw_rows", "row_count": raw_rows},
                {"month": month, "metric": "accepted_rows", "row_count": accepted_rows},
                {"month": month, "metric": "rejected_rows", "row_count": rejected_rows},
            ]
        )
        quality_rows.extend(
            {"month": month, "metric": reason, "row_count": count}
            for reason, count in sorted(monthly_rejections.items())
        )

    key_columns = {
        "monthly_summary": ["pickup_month"],
        "daily_demand": ["pickup_date"],
        "hourly_demand": ["pickup_weekday_num", "pickup_weekday", "pickup_hour"],
        "pickup_zone_summary": ["PULocationID"],
        "route_summary": ["PULocationID", "DOLocationID"],
        "distance_band_summary": ["distance_band"],
        "payment_summary": ["payment_type", "payment_method"],
    }

    tables = {
        name: _finish_metrics(_combine(frames, key_columns[name]))
        for name, frames in table_frames.items()
    }
    tables["route_summary"] = tables["route_summary"].loc[
        tables["route_summary"]["trip_count"] >= minimum_route_trips
    ].copy()

    quality = pd.DataFrame(quality_rows)
    raw_by_month = quality.loc[quality["metric"] == "raw_rows", ["month", "row_count"]].rename(
        columns={"row_count": "raw_rows"}
    )
    accepted_by_month = quality.loc[
        quality["metric"] == "accepted_rows", ["month", "row_count"]
    ].rename(columns={"row_count": "accepted_rows"})
    monthly_quality = raw_by_month.merge(accepted_by_month, on="month")
    monthly_quality["acceptance_rate_pct"] = (
        monthly_quality["accepted_rows"] / monthly_quality["raw_rows"] * 100
    ).round(2)
    tables["monthly_summary"] = tables["monthly_summary"].merge(
        monthly_quality,
        left_on="pickup_month",
        right_on="month",
        how="left",
    ).drop(columns="month")

    zones = _load_zones(zone_lookup)
    tables["pickup_zone_summary"], tables["route_summary"] = _add_zone_names(
        tables["pickup_zone_summary"], tables["route_summary"], zones
    )

    tables["monthly_summary"] = tables["monthly_summary"].sort_values("pickup_month")
    tables["daily_demand"] = tables["daily_demand"].sort_values("pickup_date")
    tables["hourly_demand"] = tables["hourly_demand"].sort_values(
        ["pickup_weekday_num", "pickup_hour"]
    )
    tables["pickup_zone_summary"] = tables["pickup_zone_summary"].sort_values(
        "trip_count", ascending=False
    )
    tables["route_summary"] = tables["route_summary"].sort_values(
        "trip_count", ascending=False
    )
    tables["distance_band_summary"]["distance_band"] = tables[
        "distance_band_summary"
    ]["distance_band"].astype(str)
    tables["data_quality_summary"] = quality.assign(
        pct_of_month_raw=lambda data: data.apply(
            lambda row: row["row_count"]
            / int(raw_by_month.loc[raw_by_month["month"] == row["month"], "raw_rows"].iloc[0])
            * 100,
            axis=1,
        ).round(4)
    )

    ordered_names = [
        "monthly_summary",
        "daily_demand",
        "hourly_demand",
        "pickup_zone_summary",
        "route_summary",
        "distance_band_summary",
        "payment_summary",
        "data_quality_summary",
    ]
    for name in ordered_names:
        tables[name].to_csv(output_dir / f"{name}.csv", index=False)

    return {name: tables[name] for name in ordered_names}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="TLC monthly Parquet files")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/tables"))
    parser.add_argument("--zone-lookup", type=Path)
    parser.add_argument("--minimum-route-trips", type=int, default=10000)
    parser.add_argument("--cleaned-dir", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    tables = run_pipeline(
        args.inputs,
        args.output_dir,
        zone_lookup=args.zone_lookup,
        minimum_route_trips=args.minimum_route_trips,
        cleaned_dir=args.cleaned_dir,
    )
    raw_rows = int(
        tables["data_quality_summary"].loc[
            tables["data_quality_summary"]["metric"] == "raw_rows", "row_count"
        ].sum()
    )
    accepted_rows = int(tables["monthly_summary"]["accepted_rows"].sum())
    print(f"Processed {raw_rows:,} raw rows; accepted {accepted_rows:,}.")
    print(f"Wrote {len(tables)} reporting tables to {args.output_dir}.")


if __name__ == "__main__":
    main()
