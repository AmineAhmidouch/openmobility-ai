
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "storage" / "processed" / "gtfs" / "idfm"

TABLES = [
    "agency",
    "routes",
    "stops",
    "trips",
    "stop_times",
    "calendar",
    "calendar_dates",
]


def main() -> None:
    con = duckdb.connect()

    try:
        # Create reusable views over the Parquet files.
        for table in TABLES:
            path = DATA_DIR / f"{table}.parquet"

            if not path.is_file():
                raise FileNotFoundError(
                    f"Missing Parquet file: {path}"
                )

            sql_path = path.as_posix().replace("'", "''")
            con.execute(
                f"""
                CREATE VIEW {table} AS
                SELECT * FROM read_parquet('{sql_path}')
                """
            )

        print("\n=== GTFS table row counts ===")

        for table in TABLES:
            count = con.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table:20} {count:>12,}")

        print("\n=== Routes with the most scheduled trips ===")

        routes = con.execute("""
            SELECT
                route_id,
                COUNT(*) AS trip_count
            FROM trips
            GROUP BY route_id
            ORDER BY trip_count DESC, route_id
            LIMIT 10
        """).fetchdf()

        print(routes.to_string(index=False))

        print("\n=== Stops with the most scheduled visits ===")

        stops = con.execute("""
            SELECT
                stop_id,
                COUNT(*) AS scheduled_visits
            FROM stop_times
            GROUP BY stop_id
            ORDER BY scheduled_visits DESC, stop_id
            LIMIT 10
        """).fetchdf()

        print(stops.to_string(index=False))

        print("\n=== Scheduled service date coverage ===")

        coverage = con.execute("""
            SELECT
                MIN(start_date) AS earliest_start_date,
                MAX(end_date) AS latest_end_date,
                COUNT(*) AS service_calendar_rows
            FROM calendar
        """).fetchdf()

        print(coverage.to_string(index=False))

    finally:
        con.close()


if __name__ == "__main__":
    main()
