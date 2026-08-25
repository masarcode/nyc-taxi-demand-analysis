# Reporting table data dictionary

The pipeline writes eight CSV tables that can be loaded directly into
BigQuery with `scripts/load_bigquery.py`.

| Table | Grain | Purpose |
| --- | --- | --- |
| `monthly_summary` | One row per month | Volume, revenue, averages, and acceptance rate |
| `daily_demand` | One row per pickup date | Daily demand and value trend |
| `hourly_demand` | Weekday and pickup hour | Recurring demand windows |
| `pickup_zone_summary` | Pickup taxi zone | Zone demand, value, distance, and duration |
| `route_summary` | Pickup and drop-off zone pair with at least 10,000 accepted trips | High-volume route performance |
| `distance_band_summary` | Trip-distance band | Fare and duration economics by trip length |
| `payment_summary` | TLC payment type | Payment mix and tip behavior |
| `data_quality_summary` | Month and validation outcome | Raw, accepted, rejected, and reason-level counts |

Shared measures include:

- `trip_count`: accepted trip records.
- `gross_booking_value_usd`: sum of TLC `total_amount`; this is not operator
  profit or net revenue.
- `fare_revenue_usd`: sum of `fare_amount` before tips and add-on charges.
- `tips_usd`: nonnegative reported tips. Cash tips are generally not captured.
- `avg_trip_distance_miles`: accepted-trip mean distance.
- `avg_trip_duration_min`: accepted-trip mean duration.
- `tip_share_pct`: reported tips divided by fare amount.

The cleaning rules require an in-month pickup timestamp, a later drop-off,
duration from 1 to 180 minutes, distance from 0 to 100 miles, positive bounded
fare and total amounts, valid taxi-zone identifiers, plausible passenger
counts when reported, and speed no greater than 80 mph.
