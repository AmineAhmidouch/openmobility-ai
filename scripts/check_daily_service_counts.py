
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = (
    PROJECT_ROOT / "storage" / "processed" / "openmobility.duckdb"
)

query = """
SELECT
    sd.service_date,
    COUNT(DISTINCT sd.service_id) AS active_service_count,
    COUNT(DISTINCT t.trip_id) AS scheduled_trip_count
FROM main.int_gtfs__service_dates AS sd
LEFT JOIN main.stg_gtfs__trips AS t
    ON sd.service_id = t.service_id
WHERE sd.service_date BETWEEN DATE '2026-10-24'
                          AND DATE '2026-10-27'
GROUP BY sd.service_date
ORDER BY sd.service_date
"""

with duckdb.connect(str(DATABASE_PATH), read_only=True) as connection:
    print(connection.execute(query).df().to_string(index=False))
