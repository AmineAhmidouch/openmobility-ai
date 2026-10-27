
{{ config(materialized='view') }}

SELECT
    NULLIF(TRIM(service_id), '') AS service_id,
    TRY_CAST(monday AS INTEGER) AS monday,
    TRY_CAST(tuesday AS INTEGER) AS tuesday,
    TRY_CAST(wednesday AS INTEGER) AS wednesday,
    TRY_CAST(thursday AS INTEGER) AS thursday,
    TRY_CAST(friday AS INTEGER) AS friday,
    TRY_CAST(saturday AS INTEGER) AS saturday,
    TRY_CAST(sunday AS INTEGER) AS sunday,
    TRY_STRPTIME(start_date, '%Y%m%d')::DATE AS start_date,
    TRY_STRPTIME(end_date, '%Y%m%d')::DATE AS end_date
FROM read_parquet(
    '{{ env_var("OPENMOBILITY_PROCESSED_DIR", "storage/processed/gtfs/idfm") }}/calendar.parquet'
)
