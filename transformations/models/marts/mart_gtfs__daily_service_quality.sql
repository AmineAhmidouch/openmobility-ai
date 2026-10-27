
{{ config(materialized='table') }}

WITH daily_metrics AS (
    SELECT
        service_date,
        COUNT(DISTINCT route_id) AS active_route_count,
        SUM(scheduled_trip_count) AS total_scheduled_trips
    FROM {{ ref('mart_gtfs__daily_route_service') }}
    GROUP BY service_date
),

weekday_baseline AS (
    SELECT
        EXTRACT(DOW FROM service_date)::INTEGER AS day_of_week,
        COUNT(*) AS weekday_observation_count,
        SUM(total_scheduled_trips) AS weekday_total_trips,
        AVG(total_scheduled_trips) AS weekday_average_trips
    FROM daily_metrics
    GROUP BY EXTRACT(DOW FROM service_date)
),

post_change_weekday_baseline AS (
    SELECT
        EXTRACT(DOW FROM service_date)::INTEGER AS day_of_week,
        MEDIAN(total_scheduled_trips) AS median_weekday_trips,
        COUNT(*) AS baseline_observation_count
    FROM daily_metrics
    WHERE service_date >= DATE '2026-10-27'
    GROUP BY EXTRACT(DOW FROM service_date)
),

metrics_with_baseline AS (
    SELECT
        d.*,
        EXTRACT(DOW FROM d.service_date)::INTEGER AS day_of_week,

        b.weekday_observation_count,

        (
            b.weekday_total_trips - d.total_scheduled_trips
        ) / NULLIF(b.weekday_observation_count - 1, 0)
            AS same_weekday_average_trips,

        p.median_weekday_trips,
        p.baseline_observation_count,

        MAX(d.active_route_count) OVER ()
            AS max_active_route_count,

        MAX(d.total_scheduled_trips) OVER ()
            AS max_scheduled_trip_count,

        LAG(d.total_scheduled_trips) OVER (
            ORDER BY d.service_date
        ) AS previous_day_trip_count

    FROM daily_metrics d

    LEFT JOIN weekday_baseline b
        ON EXTRACT(DOW FROM d.service_date) = b.day_of_week

    LEFT JOIN post_change_weekday_baseline p
        ON EXTRACT(DOW FROM d.service_date) = p.day_of_week
)

SELECT
    service_date,
    day_of_week,
    active_route_count,
    total_scheduled_trips,
    previous_day_trip_count,

    same_weekday_average_trips,

    ROUND(
        100.0 * total_scheduled_trips
        / NULLIF(same_weekday_average_trips, 0),
        2
    ) AS pct_of_same_weekday_average,

    median_weekday_trips,
    baseline_observation_count,

    ROUND(
        100.0 * total_scheduled_trips
        / NULLIF(median_weekday_trips, 0),
        2
    ) AS pct_of_post_change_weekday_median,

    CASE
        WHEN active_route_count < max_active_route_count * 0.10
          OR total_scheduled_trips < max_scheduled_trip_count * 0.10
            THEN 'WARNING_LOW_SERVICE_COVERAGE'
        ELSE 'OK'
    END AS coverage_status,

    CASE
        WHEN weekday_observation_count < 3
            THEN 'INSUFFICIENT_BASELINE'
        WHEN total_scheduled_trips
             < same_weekday_average_trips * 0.50
            THEN 'WARNING_LOW_VS_SAME_WEEKDAY'
        ELSE 'OK'
    END AS same_weekday_status,

    CASE
        WHEN baseline_observation_count < 3
            THEN 'INSUFFICIENT_BASELINE'
        WHEN total_scheduled_trips < median_weekday_trips * 0.50
            THEN 'WARNING_LOW_VS_POST_CHANGE_MEDIAN'
        ELSE 'OK'
    END AS post_change_median_status

FROM metrics_with_baseline
