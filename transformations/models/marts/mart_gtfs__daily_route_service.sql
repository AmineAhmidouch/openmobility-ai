
{{ config(materialized='table') }}

WITH daily_route_trips AS (
    SELECT
        sd.service_date,
        t.route_id,
        t.service_id,
        t.trip_id
    FROM {{ ref('int_gtfs__service_dates') }} AS sd
    INNER JOIN {{ ref('stg_gtfs__trips') }} AS t
        ON sd.service_id = t.service_id
),

route_summary AS (
    SELECT
        service_date,
        route_id,
        COUNT(DISTINCT trip_id) AS scheduled_trip_count,
        COUNT(DISTINCT service_id) AS active_service_count
    FROM daily_route_trips
    GROUP BY
        service_date,
        route_id
)

SELECT
    rs.service_date,
    rs.route_id,
    r.agency_id,
    r.route_short_name,
    r.route_long_name,
    r.route_type,
    rs.scheduled_trip_count,
    rs.active_service_count
FROM route_summary AS rs
LEFT JOIN {{ ref('stg_gtfs__routes') }} AS r
    ON rs.route_id = r.route_id
