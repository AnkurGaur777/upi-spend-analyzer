# src/spend_analyzer/categorize.py
import functools
import re
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz, process


@functools.lru_cache(maxsize=2048)
def _compile_kw_pattern(keyword: str) -> re.Pattern:
    return re.compile(rf"(?<![A-Z0-9]){re.escape(keyword)}(?![A-Z0-9])")


@functools.lru_cache(maxsize=2048)
def _compile_lexicon_pattern(word: str) -> re.Pattern:
    return re.compile(rf"(?<![A-Z0-9]){re.escape(word)}(?![A-Z0-9])")


def load_rules(path: str | Path):
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


def load_lexicon(path: str | Path) -> list[tuple[str, str]]:
    df = pd.read_csv(path)
    df["word_len"] = df["word"].str.len()
    df = df.sort_values("word_len", ascending=False)
    return list(zip(df["word"].str.upper(), df["category"]))


def lexicon_category(merchant: str, lexicon: list[tuple[str, str]]) -> str | None:
    m = (merchant or "").upper()
    for word, cat in lexicon:
        pattern = word if hasattr(word, "search") else _compile_lexicon_pattern(word)
        if pattern.search(m):
            return cat
    return None


def load_first_names(path: str | Path) -> set[str]:
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip().upper() for line in f if line.strip() and not line.startswith("#")}


def is_person_name(merchant: str, names: set[str], lexicon: list[tuple[str, str]] | None = None) -> bool:
    words = (merchant or "").strip().split()
    if len(words) not in (1, 2):
        return False
    if words[0].upper() not in names:
        return False
    if lexicon and lexicon_category(merchant, lexicon) is not None:
        return False
    return True


def categorize(
    df: pd.DataFrame,
    rules,
    lexicon=None,
    names=None,
    fuzzy_cutoff: int = 88,
) -> pd.DataFrame:
    df = df.copy()
    kw_choices = [kw for kw, _ in rules if len(kw) >= 5]
    kw_to_cat = dict(rules)
    cats, methods = [], []

    for narr, merch in zip(df["narration"], df["merchant"]):
        # 1. Brand rules on narration + merchant
        c = rule_category(f"{narr} {merch}", rules)
        if c:
            cats.append(c)
            methods.append("rule")
            continue

        # 2. Fuzzy on merchant
        hit = process.extractOne(merch, kw_choices, scorer=fuzz.token_set_ratio, score_cutoff=fuzzy_cutoff)
        if hit:
            cats.append(kw_to_cat[hit[0]])
            methods.append("fuzzy")
            continue

        # 3. Lexicon on merchant
        if lexicon is not None:
            c = lexicon_category(merch, lexicon)
            if c:
                cats.append(c)
                methods.append("lexicon")
                continue

        # 4. Person name on merchant
        if names is not None:
            if is_person_name(merch, names, lexicon=lexicon):
                cats.append("Transfers")
                methods.append("p2p")
                continue

        # 5. Fallback
        cats.append("Other")
        methods.append("none")

    df["category"], df["cat_method"] = cats, methods
    return df
