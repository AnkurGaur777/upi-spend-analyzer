# scripts/evaluate_categorizer.py
import pandas as pd
from spend_analyzer.parsers import parse_csv
from spend_analyzer.cleaning import clean
from spend_analyzer.categorize import categorize, load_rules
from spend_analyzer.evaluate import evaluate, per_category_report

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)

raw = parse_csv("data/raw/synthetic/statement_messy.csv")
cleaned = clean(raw)
rules = load_rules("data/reference/category_rules.csv")
df = categorize(cleaned, rules)

labels = pd.read_csv("data/reference/labelled_sample.csv")

eval_all = evaluate(df, labels)
eval_dev = evaluate(df, labels, split="dev")
eval_test = evaluate(df, labels, split="test")

print("=== Evaluation Summary ===")
print(f"All  (n={eval_all['n']}): Accuracy = {eval_all['accuracy']:.2%}, Coverage = {eval_all['coverage']:.2%}")
print(f"Dev  (n={eval_dev['n']}): Accuracy = {eval_dev['accuracy']:.2%}, Coverage = {eval_dev['coverage']:.2%}")
print(f"Test (n={eval_test['n']}): Accuracy = {eval_test['accuracy']:.2%}, Coverage = {eval_test['coverage']:.2%}")

print("\n=== Per-Category Report (All Rows) ===")
print(per_category_report(df, labels).to_string())

print("\n=== Accuracy by cat_method ===")
merged = df.merge(labels, on="txn_id")
merged["is_correct"] = merged["category"] == merged["true_category"]
method_acc = merged.groupby("cat_method").agg(
    total=("txn_id", "count"),
    correct=("is_correct", "sum"),
    accuracy=("is_correct", "mean"),
).sort_values(by="total", ascending=False)
print(method_acc.to_string())

print(f"\n=== Full List of Dev Errors ({len(eval_dev['errors'])} rows) ===")
dev_errors = eval_dev["errors"].rename(columns={"category": "predicted"})[
    ["merchant", "true_category", "predicted", "cat_method"]
].sort_values(by="merchant")
print(dev_errors.to_string(index=False))

print(f"\n=== Test Errors Count ===")
print(f"Total test errors: {len(eval_test['errors'])}")
