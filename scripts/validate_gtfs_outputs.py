
"""Validate processed GTFS Parquet outputs and track row-count changes."""

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "storage" / "processed" / "gtfs" / "idfm"
BASELINE_PATH = DATA_DIR / "gtfs_validation_baseline.json"

REQUIRED_COLUMNS = {
    "agency": {"agency_name"},
    "calendar": {
        "service_id", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday",
        "start_date", "end_date",
    },
    "calendar_dates": {"service_id", "date", "exception_type"},
    "routes": {"route_id", "route_type"},
    "stops": {"stop_id", "stop_lat", "stop_lon"},
    "trips": {"route_id", "service_id", "trip_id"},
    "stop_times": {
        "trip_id", "stop_id", "stop_sequence",
        "arrival_time", "departure_time",
    },
}

CHANGE_WARNING_THRESHOLD = 0.20

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def inspect_parquet(name: str, path: Path) -> dict:
    """Check readability, required columns, and row count."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing required file: {path}")

    parquet_file = pq.ParquetFile(path)
    row_count = parquet_file.metadata.num_rows
    columns = set(parquet_file.schema_arrow.names)

    missing_columns = REQUIRED_COLUMNS[name] - columns
    if missing_columns:
        raise ValueError(
            f"{name}.parquet is missing columns: "
            f"{sorted(missing_columns)}"
        )

    if row_count == 0:
        raise ValueError(f"{name}.parquet contains no rows")

    logger.info(
        "Validated %s.parquet: %s rows, %s columns",
        name,
        f"{row_count:,}",
        len(columns),
    )

    return {
        "rows": row_count,
        "columns": sorted(columns),
        "size_bytes": path.stat().st_size,
    }


def load_baseline() -> dict | None:
    if not BASELINE_PATH.exists():
        return None

    with BASELINE_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def save_baseline(metrics: dict) -> None:
    baseline = {
        "created_at": datetime.now(UTC).isoformat(),
        "tables": metrics,
    }

    temporary_path = BASELINE_PATH.with_suffix(".tmp")
    try:
        temporary_path.write_text(
            json.dumps(baseline, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(BASELINE_PATH)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate processed GTFS Parquet files."
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Replace the saved row-count baseline after validation.",
    )
    args = parser.parse_args()

    try:
        metrics = {
            name: inspect_parquet(name, DATA_DIR / f"{name}.parquet")
            for name in REQUIRED_COLUMNS
        }

        previous = load_baseline()

        if args.update_baseline or previous is None:
            save_baseline(metrics)
            logger.info(
                "Saved row-count baseline to %s",
                BASELINE_PATH,
            )
            if previous is None:
                logger.info(
                    "This is the initial baseline; no regression "
                    "comparison was possible."
                )
        else:
            old_tables = previous.get("tables", {})

            for name, current in metrics.items():
                if name not in old_tables:
                    logger.warning(
                        "%s has no saved baseline; review the table.",
                        name,
                    )
                    continue

                old_rows = old_tables[name].get("rows")
                new_rows = current["rows"]

                if not isinstance(old_rows, int) or old_rows <= 0:
                    logger.warning(
                        "%s has an invalid baseline row count.",
                        name,
                    )
                    continue

                change = (new_rows - old_rows) / old_rows

                if abs(change) >= CHANGE_WARNING_THRESHOLD:
                    logger.warning(
                        "%s row count changed from %s to %s (%+.1f%%). "
                        "Review before updating the baseline.",
                        name,
                        f"{old_rows:,}",
                        f"{new_rows:,}",
                        change * 100,
                    )
                else:
                    logger.info(
                        "%s row-count change: %+.1f%%",
                        name,
                        change * 100,
                    )

        logger.info("GTFS output validation completed.")
        return 0

    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        logger.error("GTFS output validation failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
