"""Clean the 3 raw FinSight360 datasets into schema-ready DataFrames.

Fixes dtypes (dates, %-strings), imputes/drops nulls, dedupes, winsorizes
outliers on loans.annual_income / loans.loan_amount, and standardizes
categorical text (loan_status, txn_type).
"""

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

LOAN_RAW_COLUMNS = [
    "id", "member_id", "loan_amnt", "funded_amnt", "term", "int_rate",
    "installment", "grade", "sub_grade", "emp_length", "home_ownership",
    "annual_inc", "verification_status", "issue_d", "loan_status", "purpose",
    "dti", "delinq_2yrs", "fico_range_low", "fico_range_high", "open_acc",
    "total_acc", "revol_util", "addr_state",
]

LOAN_RENAME = {
    "id": "loan_id",
    "loan_amnt": "loan_amount",
    "funded_amnt": "funded_amount",
    "int_rate": "interest_rate",
    "emp_length": "employment_length",
    "annual_inc": "annual_income",
    "issue_d": "issue_date",
    "open_acc": "open_accounts",
    "total_acc": "total_accounts",
    "addr_state": "state",
}

LOAN_SCHEMA_COLUMNS = [
    "loan_id", "member_id", "loan_amount", "funded_amount", "term_months",
    "interest_rate", "installment", "grade", "sub_grade", "employment_length",
    "home_ownership", "annual_income", "verification_status", "issue_date",
    "loan_status", "purpose", "dti", "delinq_2yrs", "fico_range_low",
    "fico_range_high", "open_accounts", "total_accounts", "revol_util", "state",
]

LOAN_NULLABLE_INT_COLUMNS = [
    "member_id", "term_months", "delinq_2yrs", "fico_range_low",
    "fico_range_high", "open_accounts", "total_accounts",
]

TXN_RENAME = {
    "type": "txn_type",
    "nameOrig": "sender_id",
    "oldbalanceOrg": "sender_bal_before",
    "newbalanceOrig": "sender_bal_after",
    "nameDest": "receiver_id",
    "oldbalanceDest": "receiver_bal_before",
    "newbalanceDest": "receiver_bal_after",
    "isFraud": "is_fraud",
    "isFlaggedFraud": "is_flagged_rule",
}

TXN_SCHEMA_COLUMNS = [
    "step", "txn_type", "amount", "sender_id", "sender_bal_before",
    "sender_bal_after", "receiver_id", "receiver_bal_before",
    "receiver_bal_after", "is_fraud", "is_flagged_rule",
]

STOCK_RENAME = {
    "Date": "trade_date",
    "Open": "open_price",
    "High": "high_price",
    "Low": "low_price",
    "Close": "close_price",
    "Adj Close": "adj_close",
    "Volume": "volume",
}

STOCK_SCHEMA_COLUMNS = [
    "ticker", "trade_date", "open_price", "high_price", "low_price",
    "close_price", "adj_close", "volume",
]


def parse_percent(series: pd.Series) -> pd.Series:
    """Coerce a numeric or '12.3%'-style string column to float."""
    if series.dtype == object:
        series = series.astype(str).str.strip().str.rstrip("%")
    return pd.to_numeric(series, errors="coerce")


def parse_term_months(series: pd.Series) -> pd.Series:
    """' 36 months' -> 36"""
    return pd.to_numeric(series.astype(str).str.extract(r"(\d+)")[0], errors="coerce")


