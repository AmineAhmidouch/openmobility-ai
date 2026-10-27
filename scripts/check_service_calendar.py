
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = (
    PROJECT_ROOT / "storage" / "processed" / "openmobility.duckdb"
)

query = """
SELECT
    t.service_id,
    COUNT(DISTINCT t.trip_id) AS trip_count,
    COUNT(DISTINCT cd.service_date) AS exception_dates,
    MIN(cd.service_date) AS first_exception_date,
    MAX(cd.service_date) AS last_exception_date,
    STRING_AGG(
        DISTINCT CAST(cd.exception_type AS VARCHAR),
        ', '
    ) AS exception_types
FROM main.stg_gtfs__trips AS t
LEFT JOIN main.stg_gtfs__calendar AS c
    ON t.service_id = c.service_id
LEFT JOIN main.stg_gtfs__calendar_dates AS cd
    ON t.service_id = cd.service_id
WHERE c.service_id IS NULL
GROUP BY t.service_id
ORDER BY trip_count DESC
"""

with duckdb.connect(str(DATABASE_PATH), read_only=True) as connection:
    result = connection.execute(query).df()
    print(result.to_string(index=False))
