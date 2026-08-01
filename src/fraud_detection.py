"""Rule-based flags + Isolation Forest anomaly scoring for fraud.

Rule engine: Section 4 Q5's balance-drain signature (sender account emptied in
a single TRANSFER/CASH_OUT), written back to finsight.transactions.is_flagged_rule.
Isolation Forest: unsupervised anomaly scoring over every transaction, evaluated
against the same is_fraud ground truth to see what it catches beyond the rule.
Both, plus anomaly_score/is_flagged_iforest, are written back to finsight.transactions
so a BI tool can query them directly instead of only reading them from the notebook.
"""

import io

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, precision_score, recall_score
from sqlalchemy import text

RANDOM_STATE = 42

# Fraud in PaySim only ever occurs on these two types (see notebooks/02_eda_fraud.ipynb).
RULE_TXN_TYPES = ("TRANSFER", "CASH_OUT")

RULE_SQL_CASE = """
    CASE
        WHEN sender_bal_before > 0
             AND sender_bal_after = 0
             AND amount = sender_bal_before
             AND txn_type IN ('TRANSFER','CASH_OUT')
        THEN 1 ELSE 0
    END
"""

# Raw balance columns + engineered deltas/errors passed to Isolation Forest,
# before txn_type one-hot encoding is appended.
BASE_FEATURE_COLUMNS = [
    "amount", "sender_bal_before", "sender_bal_after",
    "receiver_bal_before", "receiver_bal_after",
    "sender_balance_delta", "sender_balance_error",
    "receiver_balance_delta", "receiver_balance_error",
]


def apply_rule_flag(df: pd.DataFrame) -> pd.Series:
    """Section 4 Q5 rule, vectorized: sender account emptied in a single
    TRANSFER/CASH_OUT (amount == sender_bal_before, sender_bal_after == 0).
    """
    flagged = (
        (df["sender_bal_before"] > 0)
        & (df["sender_bal_after"] == 0)
        & (df["amount"] == df["sender_bal_before"])
        & (df["txn_type"].isin(RULE_TXN_TYPES))
    )
    return flagged.astype(int)


def write_rule_flags(engine) -> int:
    """Run the Q5 rule as a single SQL UPDATE against every row of
    finsight.transactions, writing 1/0 into is_flagged_rule. Returns rows updated.
    """
    with engine.begin() as conn:
        result = conn.execute(text(f"UPDATE finsight.transactions SET is_flagged_rule = {RULE_SQL_CASE}"))
        return result.rowcount


def engineer_anomaly_features(df: pd.DataFrame) -> pd.DataFrame:
    """Balance-delta / balance-error features + one-hot txn_type, for Isolation Forest.

    The *_error columns are the classic PaySim trick: the discrepancy between the
    balance change a row actually records and what a consistent ledger would show
    (e.g. sender_balance_error = sender_bal_after - (sender_bal_before - amount)).
    Raw balances alone are weak signal here because PaySim merchant destinations
    (CASH_IN/PAYMENT counterparties) always carry 0/0 balances regardless of
    transaction size, so the *_delta/*_error terms carry most of the information.
    """
    df = df.copy()
    df["sender_balance_delta"] = df["sender_bal_before"] - df["sender_bal_after"]
    df["sender_balance_error"] = df["sender_bal_after"] - (df["sender_bal_before"] - df["amount"])
    df["receiver_balance_delta"] = df["receiver_bal_after"] - df["receiver_bal_before"]
    df["receiver_balance_error"] = df["receiver_bal_after"] - (df["receiver_bal_before"] + df["amount"])

    return pd.get_dummies(df[BASE_FEATURE_COLUMNS + ["txn_type"]], columns=["txn_type"])


def train_isolation_forest(X: pd.DataFrame, contamination: float) -> IsolationForest:
    """Fit IsolationForest with a fixed random_state.

    Reproducibility warning: IsolationForest bootstraps each tree by X's *positional*
    row index (0..n-1), not by any ID column - a fixed random_state only reproduces the
    same result if the caller's row order is also fixed. Postgres does not guarantee row
    order for an unordered SELECT, and it silently changed here once (between two runs of
    notebooks/05_fraud_anomaly_detection.ipynb) after write_iforest_scores()'s own bulk
    UPDATE rewrote finsight.transactions' physical row layout - producing a materially
    different model from the same seed and the same underlying data. Always pull X's
    source rows with an explicit ORDER BY (e.g. `ORDER BY txn_id`) before calling this;
    verified deterministic (bit-identical anomaly scores across two fits) once row order
    is fixed - see reports/model_performance_report.md Section 2 for the full incident.
    """
    model = IsolationForest(
        n_estimators=200, contamination=contamination,
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    model.fit(X)
    return model


def score_transactions(model: IsolationForest, X: pd.DataFrame) -> pd.DataFrame:
    """Anomaly score (higher = more anomalous) and binary flag for every row of X."""
    normality = model.decision_function(X)  # sklearn convention: higher = more normal
    pred = model.predict(X)  # -1 = anomaly, 1 = normal
    return pd.DataFrame({
        "anomaly_score": -normality,
        "is_flagged_iforest": (pred == -1).astype(int),
    }, index=X.index)


def precision_recall(y_true, y_pred) -> dict:
    """Precision/recall/confusion matrix for a binary flag column vs ground truth."""
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


def write_iforest_scores(engine, scored: pd.DataFrame) -> int:
    """Bulk-writes anomaly_score/is_flagged_iforest back to finsight.transactions.

    `scored` must have txn_id, anomaly_score, is_flagged_iforest columns - i.e. the
    txn_df produced by notebooks/05_fraud_anomaly_detection.ipynb Section 4
    (score_transactions() output joined back onto the txn_id it was scored from).

    Loads into a TEMP TABLE via COPY, then a single UPDATE...FROM join - the same
    fast-path reasoning as db_connect.bulk_load: a per-row UPDATE over 6.36M
    transactions would be far too slow, and TEMP TABLE + COPY + join is the
    standard way to bulk-update (rather than bulk-insert) at this scale.
    """
    buf = io.StringIO()
    scored[["txn_id", "anomaly_score", "is_flagged_iforest"]].to_csv(buf, index=False, header=False)
    buf.seek(0)
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cur.execute("""
                CREATE TEMP TABLE _iforest_scores (
                    txn_id BIGINT, anomaly_score NUMERIC, is_flagged_iforest SMALLINT
                ) ON COMMIT DROP
            """)
            cur.copy_expert(
                "COPY _iforest_scores (txn_id, anomaly_score, is_flagged_iforest) "
                "FROM STDIN WITH (FORMAT csv)",
                buf,
            )
            cur.execute("""
                UPDATE finsight.transactions t
                SET anomaly_score = s.anomaly_score,
                    is_flagged_iforest = s.is_flagged_iforest
                FROM _iforest_scores s
                WHERE t.txn_id = s.txn_id
            """)
            updated = cur.rowcount
        raw_conn.commit()
    finally:
        raw_conn.close()
    return updated
