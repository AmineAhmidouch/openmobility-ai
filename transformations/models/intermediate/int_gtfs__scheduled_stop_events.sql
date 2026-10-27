
{{ config(materialized='view') }}

WITH stop_events AS (
    SELECT
        st.trip_id,
        st.stop_id,
        st.stop_sequence,
        st.arrival_time,
        st.departure_time,
        st.start_pickup_drop_off_window,
        st.end_pickup_drop_off_window,

        CASE
            WHEN st.arrival_time IS NULL
             AND st.departure_time IS NULL
             AND st.start_pickup_drop_off_window IS NOT NULL
             AND st.end_pickup_drop_off_window IS NOT NULL
                THEN 'WINDOW_BASED'

            WHEN st.arrival_time IS NULL
             AND st.departure_time IS NULL
                THEN 'MISSING_TIME'

            ELSE 'TIMED'
        END AS schedule_time_type,

        CASE
            WHEN REGEXP_FULL_MATCH(
                st.arrival_time,
                '[0-9]+:[0-5][0-9]:[0-5][0-9]'
            )
            THEN
                TRY_CAST(SPLIT_PART(st.arrival_time, ':', 1) AS INTEGER) * 3600
                + TRY_CAST(SPLIT_PART(st.arrival_time, ':', 2) AS INTEGER) * 60
                + TRY_CAST(SPLIT_PART(st.arrival_time, ':', 3) AS INTEGER)
            ELSE NULL
        END AS arrival_seconds,

        CASE
            WHEN REGEXP_FULL_MATCH(
                st.departure_time,
                '[0-9]+:[0-5][0-9]:[0-5][0-9]'
            )
            THEN
                TRY_CAST(SPLIT_PART(st.departure_time, ':', 1) AS INTEGER) * 3600
                + TRY_CAST(SPLIT_PART(st.departure_time, ':', 2) AS INTEGER) * 60
                + TRY_CAST(SPLIT_PART(st.departure_time, ':', 3) AS INTEGER)
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
        r.route_type,

        s.stop_name,
        s.stop_latitude,
        s.stop_longitude,
        s.location_type,
        s.parent_station,
        s.wheelchair_boarding

    FROM {{ ref('stg_gtfs__stop_times') }} AS st

    LEFT JOIN {{ ref('stg_gtfs__trips') }} AS t
        ON st.trip_id = t.trip_id

    LEFT JOIN {{ ref('stg_gtfs__routes') }} AS r
        ON t.route_id = r.route_id

    LEFT JOIN {{ ref('stg_gtfs__stops') }} AS s
        ON st.stop_id = s.stop_id
)

SELECT *
FROM stop_events
