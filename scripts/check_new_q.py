
from pathlib import Path

import duckdb

project_root = Path(__file__).resolve().parents[1]
database_path = (
    project_root / "storage" / "processed" / "openmobility.duckdb"
)

query = """
SELECT
    service_date,
    total_scheduled_trips,
    coverage_status,
    same_weekday_status,
    post_change_median_status
FROM main.mart_gtfs__daily_service_quality
ORDER BY service_date
"""

with duckdb.connect(str(database_path), read_only=True) as connection:
    print(connection.execute(query).df().to_string(index=False))