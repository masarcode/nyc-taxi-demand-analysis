"""Download the configured public NYC TLC trip partitions and zone lookup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlretrieve


def download(url: str, destination: Path, overwrite: bool = False) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        print(f"Exists: {destination}")
        return
    print(f"Downloading {url}")
    urlretrieve(url, destination)
    print(f"Saved: {destination}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/project.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    for month in config["months"]:
        url = config["trip_url_template"].format(month=month)
        download(url, args.output_dir / f"yellow_tripdata_{month}.parquet", args.overwrite)
    download(
        config["zone_lookup_url"],
        args.output_dir / "taxi_zone_lookup.csv",
        args.overwrite,
    )


if __name__ == "__main__":
    main()
