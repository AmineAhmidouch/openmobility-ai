
import pandas as pd
import pytest

from ingestion.open_meteo import validate_hourly_coverage


def test_valid_hourly_coverage():
    df = pd.DataFrame({
        "observation_time": pd.date_range(
            "2025-01-01",
            periods=48,
            freq="h",
            tz="UTC",
        )
    })

    validate_hourly_coverage(df, "2025-01-01", "2025-01-02")


def test_missing_hour_fails_validation():
    timestamps = pd.date_range(
        "2025-01-01",
        periods=48,
        freq="h",
        tz="UTC",
    ).delete(12)

    df = pd.DataFrame({"observation_time": timestamps})

    with pytest.raises(ValueError, match="Hourly coverage validation failed"):
        validate_hourly_coverage(
            df,
            "2025-01-01",
            "2025-01-02",
        )
