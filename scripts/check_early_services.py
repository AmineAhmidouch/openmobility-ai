
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = (
    PROJECT_ROOT / "storage" / "processed" / "openmobility.duckdb"
)

query = """
SELECT
    t.service_id,
    r.route_type,
    r.route_short_name,
    r.route_long_name,
    COUNT(DISTINCT t.trip_id) AS trip_count
FROM main.stg_gtfs__trips AS t
LEFT JOIN main.stg_gtfs__routes AS r
    ON t.route_id = r.route_id
WHERE t.service_id IN (
    'IDFM:TN:51412288-2026-10-24',
    'IDFM:TN:51440671',
    'IDFM:TN:51468563'
)
GROUP BY
    t.service_id,
    r.route_type,
    r.route_short_name,
    r.route_long_name
ORDER BY trip_count DESC
"""

with duckdb.connect(str(DATABASE_PATH), read_only=True) as connection:
    result = connection.execute(query).df()
    print(result.to_string(index=False))
