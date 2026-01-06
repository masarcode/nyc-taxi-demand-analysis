SELECT 
    PULocationID,
    DOLocationID,
    AVG(trip_duration) AS avg_duration_min,
    AVG(total_amount) AS avg_fare,
    COUNT(*) AS total_trips
FROM 
    `nyc-taxi-project-483102.taxi_pricing.cleaned_data`
WHERE 
    trip_distance > 0
GROUP BY 
    PULocationID, DOLocationID
HAVING 
    COUNT(*) > 50
ORDER BY 
    total_trips DESC;