from pathlib import Path

import pandas as pd

path = (
    Path(__file__).resolve().parents[1]
    / "storage"
    / "processed"
    / "service_quality"
    / "service_quality.parquet"
)

df = pd.read_parquet(path)

pct = "Résultat indicateurs en %"
occ = "Résultat indicateurs en occurrence"

df["missing_both"] = df[pct].isna() & df[occ].isna()

summary = (
    df.groupby(["Indicateur", "Année"])
    .agg(
        total_rows=("missing_both", "size"),
        missing_rows=("missing_both", "sum"),
    )
    .assign(
        missing_pct=lambda x: (
            100 * x["missing_rows"] / x["total_rows"]
        ).round(1)
    )
    .reset_index()
    .sort_values(
        ["missing_pct", "missing_rows"],
        ascending=False,
    )
)

print(summary.to_string(index=False))