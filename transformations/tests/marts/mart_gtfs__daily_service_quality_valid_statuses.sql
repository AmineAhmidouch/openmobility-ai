
SELECT *
FROM {{ ref('mart_gtfs__daily_service_quality') }}
WHERE coverage_status NOT IN (
        'OK',
        'WARNING_LOW_SERVICE_COVERAGE'
    )
   OR same_weekday_status NOT IN (
        'OK',
        'WARNING_LOW_VS_SAME_WEEKDAY',
        'INSUFFICIENT_BASELINE'
    )
   OR post_change_median_status NOT IN (
        'OK',
        'WARNING_LOW_VS_POST_CHANGE_MEDIAN',
        'INSUFFICIENT_BASELINE'
    )
