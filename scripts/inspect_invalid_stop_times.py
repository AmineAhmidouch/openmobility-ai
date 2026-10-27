
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = (
    ROOT
    / "storage"
    / "processed"
    / "gtfs"
    / "idfm"
    / "models"
    / "scheduled_stop_events.parquet"
)

con = duckdb.connect()

try:
    path = DATA_FILE.as_posix()

    print("=== Invalid time patterns ===")

    patterns = con.execute(f"""
        SELECT
            arrival_time,
            departure_time,
            COUNT(*) AS row_count
        FROM read_parquet('{path}')
        WHERE arrival_seconds IS NULL
           OR departure_seconds IS NULL
        GROUP BY arrival_time, departure_time
        ORDER BY row_count DESC
        LIMIT 20
    """).fetchdf()

    print(patterns.to_string(index=False))

    print("\n=== Related pickup/drop-off window fields ===")

    windows = con.execute(f"""
        SELECT
            start_pickup_drop_off_window,
            end_pickup_drop_off_window,
            pickup_type,
            drop_off_type,
            COUNT(*) AS row_count
        FROM read_parquet(
            '{(
                ROOT / "storage" / "processed" / "gtfs" / "idfm"
                / "stop_times.parquet"
            ).as_posix()}'
        ) st
        WHERE NULLIF(TRIM(arrival_time), '') IS NULL
           OR NULLIF(TRIM(departure_time), '') IS NULL
        GROUP BY ALL
        ORDER BY row_count DESC
        LIMIT 20
    """).fetchdf()

    print(windows.to_string(index=False))

    print("\n=== Coordinate ranges ===")

    coordinates = con.execute(f"""
        SELECT
            MIN(stop_latitude) AS min_latitude,
            MAX(stop_latitude) AS max_latitude,
            MIN(stop_longitude) AS min_longitude,
            MAX(stop_longitude) AS max_longitude,
            COUNT(*) FILTER (
                WHERE stop_latitude NOT BETWEEN -90 AND 90
                   OR stop_longitude NOT BETWEEN -180 AND 180
            ) AS invalid_coordinates
        FROM read_parquet('{path}')
    """).fetchdf()

    print(coordinates.to_string(index=False))

finally:
    con.close()
