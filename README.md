# nyc-taxi-demand-analysis

NYC Yellow Taxi Data Pipeline & Demand Analysis

I built this project to analyze New York City Yellow Taxi trip data to understand demand patterns, pricing behavior, and trip characteristics.
The project demonstrates an end-to-end data pipeline, starting from raw data ingestion and cleaning, through cloud storage and querying, and ending with an interactive business intelligence dashboard.

The pipeline follows this flow:

Raw Data → Python ETL → Google Cloud Storage → BigQuery → Google Looker Studio BI Dashboard

### Dataset Description:

Each row in the dataset represents one taxi trip and contains information such as:

- Pickup and drop off locations

- Trip distance

- Trip duration

- Fare and total cost

- Payment method

- Fees and surcharges

Because NYC processes millions of taxi trips per month, this project works with very large-scale data, which is why many of the aggregated values appear large.


### Phase 1: Python ETL (Extract, Transform, Load)
Purpose

The raw taxi data is too large to process in memory at once, so it must be processed in chunks.

What the ETL Script Does

1. Extract

- Reads the raw CSV taxi data in chunks

- Prevents memory overload

2. Transform

- Removes invalid records (e.g., negative distances, zero fares)

- Converts timestamps into usable datetime formats

- Calculates new derived fields:

  - trip_duration (minutes)

  - Ensures numeric columns are valid

3. Load

- Writes cleaned chunks to a new CSV

- Uploads the cleaned dataset to Google Cloud Storage (GCS)

Why Chunking Matters?

Real-world datasets often cannot fit into memory. Chunking is a production-grade technique used by data engineers to process large datasets efficiently.


### Phase 2: Google Cloud Storage (GCS)

The cleaned dataset is uploaded to Google Cloud Storage, which acts as a staging layer between Python and BigQuery.

Why this step matters:

- Separates compute (Python) from storage

- Allows BigQuery to load data efficiently

- Mirrors real-world cloud data pipelines

### Phase 3: BigQuery Data Warehouse
Table Creation

The cleaned data is loaded into BigQuery as a structured table.

Schema Overview

Key fields include:

- PULocationID – Pickup zone ID

- DOLocationID – Dropoff zone ID

- trip_distance – Distance traveled (miles)

- fare_amount – Base fare

- total_amount – Final cost paid (fare + tips + fees)

- trip_duration – Duration in minutes

BigQuery allows fast aggregation and analytics over millions of rows.

### Phase 4: SQL Analysis (queries.sql)

SQL was used to:

- Validate data integrity

- Compute summary statistics

- Prepare data for visualization

Example analyses:

- Average trip cost

- Trip counts per pickup zone

- Relationship between distance and fare

These queries power the BI dashboard.

### Phase 5: Visualization & Analysis (Dashboard)

The final dashboard answers three core business questions.

### 1. Average Trip Cost (Scorecard)

Metric:
AVG(total_amount) = 29.71 USD

What this means:

- On average, a NYC yellow taxi passenger pays $29.71 per trip

This includes:

- Base fare

- Tips

- Tolls

- Congestion and airport fees

Why this matters:

- Gives a clear benchmark for pricing

- Useful for cost-of-living, demand, and revenue analysis

### 2. Busiest Pickup Zones (Bar Chart)

X-axis:
PULocationID (pickup zone identifier)

Y-axis:
Record Count (number of trips)

What this chart shows:

- The top pickup zones by number of taxi trips

- Each bar represents how many rides started in that zone

Important clarification:

- These numbers are counts of trips, not dollars or miles

- Large values (100,000+) are expected because the dataset contains hundreds of thousands of trips

Business insight:

- Taxi demand in NYC is highly concentrated

- A small number of zones generate a disproportionate share of rides

- These areas are critical for:

  - Traffic planning

  - Pricing strategies

  - Fleet allocation

### 3. Trip Distance vs Fare Amount (Scatter Plot)

X-axis:
trip_distance (aggregated)

Y-axis:
fare_amount (aggregated)

What each point represents:

- A group of trips aggregated together

- Not a single taxi ride

Why the numbers look large:

- The chart displays summed values across many trips

For example:

- A value of 2,000,000 on the x-axis does not mean one trip traveled 2M miles

- It means many trips at that distance range combined

Key takeaway:

- There is a strong positive relationship between distance and fare

- Confirms that NYC taxi pricing scales predictably with distance

### Why outliers exist:

- Extreme trips

- Data aggregation

- No heavy filtering applied (intentional for exploratory analysis)

### Key Insights Summary

- Average NYC taxi trip costs = $29.71

- Taxi demand is concentrated in a small number of pickup zones

- Fare pricing increases consistently with trip distance

- Raw data must be cleaned and validated before analysis

- Cloud data warehouses enable fast analytics at scale

### Skills Demonstrated

- Python data processing (ETL, chunking)

- Data cleaning and validation

- Cloud storage (Google Cloud Storage)

- SQL analytics (BigQuery)

- Business intelligence & visualization

- Exploratory data analysis

- Communicating insights from large datasets

### Notes on Real World Relevance

This project mirrors real analytics workflows used in industry:

- Large datasets

- Imperfect data

- Confusing intermediate results

- Iterative understanding

My goal was not perfect charts, but demonstrating the ability to:

- Move data through a pipeline

- Ask meaningful questions

- Interpret aggregated results correctly
