# Methodology and limitations

## Scope

The portfolio release processes the six official NYC TLC Yellow Taxi monthly
Parquet partitions from January through June 2025. The files contain
24,083,384 raw rows. Raw files are downloaded directly from the TLC-hosted
CloudFront distribution and are not committed to Git.

## Row-group processing

PyArrow reads one Parquet row group at a time. Each row group is converted to
a pandas DataFrame, validated, enriched, and aggregated before the next group
is read. The full 24-million-row dataset is therefore never loaded into memory
at once.

The optional cleaned-partition writer supplies an explicit Arrow schema. This
prevents changes in nullable integer inference between row groups from causing
the schema mismatch seen in the original prototype.

## Acceptance rules

A trip is retained when it has:

- a valid pickup timestamp inside its source month;
- a later drop-off timestamp and duration from 1 to 180 minutes;
- distance greater than 0 and no more than 100 miles;
- positive, bounded fare and total amounts;
- pickup and drop-off location identifiers from 1 through 265;
- passenger count from 1 through 8 when that field is reported; and
- implied speed no greater than 80 mph.

Rules are applied in a fixed order, so every rejected record is counted once
under its first failing condition. The `data_quality_summary` table preserves
the resulting audit trail by month.

## Analytical limitations

- The six-month period is not a complete annual view and may include seasonal
  effects.
- `total_amount` is treated as gross booking value, not operator profit or net
  revenue.
- Cash tips are generally not captured, so payment-method tip comparisons are
  incomplete.
- Trip records measure completed rides, not unserved demand.
- Taxi zones are operational reporting areas, not necessarily neighborhoods.
- The analysis does not observe driver supply, weather, events, or traffic
  conditions needed to make a causal fleet-allocation forecast.
