
SELECT
    service_date,
    route_id
FROM {{ ref('mart_gtfs__daily_route_service') }}
GROUP BY
    service_date,
    route_id
HAVING COUNT(*) > 1
