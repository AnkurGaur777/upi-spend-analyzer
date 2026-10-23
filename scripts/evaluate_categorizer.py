# scripts/evaluate_categorizer.py
import argparse
import json
from pathlib import Path
import pandas as pd

from spend_analyzer.parsers import parse_csv
from spend_analyzer.cleaning import clean
from spend_analyzer.categorize import (
    categorize, load_rules, load_lexicon, load_first_names
)
from spend_analyzer.evaluate import evaluate, per_category_report

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)

parser = argparse.ArgumentParser(description="Evaluate categorizer")
parser.add_argument("--final", action="store_true", help="Include test split metrics in report")
args = parser.parse_args()

# Load assets and run pipeline
raw = parse_csv("data/raw/synthetic/statement_messy.csv")
cleaned = clean(raw)
rules = load_rules("data/reference/category_rules.csv")
lexicon = load_lexicon("data/reference/category_lexicon.csv")
names = load_first_names("data/reference/first_names.txt")

df = categorize(cleaned, rules, lexicon=lexicon, names=names)
labels = pd.read_csv("data/reference/labelled_sample.csv")

eval_all = evaluate(df, labels)
eval_dev = evaluate(df, labels, split="dev")

print("=== Evaluation Summary ===")
print(f"All  (n={eval_all['n']}): Accuracy = {eval_all['accuracy']:.2%}, Coverage = {eval_all['coverage']:.2%}")
print(f"Dev  (n={eval_dev['n']}): Accuracy = {eval_dev['accuracy']:.2%}, Coverage = {eval_dev['coverage']:.2%}")

merged = df.merge(labels, on="txn_id")
dev_merged = merged[merged["split"] == "dev"].copy()

print("\n=== Per-Category Report (DEV Rows) ===")
dev_df = df[df["txn_id"].isin(dev_merged["txn_id"])]
dev_labels = labels[labels["split"] == "dev"]
dev_cat_report = per_category_report(dev_df, dev_labels)
print(dev_cat_report.to_string())

print("\n=== Accuracy by cat_method (DEV Rows) ===")
dev_merged["is_correct"] = dev_merged["category"] == dev_merged["true_category"]
dev_method_acc = dev_merged.groupby("cat_method").agg(
    total=("txn_id", "count"),
    correct=("is_correct", "sum"),
    accuracy=("is_correct", "mean"),
).sort_values(by="total", ascending=False)
print(dev_method_acc.to_string())

dev_errors = eval_dev["errors"].rename(columns={"category": "predicted"})[
    ["merchant", "true_category", "predicted", "cat_method"]
].sort_values(by="merchant")
print(f"\n=== Full List of Remaining Dev Errors ({len(dev_errors)} rows) ===")
if len(dev_errors) > 0:
    print(dev_errors.to_string(index=False))
else:
    print("None (0 dev errors)")

metrics_to_save = {
    "all": {
        "n": eval_all["n"],
        "accuracy": round(eval_all["accuracy"], 4),
        "coverage": round(eval_all["coverage"], 4),
    },
    "dev": {
        "n": eval_dev["n"],
        "accuracy": round(eval_dev["accuracy"], 4),
        "coverage": round(eval_dev["coverage"], 4),
        "per_category": dev_cat_report.to_dict(orient="index"),
        "by_cat_method": dev_method_acc.to_dict(orient="index"),
        "error_count": len(dev_errors),
    },
}

if args.final:
    eval_test = evaluate(df, labels, split="test")
    test_df = df[df["txn_id"].isin(labels[labels["split"] == "test"]["txn_id"])]
    test_labels = labels[labels["split"] == "test"]
    test_cat_report = per_category_report(test_df, test_labels)

    print(f"\nTest (n={eval_test['n']}): Accuracy = {eval_test['accuracy']:.2%}, Coverage = {eval_test['coverage']:.2%}")
    print("\n=== Per-Category Report (TEST Rows) ===")
    print(test_cat_report.to_string())

    metrics_to_save["test"] = {
        "n": eval_test["n"],
        "accuracy": round(eval_test["accuracy"], 4),
        "coverage": round(eval_test["coverage"], 4),
        "per_category": test_cat_report.to_dict(orient="index"),
        "error_count": len(eval_test["errors"]),
    }

metrics_file = Path("docs/categorizer_metrics.json")
metrics_file.parent.mkdir(parents=True, exist_ok=True)
with open(metrics_file, "w", encoding="utf-8") as f:
    json.dump(metrics_to_save, f, indent=2)
print(f"\nMetrics saved to {metrics_file}")
