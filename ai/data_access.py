from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "storage" / "processed" / "openmobility.duckdb"

MAX_ROWS = 100
ALLOWED_SEVERITIES = {"CRITICAL", "HIGH", "MODERATE", "LOW"}
ALLOWED_RECOMMENDED_ACTIONS = {
    "INVESTIGATE_URGENTLY",
    "LOW_SAMPLE_SIZE",
}


def _query(sql: str, params: list | None = None) -> list[dict]:
    """Execute an approved read-only query against the project DuckDB database."""
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        cursor = con.execute(sql, params or [])
        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchmany(MAX_ROWS)
        return [dict(zip(columns, row)) for row in rows]


def get_service_quality_summary(
    operator: str | None = None,
    year: int | None = None,
) -> list[dict]:
    """Retrieve aggregated service-quality and reporting-completeness metrics."""
    conditions = []
    params = []

    if operator:
        conditions.append("LOWER(TRIM(operator)) = LOWER(?)")
        params.append(operator.strip())

    if year is not None:
        if isinstance(year, bool) or not isinstance(year, int):
            raise ValueError("year must be an integer.")
        if not 2000 <= year <= 2100:
            raise ValueError("year must be between 2000 and 2100.")
        conditions.append('"year" = ?')
        params.append(year)

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    sql = f"""
        SELECT
            operator,
            mode,
            theme,
            "year" AS year,
            SUM(source_record_count) AS source_record_count,
            SUM(missing_both_measurements)
                AS missing_both_measurements,
            ROUND(
                100.0 * SUM(missing_both_measurements)
                / NULLIF(SUM(source_record_count), 0),
                2
            ) AS missing_both_percentage,
            ROUND(
                100.0 * (
                    SUM(source_record_count)
                    - SUM(missing_both_measurements)
                ) / NULLIF(SUM(source_record_count), 0),
                2
            ) AS measurement_completeness_percentage
        FROM mart_service_quality__summary
        {where_clause}
        GROUP BY operator, mode, theme, "year"
        ORDER BY missing_both_percentage DESC NULLS LAST
        LIMIT {MAX_ROWS}
    """

    return _query(sql, params)


def get_data_quality_alerts(
    severity: str | None = None,
    operator: str | None = None,
    recommended_action: str | None = None,
) -> list[dict]:
    """Retrieve reporting-completeness alerts with optional exact filters."""
    conditions = []
    params = []

    if severity:
        normalized_severity = severity.strip().upper()
        if normalized_severity not in ALLOWED_SEVERITIES:
            raise ValueError(
                "Unsupported severity. Choose from "
                f"{sorted(ALLOWED_SEVERITIES)}."
            )
        conditions.append("UPPER(TRIM(severity)) = ?")
        params.append(normalized_severity)

    if operator:
        conditions.append("LOWER(TRIM(operator)) = LOWER(?)")
        params.append(operator.strip())

    if recommended_action:
        normalized_action = recommended_action.strip().upper()
        if normalized_action not in ALLOWED_RECOMMENDED_ACTIONS:
            raise ValueError(
                "Unsupported recommended_action. Choose from "
                f"{sorted(ALLOWED_RECOMMENDED_ACTIONS)}."
            )
        conditions.append("UPPER(TRIM(recommended_action)) = ?")
        params.append(normalized_action)

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    sql = f"""
        SELECT
            operator,
            mode,
            theme,
            indicator,
            year,
            quarter,
            source_record_count,
            missing_both_measurements,
            missing_both_percentage,
            measurement_completeness_percentage,
            severity,
            small_sample_flag,
            recommended_action
        FROM mart_service_quality__data_quality_alerts
        {where_clause}
        ORDER BY
            CASE severity
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'MODERATE' THEN 3
                WHEN 'LOW' THEN 4
                ELSE 5
            END,
            missing_both_percentage DESC NULLS LAST,
            source_record_count DESC
        LIMIT {MAX_ROWS}
    """

    return _query(sql, params)



def get_alerts_by_transport_mode(
    operator: str | None = None,
) -> list[dict]:
    """
    Aggregate urgent reporting-completeness alerts by operator and mode.

    If an operator is provided, only that operator is returned.
    Otherwise, all operators and their transport modes are included.

    Modes without urgent alerts are retained with a count of 0.
    The missing percentage is weighted by total source records.
    """
    if operator is not None and (
        not isinstance(operator, str) or not operator.strip()
    ):
        raise ValueError("operator must be a non-empty string.")

    operator_filter = ""
    params: list = []

    if operator is not None:
        operator_filter = "WHERE LOWER(TRIM(operator)) = LOWER(?)"
        params.append(operator.strip())

    urgent_filter = ""
    if operator is not None:
        urgent_filter = "WHERE LOWER(TRIM(operator)) = LOWER(?)"
        params.append(operator.strip())

    sql = f"""
        WITH transport_modes AS (
            SELECT DISTINCT
                operator,
                mode
            FROM mart_service_quality__data_quality_alerts
            {operator_filter}
              {"AND" if operator is not None else "WHERE"}
              operator IS NOT NULL
              AND mode IS NOT NULL
        ),

        urgent_alerts AS (
            SELECT
                operator,
                mode,
                COUNT(*) AS urgent_alert_count,
                SUM(missing_both_measurements)
                    AS total_missing_records,
                SUM(source_record_count) AS total_records
            FROM mart_service_quality__data_quality_alerts
            {urgent_filter}
              {"AND" if operator is not None else "WHERE"}
              UPPER(TRIM(recommended_action)) = 'INVESTIGATE_URGENTLY'
            GROUP BY operator, mode
        )

        SELECT
            tm.operator,
            tm.mode AS transport_mode,

            COALESCE(ua.urgent_alert_count, 0)
                AS urgent_alert_count,

            COALESCE(ua.total_missing_records, 0)
                AS total_missing_records,

            COALESCE(ua.total_records, 0)
                AS total_records,

            CASE
                WHEN COALESCE(ua.total_records, 0) = 0 THEN NULL
                ELSE ROUND(
                    100.0 * ua.total_missing_records / ua.total_records,
                    2
                )
            END AS weighted_missing_percentage

        FROM transport_modes tm

        LEFT JOIN urgent_alerts ua
            ON LOWER(TRIM(tm.operator)) = LOWER(TRIM(ua.operator))
            AND tm.mode = ua.mode

        ORDER BY
            tm.operator,
            urgent_alert_count DESC,
            total_missing_records DESC,
            tm.mode

        LIMIT {MAX_ROWS}
    """

    return _query(sql, params)



