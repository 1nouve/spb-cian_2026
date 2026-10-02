from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a CIAN snapshot for analysis.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Raw CSV. If omitted, the latest data/raw/cian_spb_sale_*.csv is used.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/cian_spb_sale_clean.csv"),
    )
    return parser.parse_args()


def latest_raw_file(raw_dir: Path = Path("data/raw")) -> Path:
    files = sorted(raw_dir.glob("cian_spb_sale_*.csv"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(
            "No raw CIAN snapshot found in data/raw/. Run collect_cian.py or provide --input."
        )
    return files[-1]


def clean_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(
        series.astype(str)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)", expand=False),
        errors="coerce",
    )


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    # Standardise the main numeric fields.
    for col in ["price", "total_meters", "rooms", "rooms_count", "floor", "floors_count"]:
        if col in data.columns:
            data[col] = clean_numeric(data[col])

    if "rooms" not in data.columns and "rooms_count" in data.columns:
        data["rooms"] = data["rooms_count"]

    if "requested_segment" in data.columns:
        data.loc[data["requested_segment"].eq("studio"), "rooms"] = 0

    # Recover offer_id if it was not produced during collection.
    if "offer_id" not in data.columns and "url" in data.columns:
        data["offer_id"] = data["url"].astype(str).str.extract(r"/flat/(\d+)", expand=False)

    # Remove duplicate listing cards from the snapshot.
    if "offer_id" in data.columns and data["offer_id"].notna().any():
        data = data.drop_duplicates(subset=["offer_id"], keep="first")
    elif "url" in data.columns:
        data = data.drop_duplicates(subset=["url"], keep="first")
    else:
        data = data.drop_duplicates()

    # Minimal sanity checks: avoid aggressive trimming of the current market.
    required = {"price", "total_meters"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    data = data[
        (data["price"] > 0)
        & data["total_meters"].between(10, 500)
    ].copy()

    data["price_per_m2"] = data["price"] / data["total_meters"]
    data = data[data["price_per_m2"].between(50_000, 3_000_000)].copy()

    if {"floor", "floors_count"}.issubset(data.columns):
        known_floor = (data["floor"] > 0) & (data["floors_count"] > 0)
        data = data[~known_floor | (data["floor"] <= data["floors_count"])].copy()

    data["price_mln"] = data["price"] / 1_000_000

    if "rooms" in data.columns:
        data["rooms"] = data["rooms"].round().astype("Int64")

    preferred = [
        "offer_id", "collected_at", "url", "rooms", "price", "price_mln",
        "total_meters", "price_per_m2", "district", "underground",
        "floor", "floors_count", "residential_complex", "author_type",
        "year_of_construction", "object_type", "house_material_type",
        "finish_type", "living_meters", "kitchen_meters",
    ]
    ordered = [c for c in preferred if c in data.columns]
    extra = [c for c in data.columns if c not in ordered]
    return data[ordered + extra].reset_index(drop=True)


def main() -> None:
    args = parse_args()
    source = args.input or latest_raw_file()
    df = pd.read_csv(source)
    clean = prepare(df)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(args.output, index=False)

    print(f"Source rows: {len(df):,}".replace(",", " "))
    print(f"Clean rows:  {len(clean):,}".replace(",", " "))
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
