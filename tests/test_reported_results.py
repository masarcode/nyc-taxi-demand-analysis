from pathlib import Path

import pandas as pd


OUTPUTS = Path("outputs/tables")


def test_committed_results_support_readme_claims() -> None:
    monthly = pd.read_csv(OUTPUTS / "monthly_summary.csv")
    hourly = pd.read_csv(OUTPUTS / "hourly_demand.csv")
    zones = pd.read_csv(OUTPUTS / "pickup_zone_summary.csv")
    routes = pd.read_csv(OUTPUTS / "route_summary.csv")

    assert int(monthly["raw_rows"].sum()) == 24_083_384
    assert int(monthly["accepted_rows"].sum()) == 21_810_780

    peak_month = monthly.loc[monthly["trip_count"].idxmax()]
    assert peak_month["pickup_month"] == "2025-05"
    assert int(peak_month["trip_count"]) == 4_054_716

    peak_hour = hourly.loc[hourly["trip_count"].idxmax()]
    assert peak_hour["pickup_weekday"] == "Thursday"
    assert int(peak_hour["pickup_hour"]) == 18

    assert zones.iloc[0]["pickup_zone"] == "Upper East Side South"
    assert routes.iloc[0]["pickup_zone"] == "Upper East Side South"
    assert routes.iloc[0]["dropoff_zone"] == "Upper East Side North"
