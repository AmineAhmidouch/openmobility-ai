
{{ config(materialized='table') }}

WITH completeness_summary AS (

    SELECT
        operator,
        mode,
        theme,
        year,

        COUNT(*) AS reporting_group_count,
        SUM(source_record_count) AS source_record_count,
        SUM(missing_both_measurements) AS missing_both_measurements,
        SUM(missing_percentage_count) AS missing_percentage_count,
        SUM(missing_occurrence_count) AS missing_occurrence_count,

        ROUND(
            100.0 * SUM(missing_both_measurements)
            / NULLIF(SUM(source_record_count), 0),
            2
        ) AS missing_both_percentage,

        ROUND(
            100.0 * (
                SUM(source_record_count)
                - SUM(missing_both_measurements)
            ) / NULLIF(SUM(source_record_count), 0),
            2
        ) AS measurement_completeness_percentage

    FROM {{ ref('mart_service_quality__reporting_completeness') }}

    GROUP BY
        operator,
        mode,
        theme,
        year

),

alert_summary AS (

    SELECT
        operator,
        mode,
        theme,
        year,

        COUNT(*) AS alert_group_count,

        COUNT(*) FILTER (
            WHERE severity = 'CRITICAL'
        ) AS critical_alert_group_count,

        COUNT(*) FILTER (
            WHERE severity = 'HIGH'
        ) AS high_alert_group_count,

        COUNT(*) FILTER (
            WHERE small_sample_flag = TRUE
        ) AS small_sample_group_count

    FROM {{ ref('mart_service_quality__data_quality_alerts') }}

    GROUP BY
        operator,
        mode,
        theme,
        year

)

SELECT
    c.operator,
    c.mode,
    c.theme,
    c.year,

    c.reporting_group_count,
    c.source_record_count,
    c.missing_both_measurements,
    c.missing_percentage_count,
    c.missing_occurrence_count,

    c.missing_both_percentage,
    c.measurement_completeness_percentage,

    COALESCE(a.alert_group_count, 0) AS alert_group_count,
    COALESCE(a.critical_alert_group_count, 0)
        AS critical_alert_group_count,
    COALESCE(a.high_alert_group_count, 0)
        AS high_alert_group_count,
    COALESCE(a.small_sample_group_count, 0)
        AS small_sample_group_count

FROM completeness_summary c

LEFT JOIN alert_summary a
    ON c.operator = a.operator
   AND c.mode = a.mode
   AND c.theme = a.theme
   AND c.year = a.year
