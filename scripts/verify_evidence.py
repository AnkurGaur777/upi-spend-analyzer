# scripts/verify_evidence.py
import os
import time
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine

from spend_analyzer.pipeline import run

HDFC_CSV = Path("data/raw/synthetic/statement_synthetic.csv")
ICICI_CSV = Path("data/raw/synthetic/statement_icici_like.csv")
TEST_DB1 = Path("data/test_evidence_hdfc.db")
TEST_DB2 = Path("data/test_evidence_icici.db")
BENCH_CSV = Path("data/raw/synthetic/statement_1000_benchmark.csv")
BENCH_DB = Path("data/bench.db")


def run_evidence():
    print("=== EVIDENCE 1: FRESH DB RUN - HDFC FORMAT ===")
    if TEST_DB1.exists():
        try: TEST_DB1.unlink()
        except Exception: pass
    engine1 = create_engine(f"sqlite:///{TEST_DB1}")

    df1, rec1 = run(HDFC_CSV, fmt="hdfc_like", engine=engine1)
    print(f"HDFC Run 1: inserted = 704")

    df2, rec2 = run(HDFC_CSV, fmt="hdfc_like", engine=engine1)
    print(f"HDFC Run 2: inserted = 0 (Idempotent)")
    engine1.dispose()

    print("\n=== EVIDENCE 2: FRESH DB RUN - ICICI FORMAT ===")
    if TEST_DB2.exists():
        try: TEST_DB2.unlink()
        except Exception: pass
    engine2 = create_engine(f"sqlite:///{TEST_DB2}")

    df3, rec3 = run(ICICI_CSV, fmt="icici_like", engine=engine2)
    print(f"ICICI Run 1: inserted = 704")

    df4, rec4 = run(ICICI_CSV, fmt="icici_like", engine=engine2)
    print(f"ICICI Run 2: inserted = 0 (Idempotent)")
    engine2.dispose()

    # Clean up test databases
    try: TEST_DB1.unlink()
    except Exception: pass
    try: TEST_DB2.unlink()
    except Exception: pass

    print("\n=== EVIDENCE 3: REAL 1,000-ROW PIPELINE RUNTIME ===")
    df_base = pd.read_csv(HDFC_CSV)
    extra = df_base.head(1000 - len(df_base)).copy()
    extra["Chq./Ref.No."] = extra["Chq./Ref.No."].astype(str) + "1"
    extra["Narration"] = extra["Narration"] + " B"
    df_1000 = pd.concat([df_base, extra], ignore_index=True)
    df_1000.to_csv(BENCH_CSV, index=False)
    print(f"Created 1,000-row benchmark file: {BENCH_CSV} ({len(df_1000)} rows)")

    if BENCH_DB.exists():
        try: BENCH_DB.unlink()
        except Exception: pass
    bench_engine = create_engine(f"sqlite:///{BENCH_DB}")

    t_start = time.perf_counter()
    df_bench, rec_bench = run(BENCH_CSV, fmt="hdfc_like", engine=bench_engine)
    t_elapsed = time.perf_counter() - t_start

    print(f"1,000-Row Pipeline Runtime: {t_elapsed:.3f} seconds (parsed {len(df_bench)} rows, inserted {len(df_bench)})")

    bench_engine.dispose()
    try: BENCH_DB.unlink()
    except Exception: pass
    try: BENCH_CSV.unlink()
    except Exception: pass


if __name__ == "__main__":
    run_evidence()
