import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
import os

# File paths
input_file = "yellow_tripdata_2025-11.parquet"
output_file = "cleaned_taxi_data.parquet"

# Open Parquet file
parquet_file = pq.ParquetFile(input_file)

def clean_chunk(df):
    #1. Drop completely empty rows
    df = df.dropna(how="all")

    df["tpep_pickup_datetime"] = pd.to_datetime(
        df["tpep_pickup_datetime"], errors="coerce"
    )
    df["tpep_dropoff_datetime"] = pd.to_datetime(
        df["tpep_dropoff_datetime"], errors="coerce"
    )

    # Remove invalid timestamps
    df = df.dropna(subset = ["tpep_pickup_datetime", "tpep_dropoff_datetime"])

    # 3. Filter invalid passenger counts
    df = df[df["passenger_count"] > 0]

    # 4. Filter invalid fares
    df = df[(df["fare_amount"] > 0) & (df["fare_amount"] < 1000)]

    # 5. Trip duration (minutes)
    df["trip_duration"] = (
        df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]
    ).dt.total_seconds() / 60

    # 6. Filter unrealistic durations
    df = df[(df["trip_duration"] >= 1) & (df["trip_duration"] <= 180)]

    return df

# Remove old output if exists
if os.path.exists(output_file):
    os.remove(output_file)
    
writer = None

# Iterate through row groups (Parquet "chunks")
for i in range(parquet_file.num_row_groups):
    print(f"Processing row group {i + 1}/{parquet_file.num_row_groups}")

    table = parquet_file.read_row_group(i)
    df = table.to_pandas()

    cleaned_df = clean_chunk(df)

    # Convert back to Arrow Table
    cleaned_table = pa.Table.from_pandas(cleaned_df, preserve_index = False)

    # Writer / append
    if writer is None: 
        writer = pq.ParquetWriter(output_file, cleaned_table.schema)

    writer.write_table(cleaned_table)

# Close writer
if writer:
    writer.close()

print("Parquet ETL processing complete.")