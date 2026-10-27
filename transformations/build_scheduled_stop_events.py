
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "storage" / "processed" / "gtfs" / "idfm"
OUTPUT_FILE = DATA_DIR / "models" / "scheduled_stop_events.parquet"


def build_scheduled_stop_events(
    data_dir: Path = DATA_DIR,
    output_file: Path = OUTPUT_FILE,
) -> None:
    """Build and validate the scheduled GTFS stop-events Parquet model."""
    data_dir = Path(data_dir)
    output_file = Path(output_file)

    stop_times_path = data_dir / "stop_times.parquet"
    trips_path = data_dir / "trips.parquet"
    routes_path = data_dir / "routes.parquet"
    stops_path = data_dir / "stops.parquet"

    required_files = [
        stop_times_path,
        trips_path,
        routes_path,
        stops_path,
    ]

    for path in required_files:
        if not path.is_file():
            raise FileNotFoundError(f"Required input file not found: {path}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = output_file.with_name(
        output_file.stem + ".tmp.parquet"
    )

    con = duckdb.connect()

    try:
        stop_times_sql_path = stop_times_path.as_posix().replace("'", "''")
        trips_sql_path = trips_path.as_posix().replace("'", "''")
        routes_sql_path = routes_path.as_posix().replace("'", "''")
        stops_sql_path = stops_path.as_posix().replace("'", "''")
        temp_sql_path = temp_file.as_posix().replace("'", "''")
        output_sql_path = output_file.as_posix().replace("'", "''")

        print("Building scheduled stop-events model...")
        print("Processing approximately 12 million records.")

        con.execute(
            f"""
            COPY (
                WITH stop_events AS (
                    SELECT
                        st.trip_id,
                        st.stop_id,
                        TRY_CAST(st.stop_sequence AS INTEGER) AS stop_sequence,
                        NULLIF(TRIM(st.arrival_time), '') AS arrival_time,
                        NULLIF(TRIM(st.departure_time), '') AS departure_time,
                        NULLIF(
                            TRIM(st.start_pickup_drop_off_window), ''
                        ) AS start_pickup_drop_off_window,
                        NULLIF(
                            TRIM(st.end_pickup_drop_off_window), ''
                        ) AS end_pickup_drop_off_window,

                        CASE
                            WHEN NULLIF(TRIM(st.arrival_time), '') IS NULL
                             AND NULLIF(TRIM(st.departure_time), '') IS NULL
                             AND NULLIF(
                                 TRIM(st.start_pickup_drop_off_window), ''
                             ) IS NOT NULL
                             AND NULLIF(
                                 TRIM(st.end_pickup_drop_off_window), ''
                             ) IS NOT NULL
                                THEN 'WINDOW_BASED'
                            WHEN NULLIF(TRIM(st.arrival_time), '') IS NULL
                             AND NULLIF(TRIM(st.departure_time), '') IS NULL
                                THEN 'MISSING_TIME'
                            ELSE 'TIMED'
                        END AS schedule_time_type,

                        CASE
                            WHEN REGEXP_FULL_MATCH(
                                TRIM(st.arrival_time),
                                '[0-9]+:[0-5][0-9]:[0-5][0-9]'
                            )
                            THEN
                                TRY_CAST(
                                    SPLIT_PART(st.arrival_time, ':', 1)
                                    AS INTEGER
                                ) * 3600
                                + TRY_CAST(
                                    SPLIT_PART(st.arrival_time, ':', 2)
                                    AS INTEGER
                                ) * 60
                                + TRY_CAST(
                                    SPLIT_PART(st.arrival_time, ':', 3)
                                    AS INTEGER
                                )
                            ELSE NULL
                        END AS arrival_seconds,

                        CASE
                            WHEN REGEXP_FULL_MATCH(
                                TRIM(st.departure_time),
                                '[0-9]+:[0-5][0-9]:[0-5][0-9]'
                            )
                            THEN
                                TRY_CAST(
                                    SPLIT_PART(st.departure_time, ':', 1)
                                    AS INTEGER
                                ) * 3600
                                + TRY_CAST(
                                    SPLIT_PART(st.departure_time, ':', 2)
                                    AS INTEGER
                                ) * 60
                                + TRY_CAST(
                                    SPLIT_PART(st.departure_time, ':', 3)
                                    AS INTEGER
                                )
                            ELSE NULL
                        END AS departure_seconds,

                        st.pickup_type,
                        st.drop_off_type,
                        st.timepoint,

                        t.service_id,
                        t.trip_headsign,
                        t.direction_id,
                        t.shape_id,
                        t.route_id,

                        r.agency_id,
                        r.route_short_name,
                        r.route_long_name,
                        TRY_CAST(r.route_type AS INTEGER) AS route_type,

                        s.stop_name,
                        TRY_CAST(s.stop_lat AS DOUBLE) AS stop_latitude,
                        TRY_CAST(s.stop_lon AS DOUBLE) AS stop_longitude,
                        TRY_CAST(s.location_type AS INTEGER) AS location_type,
                        s.parent_station,
                        s.wheelchair_boarding

                    FROM read_parquet('{stop_times_sql_path}') AS st
                    LEFT JOIN read_parquet('{trips_sql_path}') AS t
                        ON st.trip_id = t.trip_id
                    LEFT JOIN read_parquet('{routes_sql_path}') AS r
                        ON t.route_id = r.route_id
                    LEFT JOIN read_parquet('{stops_sql_path}') AS s
                        ON st.stop_id = s.stop_id
                )
                SELECT *
                FROM stop_events
            )
            TO '{temp_sql_path}'
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )

        print("Validating transformed data...")

        quality = con.execute(
            f"""
            SELECT
                COUNT(*) AS total_rows,

                COUNT_IF(
                    schedule_time_type = 'WINDOW_BASED'
                ) AS window_based_rows,

                COUNT_IF(
                    schedule_time_type = 'MISSING_TIME'
                ) AS missing_time_rows,

                COUNT_IF(
                    schedule_time_type = 'TIMED'
                    AND (
                        arrival_seconds IS NULL
                        OR departure_seconds IS NULL
                    )
                ) AS invalid_timed_rows,

                COUNT_IF(
                    stop_latitude IS NULL
                    OR stop_longitude IS NULL
                    OR stop_latitude NOT BETWEEN -90 AND 90
                    OR stop_longitude NOT BETWEEN -180 AND 180
                ) AS invalid_coordinate_rows

            FROM read_parquet('{temp_sql_path}')
            """
        ).fetchone()

        (
            total_rows,
            window_based_rows,
            missing_time_rows,
            invalid_timed_rows,
            invalid_coordinate_rows,
        ) = quality

        source_count = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{stop_times_sql_path}')
            """
        ).fetchone()[0]

        print(f"Source stop-time rows:     {source_count:,}")
        print(f"Transformed rows:          {total_rows:,}")
        print(f"Window-based rows:         {window_based_rows:,}")
        print(f"Missing-time rows:         {missing_time_rows:,}")
        print(f"Invalid timed rows:        {invalid_timed_rows:,}")
        print(f"Invalid coordinate rows:   {invalid_coordinate_rows:,}")

        if total_rows != source_count:
            raise ValueError(
                "Row count mismatch: "
                f"source={source_count:,}, transformed={total_rows:,}"
            )

        if missing_time_rows > 0:
            raise ValueError(
                f"Found {missing_time_rows:,} rows without usable schedule times."
            )

        if invalid_timed_rows > 0:
            raise ValueError(
                f"Found {invalid_timed_rows:,} invalid timed rows."
            )

        if invalid_coordinate_rows > 0:
            raise ValueError(
                f"Found {invalid_coordinate_rows:,} rows with invalid coordinates."
            )

        # Publish the new output only after all validations succeed.
        temp_file.replace(output_file)

        print("\nTransformation completed successfully.")
        print(f"Output: {output_file}")
        print(f"Total rows:              {total_rows:,}")

    except Exception:
        if temp_file.exists():
            temp_file.unlink()
        raise

    finally:
        con.close()


if __name__ == "__main__":
    build_scheduled_stop_events()
