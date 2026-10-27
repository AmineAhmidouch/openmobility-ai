
from pathlib import Path

import duckdb

project_root = Path(__file__).resolve().parents[1]
database_path = (
    project_root / "storage" / "processed" / "openmobility.duckdb"
)


query = """
SELECT
    service_date,
    day_of_week,
    active_route_count,
    total_scheduled_trips,
    previous_day_trip_count,
    ROUND(same_weekday_average_trips, 0)
        AS same_weekday_average_trips,
    pct_of_same_weekday_average,
    coverage_status,
    same_weekday_status
FROM main.mart_gtfs__daily_service_quality
ORDER BY service_date
"""


with duckdb.connect(str(database_path), read_only=True) as connection:
    result = connection.execute(query).df()
    print(result.to_string(index=False))
