
"""Ingest Île-de-France Mobilités service-quality indicators."""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_PATH = (
    PROJECT_ROOT
    / "storage"
    / "raw"
    / "service_quality"
    / "indicateurs-qualite-service-parcours-voyageur.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "storage"
    / "processed"
    / "service_quality"
    / "service_quality.parquet"
)

REQUIRED_COLUMNS = [
    "Opérateur",
    "Thématique",
    "Indicateur",
    "Mode",
    "Trimestre",
    "Année",
]

# Only columns expected to contain numeric values.
# "Groupe de lignes" and "Objectif référence contrat" can contain text.
NUMERIC_COLUMNS = [
    "DSP",
    "Année",
    "Résultat indicateurs en %",
    "Résultat indicateurs en occurrence",
]

MEASUREMENT_COLUMNS = [
    "Résultat indicateurs en %",
    "Résultat indicateurs en occurrence",
]

VALID_QUARTERS = {"T1", "T2", "T3", "T4"}


def ingest_service_quality(
    source_path: Path = SOURCE_PATH,
    output_path: Path = OUTPUT_PATH,
) -> pd.DataFrame:
    """Validate and write service-quality data to Parquet."""

    if not source_path.is_file():
        raise FileNotFoundError(
            f"Service-quality CSV not found: {source_path}"
        )

    df = pd.read_csv(
        source_path,
        encoding="utf-8-sig",
        sep=None,
        engine="python",
    )

    # Remove a possible BOM and whitespace from column names.
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
    )

    if df.empty:
        raise ValueError("Service-quality CSV contains no records.")

    if df.columns.duplicated().any():
        duplicates = df.columns[df.columns.duplicated()].tolist()
        raise ValueError(f"Duplicate column names: {duplicates}")

    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    # Trim text and standardize empty strings as nulls.
    for column in df.select_dtypes(
        include=["object", "string"]
    ).columns:
        df[column] = df[column].str.strip()
        df[column] = df[column].replace("", pd.NA)

    # Required dimensions must be populated.
    for column in REQUIRED_COLUMNS:
        if df[column].isna().any():
            raise ValueError(
                f"Required column '{column}' contains null values."
            )

    # Treat dash placeholders in numeric measurements as nulls.
    for column in MEASUREMENT_COLUMNS:
        if column in df.columns:
            df[column] = df[column].replace("-", pd.NA)

    # Convert numeric fields and reject malformed values.
    for column in NUMERIC_COLUMNS:
        if column not in df.columns:
            continue

        original = df[column]
        converted = pd.to_numeric(original, errors="coerce")

        invalid = original.notna() & converted.isna()
        if invalid.any():
            examples = original[invalid].head(5).tolist()
            raise ValueError(
                f"Invalid numeric values in '{column}': {examples}"
            )

        df[column] = converted

    # Validate quarter values.
    if not df["Trimestre"].isin(VALID_QUARTERS).all():
        invalid = sorted(
            df.loc[
                ~df["Trimestre"].isin(VALID_QUARTERS),
                "Trimestre",
            ].dropna().unique().tolist()
        )
        raise ValueError(f"Invalid quarter values: {invalid}")

    # Validate year values.
    if df["Année"].isna().any():
        raise ValueError("'Année' contains null values.")

    if not df["Année"].between(2000, 2100).all():
        raise ValueError("'Année' contains out-of-range values.")

    # Missing measurements are reported but rows are preserved.
    has_measurement = (
        df["Résultat indicateurs en %"].notna()
        | df["Résultat indicateurs en occurrence"].notna()
    )

    missing_measurement_count = int((~has_measurement).sum())

    if missing_measurement_count:
        print(
            f"Warning: {missing_measurement_count:,} rows have "
            "no percentage or occurrence measurement. "
            "Rows will be preserved."
        )

    # Reject exact duplicate rows.
    duplicate_count = int(df.duplicated().sum())
    if duplicate_count:
        raise ValueError(
            f"Found {duplicate_count} exact duplicate rows."
        )

    # Write validated data to Parquet.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)

    print("\nService-quality ingestion completed.")
    print(f"Source: {source_path}")
    print(f"Output: {output_path}")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print(f"Exact duplicates: {df.duplicated().sum():,}")
    print(f"Rows without measurements: {missing_measurement_count:,}")

    print("\nNull counts by column:")
    print(df.isna().sum().to_string())

    return df


if __name__ == "__main__":
    ingest_service_quality()
