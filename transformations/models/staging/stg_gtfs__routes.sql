
{{ config(materialized='view') }}

SELECT
    NULLIF(TRIM(route_id), '') AS route_id,
    NULLIF(TRIM(agency_id), '') AS agency_id,
    NULLIF(TRIM(route_short_name), '') AS route_short_name,
    NULLIF(TRIM(route_long_name), '') AS route_long_name,
    NULLIF(TRIM(route_desc), '') AS route_desc,
    TRY_CAST(route_type AS INTEGER) AS route_type,
    NULLIF(TRIM(route_url), '') AS route_url,
    NULLIF(TRIM(route_color), '') AS route_color,
    NULLIF(TRIM(route_text_color), '') AS route_text_color,
    TRY_CAST(route_sort_order AS INTEGER) AS route_sort_order
FROM read_parquet(
    '{{ env_var("OPENMOBILITY_PROCESSED_DIR", "storage/processed/gtfs/idfm") }}/routes.parquet'
)
