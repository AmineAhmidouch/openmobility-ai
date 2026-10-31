{{ config(materialized='view') }}

SELECT
    NULLIF(TRIM(CAST("Opérateur" AS VARCHAR)), '') AS operator,
    TRY_CAST(NULLIF(TRIM(CAST("DSP" AS VARCHAR)), '') AS INTEGER) AS dsp,
    NULLIF(TRIM(CAST("Thématique" AS VARCHAR)), '') AS theme,
    NULLIF(TRIM(CAST("Indicateur" AS VARCHAR)), '') AS indicator,
    NULLIF(TRIM(CAST("Mode" AS VARCHAR)), '') AS mode,
    NULLIF(TRIM(CAST("Groupe de lignes" AS VARCHAR)), '') AS line_group,
    NULLIF(TRIM(CAST("ID_Line" AS VARCHAR)), '') AS line_id,
    NULLIF(TRIM(CAST("Ligne" AS VARCHAR)), '') AS line,
    NULLIF(TRIM(CAST("Trimestre" AS VARCHAR)), '') AS quarter,
    TRY_CAST(NULLIF(TRIM(CAST("Année" AS VARCHAR)), '') AS INTEGER) AS year,
    TRY_CAST(NULLIF(TRIM(CAST("Résultat indicateurs en %" AS VARCHAR)), '') AS DOUBLE) AS result_percentage,
    TRY_CAST(NULLIF(TRIM(CAST("Résultat indicateurs en occurrence" AS VARCHAR)), '') AS DOUBLE) AS result_occurrence,
    NULLIF(TRIM(CAST("Objectif référence contrat" AS VARCHAR)), '') AS contract_reference_target,
    NULLIF(TRIM(CAST("Pénalité" AS VARCHAR)), '') AS penalty
FROM read_parquet(
    '{{ env_var("OPENMOBILITY_SERVICE_QUALITY_DIR", "storage/processed/service_quality") }}/service_quality.parquet'
)
