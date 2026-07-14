"""One-shot runner: generate -> ETL -> analytics -> ML."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics import should_cost, variance
from src.generate_data import generate
from src.ml import anomaly_risk
from src.ml.semantic_qa import demo
from src.pipelines import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ProcureIQ end-to-end")
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--demo-qa", action="store_true")
    args = parser.parse_args()

    if not args.skip_generate:
        generate(n_months=args.months)
    run_pipeline.run_all()
    should_cost.run()
    variance.run()
    anomaly_risk.run()
    if args.demo_qa:
        demo()
    print("\nProcureIQ ready.")
    print("  Dashboard:  streamlit run src/dashboard/app.py")
    print("  Semantic QA: python -m src.ml.semantic_qa")


if __name__ == "__main__":
    main()
