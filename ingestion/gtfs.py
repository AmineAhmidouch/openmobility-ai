
from __future__ import annotations

import logging
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]

ZIP_PATH = ROOT / "storage" / "raw" / "gtfs" / "idfm" / "IDFM-gtfs.zip"
OUTPUT_DIR = ROOT / "storage" / "processed" / "gtfs" / "idfm"

CHUNK_SIZE = 250_000

REQUIRED_COLUMNS = {
    "agency.txt": {"agency_name", "agency_url", "agency_timezone"},
    "routes.txt": {"route_id"},
    "stops.txt": {"stop_id"},
    "trips.txt": {"route_id", "service_id", "trip_id"},
    "stop_times.txt": {
        "trip_id",
        "arrival_time",
        "departure_time",
        "stop_id",
        "stop_sequence",
    },
    "calendar.txt": {
        "service_id",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_date",
        "end_date",
    },
    "calendar_dates.txt": {"service_id", "date", "exception_type"},
}

logger = logging.getLogger(__name__)


def get_gtfs_members(archive: zipfile.ZipFile) -> dict[str, str]:
    """Map GTFS filenames to archive member paths."""
    members: dict[str, str] = {}

    for name in archive.namelist():
        if name.endswith("/"):
            continue

        filename = Path(name).name.lower()

        if filename in REQUIRED_COLUMNS:
            if filename in members:
                raise ValueError(
                    f"Duplicate GTFS filename in archive: {filename}"
                )
            members[filename] = name

    missing = {
        "agency.txt",
        "routes.txt",
        "stops.txt",
        "trips.txt",
        "stop_times.txt",
    } - members.keys()

    if missing:
        raise ValueError(
            f"GTFS archive is missing required files: {sorted(missing)}"
        )

    if not {"calendar.txt", "calendar_dates.txt"} & members.keys():
        raise ValueError(
            "GTFS archive must contain calendar.txt "
            "or calendar_dates.txt"
        )

    return members


def process_gtfs_table(
    archive: zipfile.ZipFile,
    member: str,
    filename: str,
    output_path: Path,
) -> int:
    """Convert a CSV inside the ZIP to Parquet using bounded memory."""
    temporary_path = output_path.with_suffix(".parquet.tmp")
    rows_written = 0
    writer: pq.ParquetWriter | None = None

    try:
        with archive.open(member) as binary_stream:
            import io

            text_stream: TextIO = io.TextIOWrapper(
                binary_stream,
                encoding="utf-8-sig",
                newline="",
            )

            chunks = pd.read_csv(
                text_stream,
                dtype="string",
                keep_default_na=False,
                chunksize=CHUNK_SIZE,
            )

            try:
                for chunk in chunks:
                    if writer is None:
                        missing_columns = (
                            REQUIRED_COLUMNS.get(filename, set())
                            - set(chunk.columns)
                        )
                        if missing_columns:
                            raise ValueError(
                                f"{filename} is missing columns: "
                                f"{sorted(missing_columns)}"
                            )

                        if chunk.empty:
                            continue

                        table = pa.Table.from_pandas(
                            chunk,
                            preserve_index=False,
                        )
                        writer = pq.ParquetWriter(
                            temporary_path,
                            table.schema,
                            compression="zstd",
                        )
                    else:
                        table = pa.Table.from_pandas(
                            chunk,
                            schema=writer.schema,
                            preserve_index=False,
                        )

                    writer.write_table(table)
                    rows_written += len(chunk)
            finally:
                if writer is not None:
                    writer.close()

    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"{filename} is empty or has no header") from exc
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    if writer is None:
        temporary_path.unlink(missing_ok=True)
        raise ValueError(f"{filename} contains no data rows")

    temporary_path.replace(output_path)

    logger.info(
        "Processed %s: %s rows -> %s",
        filename,
        rows_written,
        output_path,
    )
    return rows_written


def ingest_gtfs() -> dict[str, int]:
    """Validate the ZIP and create Parquet files for core GTFS tables."""
    if not ZIP_PATH.is_file():
        raise FileNotFoundError(f"GTFS ZIP not found: {ZIP_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            raise ValueError(
                f"Corrupt member in GTFS ZIP: {corrupt_member}"
            )

        members = get_gtfs_members(archive)
        results: dict[str, int] = {}

        for filename, member in sorted(members.items()):
            output_path = OUTPUT_DIR / f"{filename.removesuffix('.txt')}.parquet"

            results[filename] = process_gtfs_table(
                archive=archive,
                member=member,
                filename=filename,
                output_path=output_path,
            )

    logger.info(
        "GTFS ingestion completed at %s UTC",
        datetime.now(UTC).isoformat(),
    )
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    counts = ingest_gtfs()

    print("\nGTFS ingestion completed.")
    for filename, count in sorted(counts.items()):
        print(f"{filename:20} {count:>12,} rows")
