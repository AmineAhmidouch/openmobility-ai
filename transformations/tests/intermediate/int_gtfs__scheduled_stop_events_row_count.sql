
WITH counts AS (
    SELECT
        (SELECT COUNT(*)
         FROM {{ ref('stg_gtfs__stop_times') }}) AS source_count,

        (SELECT COUNT(*)
         FROM {{ ref('int_gtfs__scheduled_stop_events') }}) AS model_count
)

SELECT *
FROM counts
WHERE source_count <> model_count
