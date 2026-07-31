"""Download all 3 source datasets for FinSight360 into data/raw/.

- LendingClub accepted loans   (Kaggle: wordsforthewise/lending-club)
- PaySim1 mobile money txns    (Kaggle: ealaxi/paysim1)
- 5 years daily OHLCV for 5 Nifty 50 tickers (yfinance, no auth needed)

Kaggle datasets require Kaggle API credentials: place kaggle.json at
~/.kaggle/kaggle.json, or set KAGGLE_USERNAME / KAGGLE_KEY env vars.
See https://www.kaggle.com/docs/api. Each Kaggle dataset is fetched via
kagglehub first; if kagglehub isn't installed or fails, this falls back
to the `kaggle` CLI (manual Kaggle API).
"""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

RAW_DIR = Path(__file__).resolve().parent / "raw"

LENDING_CLUB_SLUG = "wordsforthewise/lending-club"
PAYSIM_SLUG = "ealaxi/paysim1"
NIFTY_TICKERS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]


def _download_via_kagglehub(slug: str) -> Optional[Path]:
    try:
        import kagglehub
    except ImportError:
        return None
    try:
        return Path(kagglehub.dataset_download(slug))
    except Exception as e:
        print(f"  kagglehub download failed for {slug}: {e}")
        return None


def _download_via_kaggle_cli(slug: str, dest: Path) -> Optional[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["kaggle", "datasets", "download", "-d", slug, "-p", str(dest), "--unzip"],
            check=True,
        )
        return dest
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"  kaggle CLI download failed for {slug}: {e}")
        return None


def _fetch_kaggle_dataset(slug: str, staging_subdir: str) -> Optional[Path]:
    """Try kagglehub first, fall back to the manual `kaggle` CLI."""
    print(f"Fetching {slug} ...")
    src_dir = _download_via_kagglehub(slug)
    if src_dir is None:
        src_dir = _download_via_kaggle_cli(slug, RAW_DIR / f"_staging_{staging_subdir}")
    return src_dir


def _find_csv(src_dir: Path, name_hint: str = "") -> Optional[Path]:
    candidates = list(src_dir.rglob("*.csv")) + list(src_dir.rglob("*.csv.gz"))
    if not candidates:
        return None
    if name_hint:
        hinted = [c for c in candidates if name_hint.lower() in c.name.lower()]
        if hinted:
            candidates = hinted
    return max(candidates, key=lambda p: p.stat().st_size)


def download_lending_club() -> None:
    src_dir = _fetch_kaggle_dataset(LENDING_CLUB_SLUG, "lending_club")
    if src_dir is None:
        print("  SKIPPED: could not fetch LendingClub data. Configure Kaggle API"
              " credentials (~/.kaggle/kaggle.json) and re-run.")
        return
    csv_path = _find_csv(src_dir, name_hint="accepted")
    if csv_path is None:
        print("  SKIPPED: no accepted-loans CSV found in downloaded dataset.")
        return
    dest = RAW_DIR / ("lending_club_accepted.csv.gz" if csv_path.name.endswith(".csv.gz")
                       else "lending_club_accepted.csv")
    shutil.copy2(csv_path, dest)
    print(f"  Saved -> {dest}")


def download_paysim() -> None:
    src_dir = _fetch_kaggle_dataset(PAYSIM_SLUG, "paysim")
    if src_dir is None:
        print("  SKIPPED: could not fetch PaySim data. Configure Kaggle API"
              " credentials (~/.kaggle/kaggle.json) and re-run.")
        return
    csv_path = _find_csv(src_dir)
    if csv_path is None:
        print("  SKIPPED: no CSV found in downloaded PaySim dataset.")
        return
    dest = RAW_DIR / "paysim.csv"
    shutil.copy2(csv_path, dest)
    print(f"  Saved -> {dest}")


def download_nifty_prices(tickers=NIFTY_TICKERS, period="5y") -> None:
    print(f"Fetching {period} of daily OHLCV for {tickers} via yfinance ...")
    frames = []
    for ticker in tickers:
        df = yf.download(ticker, period=period, interval="1d", auto_adjust=False, progress=False)
        if df.empty:
            print(f"  WARNING: no data returned for {ticker}")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df.insert(0, "ticker", ticker)
        frames.append(df)
    if not frames:
        print("  SKIPPED: no ticker data retrieved.")
        return
    combined = pd.concat(frames, ignore_index=True)
    dest = RAW_DIR / "nifty50_prices.csv"
    combined.to_csv(dest, index=False)
    print(f"  Saved -> {dest} ({len(combined)} rows)")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    download_lending_club()
    download_paysim()
    download_nifty_prices()


if __name__ == "__main__":
    main()
