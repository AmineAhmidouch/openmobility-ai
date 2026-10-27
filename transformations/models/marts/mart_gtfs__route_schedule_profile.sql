
{{ config(materialized='table') }}

SELECT
    route_id,
    agency_id,
    route_short_name,
    route_long_name,
    route_type,

    COUNT(DISTINCT trip_id) AS scheduled_trip_count,
    COUNT(*) AS scheduled_stop_event_count,
    COUNT(DISTINCT stop_id) AS distinct_stop_count,
    COUNT(DISTINCT service_id) AS distinct_service_count,

    SUM(
        CASE
            WHEN schedule_time_type = 'TIMED' THEN 1
            ELSE 0
        END
    ) AS timed_stop_event_count,

    SUM(
        CASE
            WHEN schedule_time_type = 'WINDOW_BASED' THEN 1
            ELSE 0
        END
    ) AS window_based_stop_event_count,

    MIN(arrival_seconds) AS earliest_arrival_seconds,
    MAX(departure_seconds) AS latest_departure_seconds

FROM {{ ref('int_gtfs__scheduled_stop_events') }}

WHERE route_id IS NOT NULL

GROUP BY
    route_id,
    agency_id,
    route_short_name,
    route_long_name,
    route_type
