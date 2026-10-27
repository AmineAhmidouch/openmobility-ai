
{{ config(materialized='view') }}

SELECT
    NULLIF(TRIM(service_id), '') AS service_id,
    TRY_STRPTIME(date, '%Y%m%d')::DATE AS service_date,
    TRY_CAST(exception_type AS INTEGER) AS exception_type
FROM read_parquet(
    '{{ env_var("OPENMOBILITY_PROCESSED_DIR", "storage/processed/gtfs/idfm") }}/calendar_dates.parquet'
)