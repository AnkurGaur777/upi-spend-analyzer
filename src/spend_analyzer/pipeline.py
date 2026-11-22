# src/spend_analyzer/pipeline.py
import argparse
import re
import sys
import time
from pathlib import Path
import pandas as pd

from spend_analyzer.parsers import parse_csv
from spend_analyzer.cleaning import clean
from spend_analyzer.categorize import (
    categorize, load_rules, load_lexicon, load_first_names
)
from spend_analyzer.recurring import detect_recurring
from spend_analyzer.load import get_engine, load_transactions, load_recurring

SELF_RE = re.compile(r"\bSELF\b", re.I)


def _find_ref_path(filename: str) -> Path:
    p = Path("data/reference") / filename
    if p.exists():
        return p
    # Fallback relative to this file
    alt = Path(__file__).resolve().parent.parent.parent / "data" / "reference" / filename
    if alt.exists():
        return alt
    return p


def run(
    csv_path: str | Path,
    fmt: str = "auto",
    bank: str | None = None,
    engine=None,
):
    t0 = time.perf_counter()

    if engine is None:
        engine = get_engine()

    # 1. Parse
    raw_df = parse_csv(str(csv_path), fmt=fmt, bank=bank)

    # 2. Clean
    cleaned_df = clean(raw_df)

    # 3. Categorize
    rules_path = _find_ref_path("category_rules.csv")
    lexicon_path = _find_ref_path("category_lexicon.csv")
    names_path = _find_ref_path("first_names.txt")

    rules = load_rules(rules_path) if rules_path.exists() else []
    lexicon = load_lexicon(lexicon_path) if lexicon_path.exists() else []
    names = load_first_names(names_path) if names_path.exists() else set()

    df = categorize(cleaned_df, rules, lexicon=lexicon, names=names)

    # 4. Transfer flag update: existing is_transfer OR narration word-matches SELF OR category == "Transfers"
    narr_self = df["narration"].fillna("").astype(str).str.contains(SELF_RE, regex=True)
    cat_transfer = df["category"] == "Transfers"
    existing_transfer = df["is_transfer"].astype(bool) if "is_transfer" in df.columns else False
    df["is_transfer"] = (existing_transfer | narr_self | cat_transfer).astype(int)

    # 5. Detect recurring
    rec = detect_recurring(df)

    # 6. Load into database
    inserted = load_transactions(df, engine)
    load_recurring(rec, engine)

    # Metrics
    coverage = (df["category"] != "Other").mean() if len(df) > 0 else 0.0
    runtime = time.perf_counter() - t0

    print(
        f"parsed={len(df)} inserted={inserted} coverage={coverage:.1%} "
        f"subscriptions={len(rec)} runtime={runtime:.1f}s"
    )

    return df, rec


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run spend analyzer pipeline")
    parser.add_argument("csv_path", help="Path to statement CSV")
    parser.add_argument("fmt", nargs="?", default="auto", help="Bank format layout (default: auto)")
    parser.add_argument("--bank", "-b", dest="bank", default=None, help="Explicit bank format layout")
    args = parser.parse_args()

    run(args.csv_path, fmt=args.fmt, bank=args.bank)
