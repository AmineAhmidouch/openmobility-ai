
WITH source_metrics AS (

    SELECT
        COUNT(*) AS source_record_count,
        COUNT(*) FILTER (
            WHERE result_percentage IS NULL
              AND result_occurrence IS NULL
        ) AS missing_both_measurements
    FROM {{ ref('stg_service_quality__indicators') }}

),

completeness_metrics AS (

    SELECT
        SUM(source_record_count) AS source_record_count,
        SUM(missing_both_measurements) AS missing_both_measurements
    FROM {{ ref('mart_service_quality__reporting_completeness') }}

),

alert_metrics AS (

    SELECT
        COALESCE(SUM(missing_both_measurements), 0)
            AS missing_both_measurements
    FROM {{ ref('mart_service_quality__data_quality_alerts') }}

)

SELECT
    'SOURCE_VS_COMPLETENESS' AS failed_check
FROM source_metrics s
CROSS JOIN completeness_metrics c
WHERE s.source_record_count <> c.source_record_count
   OR s.missing_both_measurements <> c.missing_both_measurements

UNION ALL

SELECT
    'COMPLETENESS_VS_ALERTS' AS failed_check
FROM completeness_metrics c
CROSS JOIN alert_metrics a
WHERE c.missing_both_measurements <> a.missing_both_measurements
