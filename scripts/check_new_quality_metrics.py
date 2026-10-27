
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
    median_weekday_trips,
    baseline_observation_count,
    pct_of_post_change_weekday_median,
    coverage_status,
    same_weekday_status
FROM main.mart_gtfs__daily_service_quality
WHERE service_date IN (
    DATE '2026-10-24',
    DATE '2026-10-25',
    DATE '2026-10-26',
    DATE '2026-11-11'
)
ORDER BY service_date
"""

with duckdb.connect(str(database_path), read_only=True) as connection:
    print(connection.execute(query).df().to_string(index=False))
