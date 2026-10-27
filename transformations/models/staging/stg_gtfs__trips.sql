
{{ config(materialized='view') }}

SELECT
    NULLIF(TRIM(trip_id), '') AS trip_id,
    NULLIF(TRIM(route_id), '') AS route_id,
    NULLIF(TRIM(service_id), '') AS service_id,
    NULLIF(TRIM(trip_headsign), '') AS trip_headsign,
    NULLIF(TRIM(trip_short_name), '') AS trip_short_name,
    TRY_CAST(direction_id AS INTEGER) AS direction_id,
    NULLIF(TRIM(block_id), '') AS block_id,
    NULLIF(TRIM(shape_id), '') AS shape_id,
    TRY_CAST(wheelchair_accessible AS INTEGER) AS wheelchair_accessible,
    TRY_CAST(bikes_allowed AS INTEGER) AS bikes_allowed
FROM read_parquet(
    '{{ env_var("OPENMOBILITY_PROCESSED_DIR", "storage/processed/gtfs/idfm") }}/trips.parquet'
)
