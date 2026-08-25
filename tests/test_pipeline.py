from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nyc_taxi_pipeline.pipeline import CLEANED_SCHEMA, clean_chunk, run_pipeline


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "tpep_pickup_datetime": [
                "2025-01-10 08:00:00",
                "2025-01-10 09:00:00",
                "2025-01-10 10:00:00",
                "2025-02-01 00:00:00",
            ],
            "tpep_dropoff_datetime": [
                "2025-01-10 08:15:00",
                "2025-01-10 09:00:30",
                "2025-01-10 10:20:00",
                "2025-02-01 00:20:00",
            ],
            "passenger_count": [1.0, 1.0, None, 1.0],
            "trip_distance": [3.0, 2.0, 4.0, 4.0],
            "PULocationID": [237, 237, 161, 161],
            "DOLocationID": [236, 236, 237, 237],
            "payment_type": [1, 1, 2, 1],
            "fare_amount": [15.0, 10.0, 18.0, 20.0],
            "tip_amount": [3.0, 2.0, 0.0, 4.0],
            "tolls_amount": [0.0, 0.0, 0.0, 0.0],
            "total_amount": [21.0, 15.0, 22.0, 28.0],
        }
    )


def test_clean_chunk_applies_partition_and_quality_rules() -> None:
    clean, rejected = clean_chunk(sample_frame(), "2025-01")

    assert len(clean) == 2
    assert rejected["invalid_duration"] == 1
    assert rejected["invalid_timestamp_or_partition"] == 1
    assert clean["passenger_count"].isna().sum() == 1
    assert set(clean["pickup_month"]) == {"2025-01"}


def test_clean_chunk_has_stable_arrow_schema() -> None:
    clean, _ = clean_chunk(sample_frame().iloc[[0, 2]], "2025-01")
    table = pa.Table.from_pandas(
        clean,
        schema=CLEANED_SCHEMA,
        preserve_index=False,
        safe=False,
    )
    assert table.schema == CLEANED_SCHEMA


def test_pipeline_writes_eight_reporting_tables(tmp_path: Path) -> None:
    source = tmp_path / "yellow_tripdata_2025-01.parquet"
    pq.write_table(pa.Table.from_pandas(sample_frame()), source, row_group_size=2)
    output_dir = tmp_path / "outputs"

    tables = run_pipeline([source], output_dir, minimum_route_trips=1)

    assert len(tables) == 8
    assert {path.stem for path in output_dir.glob("*.csv")} == set(tables)
    assert int(tables["monthly_summary"]["raw_rows"].sum()) == 4
    assert int(tables["monthly_summary"]["accepted_rows"].sum()) == 2
    assert tables["route_summary"]["trip_count"].sum() == 2
