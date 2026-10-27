
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "storage" / "processed" / "gtfs" / "idfm"

TABLES = ["routes", "stops", "trips", "stop_times"]

con = duckdb.connect()

try:
    for table in TABLES:
        path = (DATA_DIR / f"{table}.parquet").as_posix()

        print(f"\n=== {table.upper()} ===")

        schema = con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{path}')"
        ).fetchdf()

        print(schema[["column_name", "column_type"]].to_string(index=False))
finally:
    con.close()
