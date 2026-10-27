
import duckdb

con = duckdb.connect()

base = "storage/processed/gtfs/idfm"

checks = {
    "stop_times_without_trip": f"""
        SELECT COUNT(*)
        FROM read_parquet('{base}/stop_times.parquet') st
        LEFT JOIN read_parquet('{base}/trips.parquet') t
            ON st.trip_id = t.trip_id
        WHERE t.trip_id IS NULL
    """,
    "trips_without_route": f"""
        SELECT COUNT(*)
        FROM read_parquet('{base}/trips.parquet') t
        LEFT JOIN read_parquet('{base}/routes.parquet') r
            ON t.route_id = r.route_id
        WHERE r.route_id IS NULL
    """,
    "stop_times_without_stop": f"""
        SELECT COUNT(*)
        FROM read_parquet('{base}/stop_times.parquet') st
        LEFT JOIN read_parquet('{base}/stops.parquet') s
            ON st.stop_id = s.stop_id
        WHERE s.stop_id IS NULL
    """,
    "duplicate_stop_time_keys": f"""
        SELECT COUNT(*)
        FROM (
            SELECT trip_id, stop_sequence
            FROM read_parquet('{base}/stop_times.parquet')
            GROUP BY trip_id, stop_sequence
            HAVING COUNT(*) > 1
        ) duplicates
    """,
}

for name, query in checks.items():
    result = con.execute(query).fetchone()[0]
    print(f"{name}: {result:,}")
