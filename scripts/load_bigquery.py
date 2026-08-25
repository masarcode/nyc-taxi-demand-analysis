"""Load the eight generated reporting tables into BigQuery.

Authentication is intentionally delegated to Google Application Default
Credentials. No key files or project credentials belong in this repository.
"""

from __future__ import annotations

import argparse
from pathlib import Path


TABLES = [
    "monthly_summary",
    "daily_demand",
    "hourly_demand",
    "pickup_zone_summary",
    "route_summary",
    "distance_band_summary",
    "payment_summary",
    "data_quality_summary",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="taxi_reporting")
    parser.add_argument("--input-dir", type=Path, default=Path("outputs/tables"))
    parser.add_argument("--location", default="US")
    args = parser.parse_args()

    from google.cloud import bigquery

    client = bigquery.Client(project=args.project)
    dataset_id = f"{args.project}.{args.dataset}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = args.location
    client.create_dataset(dataset, exists_ok=True)

    for table_name in TABLES:
        source = args.input_dir / f"{table_name}.csv"
        if not source.exists():
            raise FileNotFoundError(f"Missing reporting table: {source}")
        table_id = f"{dataset_id}.{table_name}"
        config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=True,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        with source.open("rb") as handle:
            job = client.load_table_from_file(handle, table_id, job_config=config)
        job.result()
        table = client.get_table(table_id)
        print(f"Loaded {table.num_rows:,} rows into {table_id}")


if __name__ == "__main__":
    main()
