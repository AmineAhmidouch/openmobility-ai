
from pathlib import Path

import duckdb
import pandas as pd

from transformations.build_scheduled_stop_events import (
    build_scheduled_stop_events,
)


def write_parquet(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_parquet(path, index=False)


def test_build_scheduled_stop_events(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()

    write_parquet(source / "stop_times.parquet", [
        {
            "trip_id": "T1",
            "stop_id": "S1",
            "stop_sequence": "1",
            "arrival_time": "25:10:00",
            "departure_time": "25:10:00",
            "start_pickup_drop_off_window": "",
            "end_pickup_drop_off_window": "",
            "pickup_type": "0",
            "drop_off_type": "0",
            "timepoint": "1",
        },
        {
            "trip_id": "T1",
            "stop_id": "S2",
            "stop_sequence": "2",
            "arrival_time": "",
            "departure_time": "",
            "start_pickup_drop_off_window": "09:00:00",
            "end_pickup_drop_off_window": "10:00:00",
            "pickup_type": "2",
            "drop_off_type": "2",
            "timepoint": "",
        },
    ])

    write_parquet(source / "trips.parquet", [
        {
            "trip_id": "T1",
            "route_id": "R1",
            "service_id": "SVC1",
            "trip_headsign": "Test destination",
            "direction_id": "0",
            "shape_id": "SH1",
        },
    ])

    write_parquet(source / "routes.parquet", [
        {
            "route_id": "R1",
            "agency_id": "A1",
            "route_short_name": "7",
            "route_long_name": "Test route",
            "route_type": "3",
        },
    ])

    write_parquet(source / "stops.parquet", [
        {
            "stop_id": "S1",
            "stop_name": "First stop",
            "stop_lat": "48.8566",
            "stop_lon": "2.3522",
            "location_type": "0",
            "parent_station": "",
            "wheelchair_boarding": "1",
        },
        {
            "stop_id": "S2",
            "stop_name": "Second stop",
            "stop_lat": "48.8600",
            "stop_lon": "2.3600",
            "location_type": "0",
            "parent_station": "",
            "wheelchair_boarding": "1",
        },
    ])

    output = tmp_path / "scheduled_stop_events.parquet"

    build_scheduled_stop_events(
        data_dir=source,
        output_file=output,
    )

    assert output.is_file()

    con = duckdb.connect()
    try:
        rows = con.execute(
            """
            SELECT
                trip_id,
                stop_id,
                arrival_seconds,
                schedule_time_type,
                stop_latitude
            FROM read_parquet(?)
            ORDER BY stop_sequence
            """,
            [str(output)],
        ).fetchall()
    finally:
        con.close()

    assert len(rows) == 2

    assert rows[0][0] == "T1"
    assert rows[0][1] == "S1"
    assert rows[0][2] == 90600
    assert rows[0][3] == "TIMED"
    assert rows[0][4] == 48.8566

    assert rows[1][1] == "S2"
    assert rows[1][2] is None
    assert rows[1][3] == "WINDOW_BASED"
