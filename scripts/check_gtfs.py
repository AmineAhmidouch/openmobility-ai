
import logging
import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = Path(
    os.environ.get(
        "OPENMOBILITY_PROCESSED_DIR",
        str(ROOT / "storage" / "processed" / "gtfs" / "idfm"),
    )
)

REQUIRED_FILES = [
    "agency.parquet",
    "calendar.parquet",
    "calendar_dates.parquet",
    "routes.parquet",
    "stops.parquet",
    "stop_times.parquet",
    "trips.parquet",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    # Check that all required files exist.
    missing_files = [
        filename
        for filename in REQUIRED_FILES
        if not (DATA_DIR / filename).is_file()
    ]

    if missing_files:
        for filename in missing_files:
            logger.error("Missing required file: %s", DATA_DIR / filename)
        return 1

    logger.info("Checking GTFS data in %s", DATA_DIR)

    # Use absolute paths so execution works from any working directory.
    con = duckdb.connect(database=":memory:")

    try:
        # Read each Parquet file to verify it is accessible.
        for filename in REQUIRED_FILES:
            path = (DATA_DIR / filename).as_posix().replace("'", "''")
            row_count = con.execute(
                f"SELECT COUNT(*) FROM read_parquet('{path}')"
            ).fetchone()[0]

            logger.info("%s: %s rows", filename, f"{row_count:,}")

        # Check stop_times references valid trips.
        stop_times_path = (
            DATA_DIR / "stop_times.parquet"
        ).as_posix().replace("'", "''")
        trips_path = (
            DATA_DIR / "trips.parquet"
        ).as_posix().replace("'", "''")

        orphan_stop_times = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{stop_times_path}') AS st
            LEFT JOIN read_parquet('{trips_path}') AS t
                ON st.trip_id = t.trip_id
            WHERE t.trip_id IS NULL
            """
        ).fetchone()[0]

        if orphan_stop_times:
            logger.error(
                "Found %s stop_times rows with no matching trip",
                f"{orphan_stop_times:,}",
            )
            return 1

        logger.info("stop_times trip-reference check passed.")

        # Check trips reference valid routes.
        routes_path = (
            DATA_DIR / "routes.parquet"
        ).as_posix().replace("'", "''")

        orphan_trips = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{trips_path}') AS t
            LEFT JOIN read_parquet('{routes_path}') AS r
                ON t.route_id = r.route_id
            WHERE r.route_id IS NULL
            """
        ).fetchone()[0]

        if orphan_trips:
            logger.error(
                "Found %s trips rows with no matching route",
                f"{orphan_trips:,}",
            )
            return 1

        logger.info("trips route-reference check passed.")

        # Check stop_times reference valid stops.
        stops_path = (
            DATA_DIR / "stops.parquet"
        ).as_posix().replace("'", "''")

        orphan_stops = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{stop_times_path}') AS st
            LEFT JOIN read_parquet('{stops_path}') AS s
                ON st.stop_id = s.stop_id
            WHERE s.stop_id IS NULL
            """
        ).fetchone()[0]

        if orphan_stops:
            logger.error(
                "Found %s stop_times rows with no matching stop",
                f"{orphan_stops:,}",
            )
            return 1

        logger.info("stop_times stop-reference check passed.")

    except Exception:
        logger.exception("GTFS integrity checks failed.")
        return 1
    finally:
        con.close()

    logger.info("All GTFS integrity checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
