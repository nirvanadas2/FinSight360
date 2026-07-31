"""Print and save a data inventory (row count, columns, dtypes, % missing)
for each raw dataset in data/raw/. Run after data/download_data.py.
"""

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
REPORT_PATH = Path(__file__).resolve().parent.parent / "reports" / "data_inventory.md"

FILES = {
    "LendingClub Accepted Loans": "lending_club_accepted.csv",
    "PaySim Transactions": "paysim.csv",
    "Nifty 50 Prices": "nifty50_prices.csv",
}


def inventory_for(path: Path) -> str:
    if not path.exists():
        gz_path = path.with_suffix(path.suffix + ".gz")
        if gz_path.exists():
            path = gz_path
        else:
            return f"**File not found:** `{path.name}` (run `data/download_data.py` first)\n"

    df = pd.read_csv(path, low_memory=False)
    n_rows, n_cols = df.shape
    missing_pct = (df.isna().mean() * 100).round(2)

    lines = [
        f"- **Rows:** {n_rows:,}",
        f"- **Columns:** {n_cols}",
        "",
        "| Column | Dtype | % Missing |",
        "|---|---|---|",
    ]
    for col in df.columns:
        lines.append(f"| {col} | {df[col].dtype} | {missing_pct[col]} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    sections = ["# Data Inventory\n"]
    for title, filename in FILES.items():
        print(f"\n=== {title} ({filename}) ===")
        section_md = inventory_for(RAW_DIR / filename)
        print(section_md)
        sections.append(f"## {title}\n\n{section_md}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(sections), encoding="utf-8")
    print(f"\nSaved report -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
