"""Pipeline orchestrator - bronze -> silver -> gold."""

from __future__ import annotations

import argparse

from src.pipelines import bronze, gold, silver


def run_all() -> None:
    bronze.run()
    silver.run()
    gold.run()
    print("Pipeline complete: bronze -> silver -> gold")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ProcureIQ medallion pipeline")
    parser.add_argument(
        "--layer",
        choices=["all", "bronze", "silver", "gold"],
        default="all",
    )
    args = parser.parse_args()
    if args.layer == "all":
        run_all()
    elif args.layer == "bronze":
        bronze.run()
    elif args.layer == "silver":
        silver.run()
    else:
        gold.run()


if __name__ == "__main__":
    main()
