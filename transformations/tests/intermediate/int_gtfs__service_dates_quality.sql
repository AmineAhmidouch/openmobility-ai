
SELECT
    service_id,
    service_date
FROM {{ ref('int_gtfs__service_dates') }}
WHERE service_id IS NULL
   OR service_date IS NULL
