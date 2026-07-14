from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_WAREHOUSE = ROOT / "data" / "warehouse"
DATA_EXPORTS = ROOT / "data" / "exports"
CONFIGS = ROOT / "configs"
SQL = ROOT / "sql"
WAREHOUSE_DB = DATA_WAREHOUSE / "procureiq.duckdb"


def ensure_dirs() -> None:
    for p in (DATA_RAW, DATA_WAREHOUSE, DATA_EXPORTS):
        p.mkdir(parents=True, exist_ok=True)