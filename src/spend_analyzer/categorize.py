# src/spend_analyzer/categorize.py
import functools
import re
import pandas as pd
from rapidfuzz import fuzz, process


@functools.lru_cache(maxsize=2048)
def _compile_kw_pattern(keyword: str) -> re.Pattern:
    return re.compile(rf"(?<![A-Z0-9]){re.escape(keyword)}(?![A-Z0-9])")


def load_rules(path: str):
    df = pd.read_csv(path)
    df["kwlen"] = df["keyword"].str.len()
    df = df.sort_values(["priority", "kwlen"], ascending=False)
    return list(zip(df["keyword"].str.upper(), df["category"]))


def rule_category(text: str, rules):
    t = (text or "").upper()
    for kw, cat in rules:
        pattern = kw if hasattr(kw, "search") else _compile_kw_pattern(kw)
        if pattern.search(t):
            return cat
    return None


def categorize(df: pd.DataFrame, rules, fuzzy_cutoff: int = 88) -> pd.DataFrame:
    df = df.copy()
    kw_choices = [kw for kw, _ in rules if len(kw) >= 5]
    kw_to_cat = dict(rules)
    cats, methods = [], []
    for narr, merch in zip(df["narration"], df["merchant"]):
        c = rule_category(f"{narr} {merch}", rules)
        if c:
            cats.append(c)
            methods.append("rule")
            continue
        hit = process.extractOne(merch, kw_choices, scorer=fuzz.token_set_ratio, score_cutoff=fuzzy_cutoff)
        if hit:
            cats.append(kw_to_cat[hit[0]])
            methods.append("fuzzy")
            continue
        cats.append("Other")
        methods.append("none")
    df["category"], df["cat_method"] = cats, methods
    return df
