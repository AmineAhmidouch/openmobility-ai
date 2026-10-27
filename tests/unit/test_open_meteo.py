
from datetime import UTC, datetime

import pandas as pd
import pytest

from ingestion.open_meteo import (
    HOURLY_VARIABLES,
    parse_weather_payload,
)


@pytest.fixture
def valid_payload():
    return {
        "hourly": {
            "time": [
                "2025-01-01T00:00",
                "2025-01-01T01:00",
            ],
            "temperature_2m": [5.2, 5.8],
            "precipitation": [0.0, 0.2],
            "relative_humidity_2m": [80, 82],
            "wind_speed_10m": [10.1, 11.3],
        }
    }


def test_parse_valid_payload(valid_payload):
    ingested_at = datetime(2025, 1, 8, tzinfo=UTC)

    df = parse_weather_payload(valid_payload, ingested_at)

    assert len(df) == 2
    assert set(HOURLY_VARIABLES).issubset(df.columns)
    assert str(df["observation_time"].dtype) == "datetime64[ns, UTC]"
    assert df["source"].eq("open_meteo_archive").all()
    assert (df["ingested_at"] == pd.Timestamp(ingested_at)).all()


def test_missing_variable_raises_error(valid_payload):
    del valid_payload["hourly"]["temperature_2m"]

    with pytest.raises(ValueError, match="Missing expected variable"):
        parse_weather_payload(valid_payload)


def test_unequal_array_lengths_raise_error(valid_payload):
    valid_payload["hourly"]["precipitation"] = [0.0]

    with pytest.raises(ValueError, match="Unequal array lengths"):
        parse_weather_payload(valid_payload)


def test_duplicate_timestamps_raise_error(valid_payload):
    valid_payload["hourly"]["time"] = [
        "2025-01-01T00:00",
        "2025-01-01T00:00",
    ]

    with pytest.raises(ValueError, match="Duplicate observation timestamps"):
        parse_weather_payload(valid_payload)


def test_all_weather_values_missing_raise_error(valid_payload):
    for variable in HOURLY_VARIABLES:
        valid_payload["hourly"][variable] = [None, None]

    with pytest.raises(ValueError, match="All weather values are missing"):
        parse_weather_payload(valid_payload)


def test_api_error_raises_error():
    with pytest.raises(ValueError, match="Open-Meteo API error"):
        parse_weather_payload({"error": True, "reason": "Example error"})
