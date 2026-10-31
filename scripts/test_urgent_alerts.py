import duckdb

DB_PATH = "storage/processed/openmobility.duckdb"

con = duckdb.connect(DB_PATH, read_only=True)

query = """
SELECT
    mode AS transport_mode,
    COUNT(*) AS urgent_alert_count,
    SUM(missing_both_measurements) AS total_missing_records,
    SUM(source_record_count) AS total_records,
    ROUND(AVG(missing_both_percentage), 2) AS avg_missing_percentage
FROM mart_service_quality__data_quality_alerts
WHERE UPPER(TRIM(operator)) = 'RATP'
  AND UPPER(recommended_action) = 'INVESTIGATE_URGENTLY'
GROUP BY mode
ORDER BY urgent_alert_count DESC, total_missing_records DESC;
"""

result = con.execute(query).fetchdf()

print("\n=== URGENT RATP ALERTS BY TRANSPORT MODE ===")

if result.empty:
    print("No urgent alerts found.")
else:
    print(result.to_string(index=False))

con.close()