
import json

import pandas as pd

from ingestion import open_meteo


def test_ingest_weather_writes_json_and_parquet(
    tmp_path,
    monkeypatch,
):
    variables = [
        "temperature_2m",
        "precipitation",
        "relative_humidity_2m",
        "wind_speed_10m",
    ]

    config = {
        "base_url": "https://example.test/archive",
        "location": {
            "name": "Paris",
            "latitude": 48.8566,
            "longitude": 2.3522,
        },
        "date_range": {
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
        },
        "request": {
            "timeout_seconds": 10,
            "max_retries": 0,
            "backoff_factor": 0,
        },
        "hourly_variables": variables,
    }

    timestamps = pd.date_range(
        "2025-01-01",
        periods=48,
        freq="h",
        tz="UTC",
    ).strftime("%Y-%m-%dT%H:%M").tolist()

    payload = {
        "hourly": {
            "time": timestamps,
            "temperature_2m": [5.0] * 48,
            "precipitation": [0.0] * 48,
            "relative_humidity_2m": [80] * 48,
            "wind_speed_10m": [10.0] * 48,
        }
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    class FakeSession:
        def get(self, url, params, timeout):
            assert url == config["base_url"]
            assert params["start_date"] == "2025-01-01"
            assert params["end_date"] == "2025-01-02"
            assert timeout == 10
            return FakeResponse()

        def close(self):
            pass

    monkeypatch.setattr(
        open_meteo,
        "load_config",
        lambda: config,
    )
    monkeypatch.setattr(
        open_meteo,
        "create_http_session",
        lambda **kwargs: FakeSession(),
    )
    monkeypatch.setattr(
        open_meteo,
        "RAW_DIR",
        tmp_path / "raw",
    )
    monkeypatch.setattr(
        open_meteo,
        "PROCESSED_DIR",
        tmp_path / "processed",
    )

    output_path = open_meteo.ingest_weather()

    assert output_path.exists()

    df = pd.read_parquet(output_path)
    assert len(df) == 48
    assert df["observation_time"].is_unique
    assert df["source"].eq("open_meteo_archive").all()

    raw_files = list((tmp_path / "raw").glob("*.json"))
    assert len(raw_files) == 1

    saved_payload = json.loads(
        raw_files[0].read_text(encoding="utf-8")
    )
    assert len(saved_payload["hourly"]["time"]) == 48
