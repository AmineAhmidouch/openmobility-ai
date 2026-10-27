
SELECT
    trip_id,
    stop_id,
    stop_sequence,
    schedule_time_type,
    arrival_seconds,
    departure_seconds
FROM {{ ref('int_gtfs__scheduled_stop_events') }}
WHERE
    schedule_time_type = 'MISSING_TIME'

    OR (
        schedule_time_type = 'TIMED'
        AND (
            arrival_seconds IS NULL
            OR departure_seconds IS NULL
        )
    )

    OR schedule_time_type NOT IN (
        'TIMED',
        'WINDOW_BASED',
        'MISSING_TIME'
    )
