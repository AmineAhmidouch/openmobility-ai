
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = (
    PROJECT_ROOT / "storage" / "processed" / "openmobility.duckdb"
)

query = """
WITH dates AS (
    SELECT unnest(generate_series(
        DATE '2026-10-24',
        DATE '2026-10-27',
        INTERVAL 1 DAY
    ))::DATE AS service_date
),
regular_services AS (
    SELECT
        d.service_date,
        COUNT(DISTINCT c.service_id) AS regular_service_count
    FROM dates d
    LEFT JOIN main.stg_gtfs__calendar c
        ON d.service_date BETWEEN c.start_date AND c.end_date
       AND CASE EXTRACT(DOW FROM d.service_date)
            WHEN 0 THEN c.sunday
            WHEN 1 THEN c.monday
            WHEN 2 THEN c.tuesday
            WHEN 3 THEN c.wednesday
            WHEN 4 THEN c.thursday
            WHEN 5 THEN c.friday
            WHEN 6 THEN c.saturday
           END = 1
    GROUP BY d.service_date
),
exceptions AS (
    SELECT
        d.service_date,
        COUNT(DISTINCT CASE
            WHEN cd.exception_type = 1 THEN cd.service_id
        END) AS added_service_count,
        COUNT(DISTINCT CASE
            WHEN cd.exception_type = 2 THEN cd.service_id
        END) AS removed_service_count
    FROM dates d
    LEFT JOIN main.stg_gtfs__calendar_dates cd
        ON d.service_date = cd.service_date
    GROUP BY d.service_date
)
SELECT
    d.service_date,
    r.regular_service_count,
    e.added_service_count,
    e.removed_service_count
FROM dates d
JOIN regular_services r USING (service_date)
JOIN exceptions e USING (service_date)
ORDER BY d.service_date
"""

with duckdb.connect(str(DATABASE_PATH), read_only=True) as connection:
    print(connection.execute(query).df().to_string(index=False))
