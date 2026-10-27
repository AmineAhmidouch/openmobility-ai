
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from ingestion import gtfs


def create_test_feed(
    zip_path: Path,
    *,
    omit_file: str | None = None,
    invalid_routes_header: bool = False,
) -> None:
    """Create a small synthetic GTFS ZIP for testing."""
    routes_header = (
        "wrong_route_id"
        if invalid_routes_header
        else "route_id"
    )

    files = {
        "agency.txt": (
            "agency_name,agency_url,agency_timezone\n"
            "Test Transit,https://example.com,Europe/Paris\n"
        ),
        "routes.txt": (
            f"{routes_header}\n"
            "0007\n"
        ),
        "stops.txt": (
            "stop_id\n"
            "001\n"
            "002\n"
        ),
        "trips.txt": (
            "route_id,service_id,trip_id\n"
            "0007,SVC1,0001\n"
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "0001,25:10:00,25:10:00,001,1\n"
            "0001,25:15:00,25:15:00,002,2\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,"
            "friday,saturday,sunday,start_date,end_date\n"
            "SVC1,1,1,1,1,1,0,0,20261001,20261031\n"
        ),
        "calendar_dates.txt": (
            "service_id,date,exception_type\n"
            "SVC1,20261031,2\n"
        ),
    }

    if omit_file is not None:
        files.pop(omit_file)

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)


def configure_test_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    zip_path: Path,
) -> None:
    """Redirect ingestion outputs to temporary test directories."""
    monkeypatch.setattr(gtfs, "ZIP_PATH", zip_path)
    monkeypatch.setattr(
        gtfs,
        "OUTPUT_DIR",
        tmp_path / "processed" / "gtfs",
    )
    # Force multiple chunks even for this tiny dataset.
    monkeypatch.setattr(gtfs, "CHUNK_SIZE", 1)


def test_ingest_gtfs_creates_parquet_and_preserves_strings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zip_path = tmp_path / "test_gtfs.zip"
    create_test_feed(zip_path)
    configure_test_paths(monkeypatch, tmp_path, zip_path)

    counts = gtfs.ingest_gtfs()

    assert counts["agency.txt"] == 1
    assert counts["routes.txt"] == 1
    assert counts["stops.txt"] == 2
    assert counts["trips.txt"] == 1
    assert counts["stop_times.txt"] == 2
    assert counts["calendar.txt"] == 1
    assert counts["calendar_dates.txt"] == 1

    output_dir = tmp_path / "processed" / "gtfs"

    for table in (
        "agency",
        "routes",
        "stops",
        "trips",
        "stop_times",
        "calendar",
        "calendar_dates",
    ):
        assert (output_dir / f"{table}.parquet").is_file()

    routes = pd.read_parquet(output_dir / "routes.parquet")
    stop_times = pd.read_parquet(output_dir / "stop_times.parquet")

    assert routes.loc[0, "route_id"] == "0007"
    assert stop_times.loc[0, "trip_id"] == "0001"
    assert stop_times.loc[0, "stop_id"] == "001"
    assert stop_times.loc[0, "arrival_time"] == "25:10:00"


def test_ingest_gtfs_rejects_missing_required_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zip_path = tmp_path / "incomplete_gtfs.zip"
    create_test_feed(zip_path, omit_file="stops.txt")
    configure_test_paths(monkeypatch, tmp_path, zip_path)

    with pytest.raises(ValueError, match="missing required files"):
        gtfs.ingest_gtfs()


def test_ingest_gtfs_rejects_missing_required_column(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zip_path = tmp_path / "invalid_gtfs.zip"
    create_test_feed(zip_path, invalid_routes_header=True)
    configure_test_paths(monkeypatch, tmp_path, zip_path)

    with pytest.raises(ValueError, match="routes.txt is missing columns"):
        gtfs.ingest_gtfs()
