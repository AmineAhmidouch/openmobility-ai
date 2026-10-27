
SELECT
    trip_id,
    stop_id,
    stop_latitude,
    stop_longitude
FROM {{ ref('int_gtfs__scheduled_stop_events') }}
WHERE
    stop_latitude IS NULL
    OR stop_longitude IS NULL
    OR stop_latitude NOT BETWEEN -90 AND 90
    OR stop_longitude NOT BETWEEN -180 AND 180
