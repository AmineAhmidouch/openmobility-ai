from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = (
    PROJECT_ROOT / "storage" / "processed" / "openmobility.duckdb"
)
GTFS_DIR = PROJECT_ROOT / "storage" / "processed" / "gtfs" / "idfm"

connection = duckdb.connect(str(DATABASE_PATH), read_only=True)

try:
    print("\n=== Top 15 routes by scheduled trip count ===")

    print(
        connection.execute(
            """
            SELECT
                route_id,
                route_short_name,
                route_long_name,
                route_type,
                scheduled_trip_count,
                scheduled_stop_event_count,
                distinct_stop_count,
                distinct_service_count
            FROM main.mart_gtfs__route_schedule_profile
            ORDER BY scheduled_trip_count DESC
            LIMIT 15
            """
        ).df().to_string(index=False)
    )

    print("\n=== Route counts by GTFS route type ===")

    print(
        connection.execute(
            """
            SELECT
                route_type,
                COUNT(*) AS route_count,
                SUM(scheduled_trip_count) AS total_scheduled_trips,
                ROUND(AVG(scheduled_trip_count), 1)
                    AS avg_trips_per_route
            FROM main.mart_gtfs__route_schedule_profile
            GROUP BY route_type
            ORDER BY route_type
            """
        ).df().to_string(index=False)
    )

    print("\n=== GTFS calendar coverage ===")

    print(
        connection.execute(
            """
            SELECT
                MIN(start_date) AS earliest_calendar_date,
                MAX(end_date) AS latest_calendar_date,
                COUNT(*) AS calendar_rows
            FROM read_parquet(?)
            """,
            [str(GTFS_DIR / "calendar.parquet")],
        ).df().to_string(index=False)
    )

    print("\n=== GTFS calendar exceptions ===")

    print(
        connection.execute(
            """
            SELECT
                exception_type,
                COUNT(*) AS exception_count,
                MIN(date) AS earliest_exception_date,
                MAX(date) AS latest_exception_date
            FROM read_parquet(?)
            GROUP BY exception_type
            ORDER BY exception_type
            """,
            [str(GTFS_DIR / "calendar_dates.parquet")],
        ).df().to_string(index=False)
    )

    print("\n=== Top 30 routes on 2026-10-24 ===")

    print(
        connection.execute(
            """
            SELECT
                service_date,
                route_id,
                agency_id,
                route_short_name,
                route_long_name,
                route_type,
                scheduled_trip_count
            FROM main.mart_gtfs__daily_route_service
            WHERE service_date = DATE '2026-10-24'
            ORDER BY scheduled_trip_count DESC
            LIMIT 30
            """
        ).df().to_string(index=False)
    )

    print("\n=== Daily scheduled service totals ===")

    print(
        connection.execute(
            """
            SELECT
                service_date,
                COUNT(*) AS active_route_count,
                SUM(scheduled_trip_count) AS total_scheduled_trips
            FROM main.mart_gtfs__daily_route_service
            GROUP BY service_date
            ORDER BY service_date
            """
        ).df().to_string(index=False)
    )

    print("\n=== Service-date diagnostics ===")

    print(
        connection.execute(
            """
            WITH service_counts AS (
                SELECT
                    service_date,
                    COUNT(DISTINCT service_id) AS active_services
                FROM main.int_gtfs__service_dates
                GROUP BY service_date
            ),

            exception_counts AS (
                SELECT
                    service_date,
                    COUNT(*) FILTER (
                        WHERE exception_type = 1
                    ) AS added_services,
                    COUNT(*) FILTER (
                        WHERE exception_type = 2
                    ) AS removed_services
                FROM main.stg_gtfs__calendar_dates
                GROUP BY service_date
            ),

            trip_counts AS (
                SELECT
                    sd.service_date,
                    COUNT(DISTINCT t.trip_id) AS scheduled_trips
                FROM main.int_gtfs__service_dates AS sd
                INNER JOIN main.stg_gtfs__trips AS t
                    ON sd.service_id = t.service_id
                GROUP BY sd.service_date
            )

            SELECT
                s.service_date,
                s.active_services,
                COALESCE(e.added_services, 0) AS added_services,
                COALESCE(e.removed_services, 0) AS removed_services,
                COALESCE(t.scheduled_trips, 0) AS scheduled_trips
            FROM service_counts AS s
            LEFT JOIN exception_counts AS e
                ON s.service_date = e.service_date
            LEFT JOIN trip_counts AS t
                ON s.service_date = t.service_date
            ORDER BY s.service_date
            """
        ).df().to_string(index=False)
    )

    print("\n=== Detailed calendar diagnostics: 24-29 October ===")

    print(
        connection.execute(
            """
            WITH dates AS (
                SELECT unnest(
                    generate_series(
                        DATE '2026-10-24',
                        DATE '2026-10-29',
                        INTERVAL 1 DAY
                    )
                )::DATE AS service_date
            ),

            regular_services AS (
                SELECT
                    d.service_date,
                    COUNT(DISTINCT c.service_id)
                        AS regular_service_count
                FROM dates AS d
                CROSS JOIN main.stg_gtfs__calendar AS c
                WHERE d.service_date BETWEEN c.start_date AND c.end_date
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
                    service_date,
                    COUNT(DISTINCT CASE
                        WHEN exception_type = 1 THEN service_id
                    END) AS added_service_count,
                    COUNT(DISTINCT CASE
                        WHEN exception_type = 2 THEN service_id
                    END) AS removed_service_count
                FROM main.stg_gtfs__calendar_dates
                WHERE service_date BETWEEN
                    DATE '2026-10-24' AND DATE '2026-10-29'
                GROUP BY service_date
            ),

            final_services AS (
                SELECT
                    service_date,
                    COUNT(DISTINCT service_id)
                        AS active_service_count
                FROM main.int_gtfs__service_dates
                WHERE service_date BETWEEN
                    DATE '2026-10-24' AND DATE '2026-10-29'
                GROUP BY service_date
            ),

            trips AS (
                SELECT
                    sd.service_date,
                    COUNT(DISTINCT t.trip_id)
                        AS scheduled_trip_count
                FROM main.int_gtfs__service_dates AS sd
                INNER JOIN main.stg_gtfs__trips AS t
                    ON sd.service_id = t.service_id
                WHERE sd.service_date BETWEEN
                    DATE '2026-10-24' AND DATE '2026-10-29'
                GROUP BY sd.service_date
            )

            SELECT
                d.service_date,
                COALESCE(r.regular_service_count, 0)
                    AS regular_service_count,
                COALESCE(e.added_service_count, 0)
                    AS added_service_count,
                COALESCE(e.removed_service_count, 0)
                    AS removed_service_count,
                COALESCE(f.active_service_count, 0)
                    AS active_service_count,
                COALESCE(t.scheduled_trip_count, 0)
                    AS scheduled_trip_count
            FROM dates AS d
            LEFT JOIN regular_services AS r USING (service_date)
            LEFT JOIN exceptions AS e USING (service_date)
            LEFT JOIN final_services AS f USING (service_date)
            LEFT JOIN trips AS t USING (service_date)
            ORDER BY d.service_date
            """
        ).df().to_string(index=False)
    )

    print("\n=== Calendar records active on 2026-10-24 to 2026-10-27 ===")

    print(
        connection.execute(
            """
            WITH dates AS (
                SELECT unnest(
                    generate_series(
                        DATE '2026-10-24',
                        DATE '2026-10-27',
                        INTERVAL 1 DAY
                    )
                )::DATE AS service_date
            )
            SELECT
                d.service_date,
                c.service_id,
                c.start_date,
                c.end_date,
                c.monday,
                c.tuesday,
                c.wednesday,
                c.thursday,
                c.friday,
                c.saturday,
                c.sunday
            FROM dates AS d
            JOIN main.stg_gtfs__calendar AS c
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
            ORDER BY d.service_date, c.service_id
            """
        ).df().to_string(index=False)
    )

    print("\n=== Calendar validity start-date distribution ===")

    print(
        connection.execute(
            """
            SELECT
                start_date,
                end_date,
                COUNT(*) AS calendar_rows,
                SUM(monday) AS monday_services,
                SUM(tuesday) AS tuesday_services,
                SUM(saturday) AS saturday_services,
                SUM(sunday) AS sunday_services
            FROM main.stg_gtfs__calendar
            GROUP BY start_date, end_date
            ORDER BY start_date, end_date
            """
        ).df().to_string(index=False)
    )

finally:
    connection.close()
