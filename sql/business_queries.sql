-- BigQuery examples for the eight tables loaded by scripts/load_bigquery.py.
-- Replace `your-project` with the configured Google Cloud project ID.

-- Peak demand windows
SELECT
  pickup_weekday,
  pickup_hour,
  trip_count,
  gross_booking_value_usd
FROM `your-project.taxi_reporting.hourly_demand`
ORDER BY trip_count DESC
LIMIT 20;

-- Highest-volume pickup zones with readable names
SELECT
  pickup_borough,
  pickup_zone,
  trip_count,
  avg_total_amount_usd,
  gross_booking_value_usd
FROM `your-project.taxi_reporting.pickup_zone_summary`
ORDER BY trip_count DESC
LIMIT 20;

-- High-volume routes
SELECT
  pickup_zone,
  dropoff_zone,
  trip_count,
  avg_trip_duration_min,
  avg_total_amount_usd
FROM `your-project.taxi_reporting.route_summary`
WHERE trip_count >= 1000
ORDER BY trip_count DESC;

-- Monthly acceptance and demand trend
SELECT
  pickup_month,
  raw_rows,
  accepted_rows,
  acceptance_rate_pct,
  trip_count,
  gross_booking_value_usd
FROM `your-project.taxi_reporting.monthly_summary`
ORDER BY pickup_month;
