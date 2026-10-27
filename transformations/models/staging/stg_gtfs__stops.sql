
{{ config(materialized='view') }}

SELECT
    NULLIF(TRIM(stop_id), '') AS stop_id,
    NULLIF(TRIM(stop_code), '') AS stop_code,
    NULLIF(TRIM(stop_name), '') AS stop_name,
    NULLIF(TRIM(stop_desc), '') AS stop_desc,
    TRY_CAST(stop_lon AS DOUBLE) AS stop_longitude,
    TRY_CAST(stop_lat AS DOUBLE) AS stop_latitude,
    NULLIF(TRIM(zone_id), '') AS zone_id,
    NULLIF(TRIM(stop_url), '') AS stop_url,
    TRY_CAST(location_type AS INTEGER) AS location_type,
    NULLIF(TRIM(parent_station), '') AS parent_station,
    NULLIF(TRIM(stop_timezone), '') AS stop_timezone,
    NULLIF(TRIM(level_id), '') AS level_id,
    TRY_CAST(wheelchair_boarding AS INTEGER) AS wheelchair_boarding,
    NULLIF(TRIM(platform_code), '') AS platform_code,
    NULLIF(TRIM(stop_access), '') AS stop_access
FROM read_parquet(
    '{{ env_var("OPENMOBILITY_PROCESSED_DIR", "storage/processed/gtfs/idfm") }}/stops.parquet'
)