def standardize_categorical(series: pd.Series) -> pd.Series:
    """Strip whitespace and collapse internal whitespace runs."""
    return series.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Cap outliers to the [lower, upper] quantile range."""
    lo, hi = series.quantile([lower, upper])
    return series.clip(lower=lo, upper=hi)


def clean_loans(df: pd.DataFrame) -> pd.DataFrame:
    """df must contain at least LOAN_RAW_COLUMNS (see download_data.py / usecols)."""
    df = df[LOAN_RAW_COLUMNS].rename(columns=LOAN_RENAME).copy()

    df["loan_id"] = pd.to_numeric(df["loan_id"], errors="coerce")
    df["term_months"] = parse_term_months(df["term"])
    df["interest_rate"] = parse_percent(df["interest_rate"])
    df["revol_util"] = parse_percent(df["revol_util"])
    df["issue_date"] = pd.to_datetime(df["issue_date"], format="%b-%Y", errors="coerce")
    for col in ["loan_amount", "funded_amount", "installment", "annual_income", "dti",
                "delinq_2yrs", "fico_range_low", "fico_range_high", "open_accounts",
                "total_accounts"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # drop rows missing fields essential to identity / core analysis (e.g. footer
    # summary rows like "Total amount funded in policy code 1: ...")
    df = df.dropna(subset=["loan_id", "term_months", "issue_date", "loan_status", "grade"])
    df["loan_id"] = df["loan_id"].astype("int64")
    df = df.drop_duplicates(subset="loan_id", keep="first")

    median_impute_cols = [
        "annual_income", "dti", "revol_util", "installment", "funded_amount",
        "interest_rate", "fico_range_low", "fico_range_high",
        "open_accounts", "total_accounts",
    ]
    for col in median_impute_cols:
        df[col] = df[col].fillna(df[col].median())
    df["delinq_2yrs"] = df["delinq_2yrs"].fillna(0)
    df["employment_length"] = df["employment_length"].fillna("Unknown")
    for col in ["home_ownership", "verification_status", "purpose", "state"]:
        df[col] = df[col].fillna("Unknown")

    # "Does not meet the credit policy. Status:Fully Paid" -> "Fully Paid": these are
    # loans under a retired credit policy but the trailing status is still the true
    # outcome; strip the prefix so it fits VARCHAR(30) and matches downstream SQL
    # filters on the canonical status strings.
    df["loan_status"] = standardize_categorical(df["loan_status"]).str.replace(
        r"^Does not meet the credit policy\.\s*Status:\s*", "", regex=True
    )
    df["purpose"] = standardize_categorical(df["purpose"])
    df["home_ownership"] = standardize_categorical(df["home_ownership"])
    df["verification_status"] = standardize_categorical(df["verification_status"])
    df["employment_length"] = standardize_categorical(df["employment_length"])
    df["grade"] = standardize_categorical(df["grade"]).str.upper().str[:1]
    df["sub_grade"] = standardize_categorical(df["sub_grade"]).str.upper()
    df["state"] = standardize_categorical(df["state"]).str.upper().str[:2]

    df["annual_income"] = winsorize(df["annual_income"])
    df["loan_amount"] = winsorize(df["loan_amount"])
    df["dti"] = winsorize(df["dti"])

    for col in LOAN_NULLABLE_INT_COLUMNS:
        df[col] = df[col].round().astype("Int64")
    df["issue_date"] = df["issue_date"].dt.date

    return df[LOAN_SCHEMA_COLUMNS].reset_index(drop=True)


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=TXN_RENAME).copy()
    df = df.drop_duplicates()

    numeric_cols = ["step", "amount", "sender_bal_before", "sender_bal_after",
                     "receiver_bal_before", "receiver_bal_after", "is_fraud"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["step", "amount", "sender_id", "receiver_id"])

    df["txn_type"] = standardize_categorical(df["txn_type"]).str.upper()
    df["sender_id"] = standardize_categorical(df["sender_id"])
    df["receiver_id"] = standardize_categorical(df["receiver_id"])

    df["step"] = df["step"].astype("int64")
    df["is_fraud"] = df["is_fraud"].astype("int64")
    # is_flagged_rule is populated later by the rule engine (fraud_detection.py)
    df["is_flagged_rule"] = pd.array([pd.NA] * len(df), dtype="Int64")

    return df[TXN_SCHEMA_COLUMNS].reset_index(drop=True)


def clean_stock_prices(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=STOCK_RENAME).copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
    df["ticker"] = standardize_categorical(df["ticker"]).str.upper()

    for col in ["open_price", "high_price", "low_price", "close_price", "adj_close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = df["volume"].round().astype("Int64")

    df = df.dropna(subset=["ticker", "trade_date", "close_price"])
    df = df.drop_duplicates(subset=["ticker", "trade_date"], keep="first")
    df = df.sort_values(["ticker", "trade_date"]).reset_index(drop=True)

    return df[STOCK_SCHEMA_COLUMNS]


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Cleaning LendingClub loans ...")
    raw_loans = pd.read_csv(RAW_DIR / "lending_club_accepted.csv",
                             usecols=LOAN_RAW_COLUMNS, low_memory=False)
    loans = clean_loans(raw_loans)
    loans.to_parquet(PROCESSED_DIR / "loans.parquet", index=False)
    print(f"  {len(loans):,} rows -> {PROCESSED_DIR / 'loans.parquet'}")

    print("Cleaning PaySim transactions ...")
    raw_txns = pd.read_csv(RAW_DIR / "paysim.csv")
    txns = clean_transactions(raw_txns)
    txns.to_parquet(PROCESSED_DIR / "transactions.parquet", index=False)
    print(f"  {len(txns):,} rows -> {PROCESSED_DIR / 'transactions.parquet'}")

    print("Cleaning Nifty 50 prices ...")
    raw_prices = pd.read_csv(RAW_DIR / "nifty50_prices.csv")
    prices = clean_stock_prices(raw_prices)
    prices.to_parquet(PROCESSED_DIR / "stock_prices.parquet", index=False)
    print(f"  {len(prices):,} rows -> {PROCESSED_DIR / 'stock_prices.parquet'}")


if __name__ == "__main__":
    main()
