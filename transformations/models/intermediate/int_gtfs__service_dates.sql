
{{ config(materialized='table') }}

WITH calendar_dates AS (
    SELECT
        service_id,
        start_date,
        end_date,
        monday,
        tuesday,
        wednesday,
        thursday,
        friday,
        saturday,
        sunday
    FROM {{ ref('stg_gtfs__calendar') }}
),

regular_service_dates AS (
    SELECT
        c.service_id,
        d.service_date
    FROM calendar_dates AS c
    CROSS JOIN LATERAL (
        SELECT unnest(
            generate_series(c.start_date, c.end_date, INTERVAL 1 DAY)
        )::DATE AS service_date
    ) AS d
    WHERE
        CASE EXTRACT(DOW FROM d.service_date)
            WHEN 0 THEN c.sunday
            WHEN 1 THEN c.monday
            WHEN 2 THEN c.tuesday
            WHEN 3 THEN c.wednesday
            WHEN 4 THEN c.thursday
            WHEN 5 THEN c.friday
            WHEN 6 THEN c.saturday
        END = 1
),

exceptions AS (
    SELECT
        service_id,
        service_date,
        exception_type
    FROM {{ ref('stg_gtfs__calendar_dates') }}
),

service_dates_after_removals AS (
    SELECT r.service_id, r.service_date
    FROM regular_service_dates AS r
    WHERE NOT EXISTS (
        SELECT 1
        FROM exceptions AS e
        WHERE e.service_id = r.service_id
          AND e.service_date = r.service_date
          AND e.exception_type = 2
    )
),

final_service_dates AS (
    SELECT service_id, service_date
    FROM service_dates_after_removals

    UNION

    SELECT service_id, service_date
    FROM exceptions
    WHERE exception_type = 1
)

SELECT
    service_id,
    service_date
FROM final_service_dates
