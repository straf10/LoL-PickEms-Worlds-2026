"""Project paths. Scripts resolve every file from here, so they work from any working directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "pickems.duckdb"
ROSTERS_CSV = ROOT / "data" / "rosters_2026.csv"
OUTPUTS = ROOT / "outputs"
