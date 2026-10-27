
{{ config(materialized='view') }}

SELECT
    NULLIF(TRIM(trip_id), '') AS trip_id,
    NULLIF(TRIM(stop_id), '') AS stop_id,
    TRY_CAST(stop_sequence AS INTEGER) AS stop_sequence,
    NULLIF(TRIM(arrival_time), '') AS arrival_time,
    NULLIF(TRIM(departure_time), '') AS departure_time,
    NULLIF(TRIM(start_pickup_drop_off_window), '') AS start_pickup_drop_off_window,
    NULLIF(TRIM(end_pickup_drop_off_window), '') AS end_pickup_drop_off_window,
    TRY_CAST(pickup_type AS INTEGER) AS pickup_type,
    TRY_CAST(drop_off_type AS INTEGER) AS drop_off_type,
    NULLIF(TRIM(local_zone_id), '') AS local_zone_id,
    NULLIF(TRIM(stop_headsign), '') AS stop_headsign,
    TRY_CAST(timepoint AS INTEGER) AS timepoint,
    NULLIF(TRIM(pickup_booking_rule_id), '') AS pickup_booking_rule_id,
    NULLIF(TRIM(drop_off_booking_rule_id), '') AS drop_off_booking_rule_id
FROM read_parquet(
    '{{ env_var("OPENMOBILITY_PROCESSED_DIR", "storage/processed/gtfs/idfm") }}/stop_times.parquet'
)
