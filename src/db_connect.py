"""SQLAlchemy + psycopg2 wrapper: bulk-load cleaned dataframes into PostgreSQL.

Reads data/processed/*.parquet if present (see data_cleaning.py), otherwise
cleans straight from data/raw/. Loads finsight.loans, finsight.transactions,
and finsight.stock_prices via psycopg2 COPY (fast bulk insert for millions
of rows) and computes stock_prices.daily_return during the load.
"""

import io
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from data_cleaning import (
    LOAN_RAW_COLUMNS,
    LOAN_SCHEMA_COLUMNS,
    PROCESSED_DIR,
    RAW_DIR,
    STOCK_SCHEMA_COLUMNS,
    TXN_SCHEMA_COLUMNS,
    clean_loans,
    clean_stock_prices,
    clean_transactions,
)

load_dotenv()

DB_USER = os.getenv("POSTGRES_USER", "finsight")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "finsight")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5433")
DB_NAME = os.getenv("POSTGRES_DB", "finsight")


def get_engine():
    url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url)


def bulk_load(engine, df: pd.DataFrame, table: str, columns: list) -> int:
    """Load a dataframe into `table` via psycopg2 COPY FROM STDIN.

    Far faster than to_sql()/executemany for multi-million row datasets.
    """
    buf = io.StringIO()
    df[columns].to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cols_sql = ", ".join(columns)
            cur.copy_expert(
                f"COPY {table} ({cols_sql}) FROM STDIN WITH (FORMAT csv, NULL '\\N')",
                buf,
            )
        raw_conn.commit()
    finally:
        raw_conn.close()
    return len(df)


def _read_cleaned(name: str, clean_fn, raw_path: Path, **read_csv_kwargs) -> pd.DataFrame:
    parquet_path = PROCESSED_DIR / f"{name}.parquet"
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    raw_df = pd.read_csv(raw_path, **read_csv_kwargs)
    return clean_fn(raw_df)


def load_loans(engine) -> int:
    df = _read_cleaned(
        "loans", clean_loans, RAW_DIR / "lending_club_accepted.csv",
        usecols=LOAN_RAW_COLUMNS, low_memory=False,
    )
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE finsight.loans RESTART IDENTITY"))
    return bulk_load(engine, df, "finsight.loans", LOAN_SCHEMA_COLUMNS)


def load_transactions(engine) -> int:
    df = _read_cleaned("transactions", clean_transactions, RAW_DIR / "paysim.csv")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE finsight.transactions RESTART IDENTITY"))
    return bulk_load(engine, df, "finsight.transactions", TXN_SCHEMA_COLUMNS)


def load_stock_prices(engine) -> int:
    df = _read_cleaned("stock_prices", clean_stock_prices, RAW_DIR / "nifty50_prices.csv")
    df = df.sort_values(["ticker", "trade_date"]).copy()
    df["daily_return"] = df.groupby("ticker")["adj_close"].pct_change().round(5)
    columns = STOCK_SCHEMA_COLUMNS + ["daily_return"]
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE finsight.stock_prices RESTART IDENTITY"))
    return bulk_load(engine, df, "finsight.stock_prices", columns)


def row_count(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def main() -> None:
    engine = get_engine()

    print("Loading loans ...")
    load_loans(engine)
    print("Loading transactions ...")
    load_transactions(engine)
    print("Loading stock prices ...")
    load_stock_prices(engine)

    print("\nRow counts after load:")
    for table in ["finsight.loans", "finsight.transactions", "finsight.stock_prices"]:
        print(f"  {table}: {row_count(engine, table):,}")


if __name__ == "__main__":
    main()
