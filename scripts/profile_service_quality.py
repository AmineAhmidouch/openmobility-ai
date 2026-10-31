
"""Profile missing measurements in service-quality data."""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = (
    PROJECT_ROOT
    / "storage"
    / "processed"
    / "service_quality"
    / "service_quality.parquet"
)


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(
            f"Parquet file not found: {DATA_PATH}. "
            "Run service-quality ingestion first."
        )

    df = pd.read_parquet(DATA_PATH)

    percentage = "Résultat indicateurs en %"
    occurrence = "Résultat indicateurs en occurrence"

    missing_both = df[percentage].isna() & df[occurrence].isna()

    print(f"Total rows: {len(df):,}")
    print(f"Rows missing both measurements: {missing_both.sum():,}")

    for column in [
        "Opérateur",
        "Thématique",
        "Indicateur",
        "Mode",
        "Trimestre",
        "Année",
        "Objectif référence contrat",
        "Pénalité",
    ]:
        print(f"\n--- {column}: rows missing both measurements ---")
        counts = (
            df.loc[missing_both, column]
            .fillna("<NULL>")
            .value_counts(dropna=False)
            .head(20)
        )
        print(counts.to_string())

    print("\n--- Measurement availability by year ---")
    yearly = (
        df.assign(
            has_percentage=df[percentage].notna(),
            has_occurrence=df[occurrence].notna(),
            missing_both=missing_both,
        )
        .groupby("Année")
        .agg(
            rows=("Année", "size"),
            with_percentage=("has_percentage", "sum"),
            with_occurrence=("has_occurrence", "sum"),
            missing_both=("missing_both", "sum"),
        )
    )
    print(yearly.to_string())


if __name__ == "__main__":
    main()