def get_reporting_completeness_by_transport_mode(
    operator: str | None = None,
) -> list[dict]:
    """
    Compare overall reporting completeness by operator and transport mode.

    Overall metrics include all reporting records.
    Urgent-alert metrics are calculated separately from the alert mart.
    An optional operator filter limits the comparison to one operator.
    """
    if operator is not None and (
        not isinstance(operator, str) or not operator.strip()
        ):
            raise ValueError("operator must be a non-empty string.")

    operator_filter = ""
    params: list = []

    if operator:
        operator_filter = "WHERE LOWER(TRIM(operator)) = LOWER(?)"
        params.append(operator.strip())

    urgent_filter = ""
    if operator:
        urgent_filter = "WHERE LOWER(TRIM(operator)) = LOWER(?)"
        params.append(operator.strip())

    sql = f"""
        WITH overall_metrics AS (
            SELECT
                operator,
                mode,
                SUM(source_record_count) AS total_records,
                SUM(missing_both_measurements)
                    AS total_missing_records
            FROM mart_service_quality__summary
            {operator_filter}
            GROUP BY operator, mode
        ),

        urgent_metrics AS (
            SELECT
                operator,
                mode,
                COUNT(*) AS urgent_alert_count,
                SUM(source_record_count) AS urgent_total_records,
                SUM(missing_both_measurements)
                    AS urgent_missing_records
            FROM mart_service_quality__data_quality_alerts
            {urgent_filter}
              {"AND" if operator else "WHERE"}
              UPPER(TRIM(recommended_action)) = 'INVESTIGATE_URGENTLY'
            GROUP BY operator, mode
        )

        SELECT
            o.operator,
            o.mode AS transport_mode,
            o.total_records,
            o.total_missing_records,

            ROUND(
                100.0 * o.total_missing_records
                / NULLIF(o.total_records, 0),
                2
            ) AS overall_missing_percentage,

            ROUND(
                100.0 * (
                    o.total_records - o.total_missing_records
                ) / NULLIF(o.total_records, 0),
                2
            ) AS overall_completeness_percentage,

            COALESCE(u.urgent_alert_count, 0)
                AS urgent_alert_count,

            COALESCE(u.urgent_total_records, 0)
                AS urgent_total_records,

            COALESCE(u.urgent_missing_records, 0)
                AS urgent_missing_records,

            ROUND(
                100.0 * u.urgent_missing_records
                / NULLIF(u.urgent_total_records, 0),
                2
            ) AS urgent_missing_percentage

        FROM overall_metrics o
        LEFT JOIN urgent_metrics u
            ON LOWER(TRIM(o.operator)) = LOWER(TRIM(u.operator))
            AND o.mode = u.mode

        ORDER BY
            overall_missing_percentage DESC NULLS LAST,
            o.operator,
            o.mode

        LIMIT {MAX_ROWS}
    """

    return _query(sql, params)



def search_stops(search_term: str) -> list[dict]:
    """Search stops, prioritizing exact names and word-start matches."""
    term = search_term.strip()
    if not term:
        return []

    sql = """
        SELECT
            stop_id,
            stop_name,
            stop_latitude,
            stop_longitude,
            parent_station,
            location_type
        FROM stg_gtfs__stops
        WHERE
            LOWER(TRIM(stop_name)) = LOWER(?)
            OR LOWER(stop_name) LIKE LOWER(?)
        ORDER BY
            CASE
                WHEN LOWER(TRIM(stop_name)) = LOWER(?) THEN 0
                WHEN LOWER(stop_name) LIKE LOWER(?) THEN 1
                ELSE 2
            END,
            stop_name
        LIMIT 50
    """

    return _query(
        sql,
        [
            term,
            f"% {term}%",
            term,
            f"% {term}%",
        ],
    )


def search_routes(search_term: str) -> list[dict]:
    """Search GTFS route names and short names."""
    term = search_term.strip()
    if not term:
        return []

    return _query(
        """
        SELECT
            route_id,
            route_short_name,
            route_long_name,
            route_type,
            route_color
        FROM stg_gtfs__routes
        WHERE route_short_name ILIKE ?
           OR route_long_name ILIKE ?
        ORDER BY route_short_name, route_long_name
        LIMIT 50
        """,
        [f"%{term}%", f"%{term}%"],
    )
