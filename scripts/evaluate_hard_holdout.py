# scripts/evaluate_hard_holdout.py
"""Read-only evaluation script for the synthetic hard holdout benchmark.

This script NEVER creates or modifies any files. It evaluates the current
categorization pipeline against data/reference/labelled_holdout_hard.csv.
"""
from pathlib import Path
import pandas as pd

from spend_analyzer.parsers import parse_csv
from spend_analyzer.cleaning import clean
from spend_analyzer.categorize import (
    categorize, load_rules, load_lexicon, load_first_names
)
from spend_analyzer.evaluate import evaluate

RAW_CSV = Path("data/raw/synthetic/statement_hard_holdout.csv")
LABELS_CSV = Path("data/reference/labelled_holdout_hard.csv")


def evaluate_hard_holdout():
    if not RAW_CSV.exists() or not LABELS_CSV.exists():
        raise FileNotFoundError(
            f"Holdout files not found! Expected {RAW_CSV} and {LABELS_CSV}. "
            f"Run scripts/make_hard_holdout.py once to generate them."
        )

    # Load assets (read-only)
    rules = load_rules("data/reference/category_rules.csv")
    lexicon = load_lexicon("data/reference/category_lexicon.csv")
    names = load_first_names("data/reference/first_names.txt")

    # Run pipeline cleaning and categorization in memory
    parsed = parse_csv(RAW_CSV)
    cleaned = clean(parsed)
    categorized = categorize(cleaned, rules, lexicon=lexicon, names=names)

    labels_df = pd.read_csv(LABELS_CSV)
    res = evaluate(categorized, labels_df)

    print("\n=== HARD HOLDOUT EVALUATION SUMMARY ===")
    print(f"Holdout Size: n = {res['n']}")
    print(f"Accuracy:     {res['accuracy']:.2%}")
    print(f"Coverage:     {res['coverage']:.2%}")
    print(f"Misclassified or Unclassified: {len(res['errors'])} rows")

    print("\n=== MISCLASSIFIED / UNCLASSIFIED ROWS ===")
    errs = res["errors"]
    print(errs.to_string(index=False))

    return res


if __name__ == "__main__":
    evaluate_hard_holdout()
