{{ config(materialized='table') }}

SELECT
    operator,
    dsp,
    mode,
    theme,
    indicator,
    year,
    quarter,

    COUNT(*) AS record_count,

    COUNT(result_percentage) AS percentage_record_count,
    AVG(result_percentage) AS avg_reported_percentage,
    MIN(result_percentage) AS min_reported_percentage,
    MAX(result_percentage) AS max_reported_percentage,

    COUNT(result_occurrence) AS occurrence_record_count,
    SUM(result_occurrence) AS total_reported_occurrences,

    COUNT(*) FILTER (
        WHERE result_percentage IS NULL
          AND result_occurrence IS NULL
    ) AS missing_both_measurements,

    COUNT(*) FILTER (
        WHERE result_percentage IS NOT NULL
           OR result_occurrence IS NOT NULL
    ) AS records_with_measurements,

    COUNT(*) FILTER (
        WHERE LOWER(TRIM(penalty)) = 'oui'
    ) AS penalty_yes_count,

    COUNT(*) FILTER (
        WHERE LOWER(TRIM(penalty)) = 'non'
    ) AS penalty_no_count,

    COUNT(*) FILTER (
        WHERE penalty IS NULL
           OR LOWER(TRIM(penalty)) NOT IN ('oui', 'non')
    ) AS penalty_unknown_count

FROM {{ ref('stg_service_quality__indicators') }}

GROUP BY
    operator,
    dsp,
    mode,
    theme,
    indicator,
    year,
    quarter
