
import duckdb

db_path = "storage/processed/openmobility.duckdb"

query = """

SELECT
    operator,
    mode,
    theme,
    indicator,
    year,
    SUM(source_record_count) AS source_records,
    SUM(missing_both_measurements) AS missing_records,
    ROUND(
        100.0 * SUM(missing_both_measurements)
        / NULLIF(SUM(source_record_count), 0),
        2
    ) AS missing_percentage
FROM mart_service_quality__reporting_completeness
WHERE
    LOWER(indicator) LIKE '%grève%'
    OR LOWER(indicator) LIKE '%grèves%'
    OR LOWER(indicator) LIKE '%travaux%'
    OR LOWER(indicator) LIKE '%ascenseurs%'
    OR LOWER(indicator) LIKE '%escaliers mécaniques%'
GROUP BY
    operator, mode, theme, indicator, year
HAVING
    SUM(source_record_count) >= 8
    AND SUM(missing_both_measurements) > 0
ORDER BY
    missing_percentage DESC,
    missing_records DESC
"""

with duckdb.connect(db_path, read_only=True) as conn:
    results = conn.execute(query).fetchdf()
    print(results.to_string(index=False))
