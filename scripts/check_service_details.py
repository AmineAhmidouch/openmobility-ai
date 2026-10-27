
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
    MIN(t.service_id) AS service_id_check,
    c.start_date,
    c.end_date,
    c.monday,
    c.tuesday,
    c.wednesday,
    c.thursday,
    c.friday,
    c.saturday,
    c.sunday,
    COUNT(DISTINCT cd.service_date) AS exception_dates
FROM main.stg_gtfs__trips t
LEFT JOIN main.stg_gtfs__calendar c
    ON t.service_id = c.service_id
LEFT JOIN main.stg_gtfs__calendar_dates cd
    ON t.service_id = cd.service_id
WHERE t.service_id IN (
    'IDFM:TN:51412288-2026-10-24',
    'IDFM:TN:51440671',
    'IDFM:TN:51468563'
)
GROUP BY
    t.service_id,
    c.start_date,
    c.end_date,
    c.monday,
    c.tuesday,
    c.wednesday,
    c.thursday,
    c.friday,
    c.saturday,
    c.sunday
ORDER BY t.service_id
"""

with duckdb.connect(str(DATABASE_PATH), read_only=True) as connection:
    print(connection.execute(query).df().to_string(index=False))
