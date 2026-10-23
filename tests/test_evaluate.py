from pathlib import Path
import pandas as pd
from spend_analyzer.evaluate import evaluate, per_category_report

ALLOWED_CATEGORIES = {
    "Food & Dining", "Groceries", "Transport", "Shopping",
    "Bills & Utilities", "Rent", "Subscriptions", "Health",
    "Entertainment", "Investments", "Cash Withdrawal", "Transfers",
    "Income", "Other"
}


def test_evaluate_basic_and_errors():
    df = pd.DataFrame({
        "txn_id": ["t1", "t2", "t3", "t4"],
        "merchant": ["M1", "M2", "M3", "M4"],
        "narration": ["N1", "N2", "N3", "N4"],
        "category": ["Food & Dining", "Other", "Transport", "Shopping"],
        "cat_method": ["rule", "none", "fuzzy", "rule"],
    })
    labels = pd.DataFrame({
        "txn_id": ["t1", "t2", "t3", "t4"],
        "true_category": ["Food & Dining", "Shopping", "Transport", "Other"],
        "split": ["dev", "dev", "test", "test"],
    })

    res = evaluate(df, labels)
    assert res["n"] == 4
    assert res["accuracy"] == 0.5
    assert res["coverage"] == 0.75
    assert len(res["errors"]) == 2
    assert (res["errors"]["true_category"] != res["errors"]["category"]).all()
    assert list(res["errors"].columns) == [
        "merchant", "narration", "true_category", "category", "cat_method"
    ]


def test_evaluate_split_filter():
    df = pd.DataFrame({
        "txn_id": ["t1", "t2", "t3"],
        "merchant": ["M1", "M2", "M3"],
        "narration": ["N1", "N2", "N3"],
        "category": ["Food & Dining", "Shopping", "Transport"],
        "cat_method": ["rule", "rule", "rule"],
    })
    labels = pd.DataFrame({
        "txn_id": ["t1", "t2", "t3"],
        "true_category": ["Food & Dining", "Shopping", "Groceries"],
        "split": ["dev", "dev", "test"],
    })

    res_dev = evaluate(df, labels, split="dev")
    assert res_dev["n"] == 2
    assert res_dev["accuracy"] == 1.0
    assert len(res_dev["errors"]) == 0

    res_test = evaluate(df, labels, split="test")
    assert res_test["n"] == 1
    assert res_test["accuracy"] == 0.0
    assert len(res_test["errors"]) == 1


def test_per_category_report():
    df = pd.DataFrame({
        "txn_id": ["t1", "t2", "t3"],
        "category": ["Food & Dining", "Food & Dining", "Shopping"],
    })
    labels = pd.DataFrame({
        "txn_id": ["t1", "t2", "t3"],
        "true_category": ["Food & Dining", "Shopping", "Shopping"],
        "split": ["dev", "dev", "test"],
    })
    rep = per_category_report(df, labels)
    assert "precision" in rep.columns
    assert "recall" in rep.columns
    assert "support" in rep.columns
    assert rep.loc["Food & Dining", "support"] == 1
    assert rep.loc["Shopping", "support"] == 2


def test_labelled_sample_file():
    path = Path("data/reference/labelled_sample.csv")
    assert path.exists(), "labelled_sample.csv does not exist"
    df = pd.read_csv(path)
    assert len(df) == 300
    assert df["txn_id"].is_unique
    assert set(df["split"].unique()) == {"dev", "test"}
    assert df["true_category"].isin(ALLOWED_CATEGORIES).all()
