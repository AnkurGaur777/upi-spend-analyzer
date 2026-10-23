# src/spend_analyzer/evaluate.py
import pandas as pd


def evaluate(df: pd.DataFrame, labels: pd.DataFrame, split: str | None = None) -> dict:
    merged = df.merge(labels, on="txn_id")
    if split is not None:
        merged = merged[merged["split"] == split]

    n = len(merged)
    if n == 0:
        return {
            "n": 0,
            "accuracy": 0.0,
            "coverage": 0.0,
            "errors": pd.DataFrame(
                columns=["merchant", "narration", "true_category", "category", "cat_method"]
            ),
        }

    accuracy = float((merged["category"] == merged["true_category"]).mean())
    coverage = float((merged["category"] != "Other").mean())
    errors = merged[merged["category"] != merged["true_category"]][
        ["merchant", "narration", "true_category", "category", "cat_method"]
    ].copy()

    return {
        "n": n,
        "accuracy": accuracy,
        "coverage": coverage,
        "errors": errors,
    }


def per_category_report(df: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    merged = df.merge(labels, on="txn_id")
    categories = sorted(merged["true_category"].unique())
    rows = []
    for cat in categories:
        support = int((merged["true_category"] == cat).sum())
        tp = int(((merged["true_category"] == cat) & (merged["category"] == cat)).sum())
        predicted_count = int((merged["category"] == cat).sum())
        precision = tp / predicted_count if predicted_count > 0 else 0.0
        recall = tp / support if support > 0 else 0.0
        rows.append({
            "category": cat,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "support": support,
        })
    return pd.DataFrame(rows).set_index("category")
