{{ config(materialized='table') }}

SELECT
    operator,
    dsp,
    mode,
    theme,
    indicator,
    year,
    quarter,

    COUNT(*) AS source_record_count,

    COUNT(result_percentage) AS percentage_record_count,

    COUNT(result_occurrence) AS occurrence_record_count,

    COUNT(*) FILTER (
        WHERE result_percentage IS NULL
          AND result_occurrence IS NULL
    ) AS missing_both_measurements,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE result_percentage IS NULL
              AND result_occurrence IS NULL
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS missing_both_percentage,

    COUNT(*) FILTER (
        WHERE result_percentage IS NULL
    ) AS missing_percentage_count,

    COUNT(*) FILTER (
        WHERE result_occurrence IS NULL
    ) AS missing_occurrence_count,

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
