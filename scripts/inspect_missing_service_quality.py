
"""Inspect service-quality records without measured results."""

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
    df = pd.read_parquet(DATA_PATH)

    percentage = "Résultat indicateurs en %"
    occurrence = "Résultat indicateurs en occurrence"

    missing = df[
        df[percentage].isna() & df[occurrence].isna()
    ].copy()

    columns = [
        "Année",
        "Trimestre",
        "Opérateur",
        "Mode",
        "Groupe de lignes",
        "ID_Line",
        "Ligne",
        "Thématique",
        "Indicateur",
        "Objectif référence contrat",
        "Pénalité",
    ]

    print(f"Rows without either measurement: {len(missing):,}")

    print("\n--- Sample of 30 rows ---")
    print(
        missing[columns]
        .sort_values(
            ["Indicateur", "Année", "Trimestre"],
            na_position="last",
        )
        .head(30)
        .to_string(index=False)
    )

    print("\n--- Missing measurements by indicator and year ---")
    summary = (
        missing.groupby(["Indicateur", "Année"])
        .size()
        .unstack(fill_value=0)
    )
    print(summary.to_string())

    print("\n--- Penalty by year ---")
    print(
        pd.crosstab(
            missing["Année"],
            missing["Pénalité"].fillna("<NULL>"),
        ).to_string()
    )


if __name__ == "__main__":
    main()
