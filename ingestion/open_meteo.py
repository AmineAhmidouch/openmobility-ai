
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "settings.yml"

RAW_DIR = ROOT / "storage" / "raw" / "open_meteo"
PROCESSED_DIR = ROOT / "storage" / "processed" / "open_meteo"

HOURLY_VARIABLES = [
    "temperature_2m",
    "precipitation",
    "relative_humidity_2m",
    "wind_speed_10m",
]

logger = logging.getLogger(__name__)


def load_config() -> dict[str, Any]:
    """Load and validate Open-Meteo configuration."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    if not isinstance(config, dict):
        raise TypeError("Configuration file must contain a YAML mapping")

    settings = config.get("open_meteo")

    if settings is None:
        raise ValueError("Missing 'open_meteo' configuration")

    if not isinstance(settings, dict):
        raise TypeError("'open_meteo' configuration must be a mapping")

    for section in ("location", "date_range", "request"):
        if section not in settings:
            raise ValueError(f"Missing configuration section: {section}")

        if not isinstance(settings[section], dict):
            raise TypeError(
                f"Configuration section '{section}' must be a mapping"
            )

    if not isinstance(settings.get("base_url"), str) or not settings[
        "base_url"
    ].strip():
        raise ValueError("Missing or invalid Open-Meteo base_url")

    variables = settings.get("hourly_variables")

    if not isinstance(variables, list) or not variables:
        raise ValueError("hourly_variables must be a non-empty list")

    if not all(isinstance(variable, str) and variable for variable in variables):
        raise ValueError("Each hourly variable must be a non-empty string")

    location = settings["location"]

    for key in ("latitude", "longitude"):
        if key not in location:
            raise ValueError(f"Missing location setting: {key}")

        value = location[key]

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"Location setting '{key}' must be numeric")

    if not -90 <= location["latitude"] <= 90:
        raise ValueError("latitude must be between -90 and 90")

    if not -180 <= location["longitude"] <= 180:
        raise ValueError("longitude must be between -180 and 180")

    dates = settings["date_range"]

    for key in ("start_date", "end_date"):
        if key not in dates:
            raise ValueError(f"Missing date setting: {key}")

        if not isinstance(dates[key], str):
            raise TypeError(f"{key} must be a string in YYYY-MM-DD format")

        try:
            datetime.strptime(dates[key], "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(
                f"{key} must use YYYY-MM-DD format"
            ) from exc

    start = datetime.strptime(
        dates["start_date"], "%Y-%m-%d"
    ).date()
    end = datetime.strptime(
        dates["end_date"], "%Y-%m-%d"
    ).date()

    if end < start:
        raise ValueError("end_date must be on or after start_date")

    request_config = settings["request"]

    timeout = request_config.get("timeout_seconds", 60)
    retries = request_config.get("max_retries", 3)
    backoff = request_config.get("backoff_factor", 1.0)

    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise ValueError("timeout_seconds must be positive")

    if (
        isinstance(retries, bool)
        or not isinstance(retries, int)
        or retries < 0
    ):
        raise ValueError("max_retries must be a non-negative integer")

    if (
        isinstance(backoff, bool)
        or not isinstance(backoff, (int, float))
        or backoff < 0
    ):
        raise ValueError("backoff_factor must be non-negative")

    return settings


def create_http_session(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
) -> requests.Session:
    """Create a session that retries transient HTTP failures."""

    retry_policy = Retry(
        total=max_retries,
        connect=max_retries,
        read=max_retries,
        status=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry_policy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def parse_weather_payload(
    payload: dict[str, Any],
    ingested_at: datetime | None = None,
    hourly_variables: list[str] | None = None,
) -> pd.DataFrame:
    """Validate and convert an Open-Meteo response into a DataFrame."""

    if not isinstance(payload, dict):
        raise TypeError("Open-Meteo response must be a JSON object")

    if payload.get("error"):
        raise ValueError(f"Open-Meteo API error: {payload}")

    variables = (
        hourly_variables
        if hourly_variables is not None
        else HOURLY_VARIABLES
    )

    if not variables:
        raise ValueError("At least one hourly variable is required")

    hourly = payload.get("hourly")

    if not isinstance(hourly, dict):
        raise TypeError("'hourly' must be a dictionary")

    timestamps = hourly.get("time")

    if not isinstance(timestamps, list) or not timestamps:
        raise ValueError("Missing hourly observations or timestamps")

    if len(timestamps) != len(set(timestamps)):
        raise ValueError("Duplicate observation timestamps detected")

    for variable in variables:
        if variable not in hourly:
            raise ValueError(f"Missing expected variable: {variable}")

        if len(hourly[variable]) != len(timestamps):
            raise ValueError(f"Unequal array lengths for {variable}")

    df = pd.DataFrame(
        {
            "observation_time": pd.to_datetime(
                timestamps,
                utc=True,
                errors="raise",
            ),
            **{
                variable: hourly[variable]
                for variable in variables
            },
        }
    )

    if df["observation_time"].isna().any():
        raise ValueError("Invalid observation timestamps")

    for variable in variables:
        df[variable] = pd.to_numeric(
            df[variable],
            errors="raise",
        )

    if df[variables].isna().all(axis=1).any():
        raise ValueError(
            "All weather values are missing for an observation"
        )

    ingestion_time = ingested_at or datetime.now(UTC)

    df["ingested_at"] = pd.Timestamp(ingestion_time)
    df["source"] = "open_meteo_archive"

    return df


def validate_hourly_coverage(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> None:
    """Ensure every expected UTC hour is present exactly once."""

    start = pd.Timestamp(f"{start_date} 00:00:00", tz="UTC")
    end = pd.Timestamp(f"{end_date} 23:00:00", tz="UTC")

    expected = pd.date_range(
        start=start,
        end=end,
        freq="h",
    )

    actual = pd.DatetimeIndex(df["observation_time"])

    if not actual.equals(expected):
        missing = expected.difference(actual)
        unexpected = actual.difference(expected)

        raise ValueError(
            "Hourly coverage validation failed: "
            f"expected {len(expected)} observations, got {len(actual)}; "
            f"missing={len(missing)}, unexpected={len(unexpected)}"
        )


def ingest_weather(
    start_date: str | None = None,
    end_date: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Path:
    """Fetch historical weather and save raw JSON and processed Parquet."""

    config = load_config()

    location = config["location"]
    date_range = config["date_range"]
    request_config = config["request"]

    start_date = start_date or date_range["start_date"]
    end_date = end_date or date_range["end_date"]

    latitude = latitude if latitude is not None else location["latitude"]
    longitude = longitude if longitude is not None else location["longitude"]

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError("Dates must use YYYY-MM-DD format") from exc

    if end < start:
        raise ValueError("end_date must be on or after start_date")

    if (
        isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or not -90 <= latitude <= 90
    ):
        raise ValueError("latitude must be between -90 and 90")

    if (
        isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
        or not -180 <= longitude <= 180
    ):
        raise ValueError("longitude must be between -180 and 180")

    variables = config["hourly_variables"]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": "UTC",
    }

    logger.info(
        "Fetching weather for latitude=%s longitude=%s, dates=%s to %s",
        latitude,
        longitude,
        start_date,
        end_date,
    )

    session = create_http_session(
        max_retries=request_config.get("max_retries", 3),
        backoff_factor=request_config.get("backoff_factor", 1.0),
    )

    try:
        response = session.get(
            config["base_url"],
            params=params,
            timeout=request_config.get("timeout_seconds", 60),
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        session.close()

    if not isinstance(payload, dict):
        raise TypeError("Open-Meteo response must be a JSON object")

    if payload.get("error"):
        raise ValueError(f"Open-Meteo API error: {payload}")

    ingested_at = datetime.now(UTC)

    df = parse_weather_payload(
        payload,
        ingested_at=ingested_at,
        hourly_variables=variables,
    )

    validate_hourly_coverage(
        df,
        start_date,
        end_date,
    )

    run_timestamp = ingested_at.strftime("%Y%m%dT%H%M%S%fZ")

    raw_path = (
        RAW_DIR
        / f"weather_{start_date}_{end_date}_{run_timestamp}.json"
    )

    parquet_path = (
        PROCESSED_DIR
        / f"weather_{start_date}_{end_date}.parquet"
    )

    raw_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    df.to_parquet(parquet_path, index=False)

    logger.info(
        "Ingestion completed: rows=%s raw=%s parquet=%s",
        len(df),
        raw_path,
        parquet_path,
    )

    return parquet_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    output_path = ingest_weather()
    result = pd.read_parquet(output_path)

    print(f"\nOutput: {output_path}")
    print(f"Rows: {len(result)}")
    print(result.head().to_string(index=False))
