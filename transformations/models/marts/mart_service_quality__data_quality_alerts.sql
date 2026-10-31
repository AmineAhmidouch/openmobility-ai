
{{ config(materialized='table') }}

WITH reporting AS (

    SELECT
        operator,
        dsp,
        mode,
        theme,
        indicator,
        year,
        quarter,
        source_record_count,
        missing_both_measurements,
        missing_both_percentage,
        missing_percentage_count,
        missing_occurrence_count,
        penalty_yes_count,
        penalty_no_count,
        penalty_unknown_count

    FROM {{ ref('mart_service_quality__reporting_completeness') }}

),

classified AS (

    SELECT
        *,

        ROUND(
            100.0 - missing_both_percentage,
            2
        ) AS measurement_completeness_percentage,

        CASE
            WHEN missing_both_percentage > 60 THEN 'CRITICAL'
            WHEN missing_both_percentage > 30 THEN 'HIGH'
            WHEN missing_both_percentage > 10 THEN 'MODERATE'
            WHEN missing_both_percentage > 0 THEN 'LOW'
            ELSE 'COMPLETE'
        END AS severity,

        CASE
            WHEN source_record_count < 8 THEN TRUE
            ELSE FALSE
        END AS small_sample_flag

    FROM reporting

)

SELECT
    operator,
    dsp,
    mode,
    theme,
    indicator,
    year,
    quarter,

    source_record_count,
    missing_both_measurements,
    missing_both_percentage,
    measurement_completeness_percentage,

    missing_percentage_count,
    missing_occurrence_count,

    penalty_yes_count,
    penalty_no_count,
    penalty_unknown_count,

    severity,
    small_sample_flag,

    CASE
        WHEN small_sample_flag
            THEN 'LOW_SAMPLE_SIZE'
        WHEN severity = 'CRITICAL'
            THEN 'INVESTIGATE_URGENTLY'
        WHEN severity = 'HIGH'
            THEN 'INVESTIGATE'
        WHEN severity = 'MODERATE'
            THEN 'MONITOR'
        WHEN severity = 'LOW'
            THEN 'WATCH'
        ELSE 'NO_ACTION'
    END AS recommended_action

FROM classified
WHERE missing_both_measurements > 0
