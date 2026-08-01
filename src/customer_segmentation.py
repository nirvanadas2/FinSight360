"""RFM feature build + K-Means clustering for customer segmentation.

RFM is built by aggregating finsight.transactions by sender_id: Frequency =
number of transactions sent, Monetary = total amount sent, Recency = hours
since a sender's last transaction, measured back from the maximum `step`
observed anywhere in the dataset.

PaySim's `step` is hours-since-simulation-start (1-743, ~31 simulated days),
not a real calendar date - Recency here is *simulated-time* recency relative
to the dataset's own end point, not real customer recency, and shouldn't be
read as "days since a real customer's last real transaction". signup_date /
last_txn_date on finsight.customers are populated by anchoring `step` to the
same arbitrary TIMESTAMP '2023-01-01' base already used in sql/06_kpi_views.sql,
purely so the schema's DATE columns have a value - that anchor is not a real
signup date. Clustering itself runs on `step`-derived Recency directly, never
on the anchored calendar dates.

A second, more consequential data characteristic: PaySim's nameOrig sender IDs
are almost all one-shot - 6,344,009 of 6,353,307 distinct senders (99.85%)
appear exactly once in the transaction log, and none appear more than 3 times.
Frequency is therefore near-constant across the population; RFM segmentation
here is effectively Recency/Monetary-driven for the vast majority of
customers, with a small distinguishable tail of repeat senders. See notebook
Section 2 for the full breakdown.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from db_connect import bulk_load

RANDOM_STATE = 42
STEP_ANCHOR = pd.Timestamp("2023-01-01")  # same arbitrary anchor as sql/06_kpi_views.sql

CUSTOMER_SCHEMA_COLUMNS = [
    "customer_id", "signup_date", "segment", "total_txn_count",
    "total_txn_value", "avg_txn_value", "last_txn_date", "risk_score",
]


def build_rfm(engine) -> pd.DataFrame:
    """One row per sender_id: Frequency/Monetary from a single GROUP BY, Recency
    derived from `step` relative to the dataset's max step.
    """
    df = pd.read_sql("""
        SELECT sender_id AS customer_id,
               COUNT(*) AS frequency,
               SUM(amount) AS monetary,
               ROUND(AVG(amount), 2) AS avg_txn_value,
               MIN(step) AS first_step,
               MAX(step) AS last_step
        FROM finsight.transactions
        GROUP BY sender_id;
    """, engine)

    max_step = pd.read_sql("SELECT MAX(step) AS mx FROM finsight.transactions", engine)["mx"].iloc[0]
    df["recency_hours"] = max_step - df["last_step"]
    df["signup_date"] = (STEP_ANCHOR + pd.to_timedelta(df["first_step"], unit="h")).dt.date
    df["last_txn_date"] = (STEP_ANCHOR + pd.to_timedelta(df["last_step"], unit="h")).dt.date
    df["total_txn_count"] = df["frequency"]
    df["total_txn_value"] = df["monetary"]
    return df


def rfm_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """log1p + standardize R/F/M into a clustering-ready matrix.

    log1p on frequency/monetary tames right-skew (standard RFM practice) and,
    specifically for this dataset, keeps the rare repeat-sender tail (2-3
    transactions vs. the modal 1) from becoming an extreme outlier once
    standardized: frequency's raw variance is so small (99.85% of senders sit
    at frequency=1) that a handful of freq=2/3 senders would otherwise land
    many standard deviations out and dominate cluster assignment.
    """
    X = pd.DataFrame({
        "recency_hours": df["recency_hours"].astype(float),
        "frequency_log": np.log1p(df["frequency"]),
        "monetary_log": np.log1p(df["monetary"]),
    }, index=df.index)
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns, index=X.index)
    return X_scaled, scaler


def elbow_silhouette_curve(X_scaled: pd.DataFrame, k_range=range(2, 11),
                            sample_size: int = 20_000, silhouette_sample_size: int = 5_000,
                            random_state: int = RANDOM_STATE) -> pd.DataFrame:
    """Inertia (elbow) + silhouette score per k, on a fixed seeded sample.

    Silhouette's pairwise-distance cost makes it infeasible on the full
    multi-million-row population; a representative sample is standard
    practice for k-selection regardless.
    """
    sample = X_scaled.sample(n=min(sample_size, len(X_scaled)), random_state=random_state)
    rows = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = km.fit_predict(sample)
        rows.append({
            "k": k,
            "inertia": km.inertia_,
            "silhouette": silhouette_score(
                sample, labels, sample_size=min(silhouette_sample_size, len(sample)),
                random_state=random_state,
            ),
        })
    return pd.DataFrame(rows)


def fit_kmeans(X_scaled: pd.DataFrame, k: int, random_state: int = RANDOM_STATE) -> KMeans:
    model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    model.fit(X_scaled)
    return model


def profile_clusters(df: pd.DataFrame, cluster_col: str = "cluster") -> pd.DataFrame:
    """Raw (untransformed) mean recency/frequency/monetary per cluster, plus size."""
    return df.groupby(cluster_col).agg(
        n_customers=("customer_id", "count"),
        avg_recency_hours=("recency_hours", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
    ).reset_index()


def label_clusters(profile: pd.DataFrame, cluster_col: str = "cluster") -> dict:
    """Map cluster -> business-readable label, split into two genuinely different
    naming regimes depending on whether a cluster shows repeat-sender behavior.

    A cluster counts as repeat-sender behavior only if its average frequency is
    meaningfully above the one-shot baseline (not a relative rank/median split:
    with 99.85% of senders at frequency=1, most clusters tie on frequency, and a
    "top half" rule would arbitrarily call one of several tied, effectively-
    identical clusters "frequent" depending on row order alone).

    Repeat clusters get RFM/loyalty-style language ("High-Value Loyal") - that
    framing is earned there, since there's an actual repeat-transaction pattern
    to describe. One-time clusters (frequency ~ 1, no second transaction to
    compare against) do NOT get trajectory language like "Lapsing"/"Dormant"/
    "New" - a single transaction has no trajectory, and simulated-time Recency
    differences between one-time senders don't mean what "lapsing" implies for a
    real repeat customer. One-time clusters are labeled purely on transaction
    size (avg_monetary), tiered by relative rank among the one-time clusters.

    Labels are kept to <=20 chars for finsight.customers.segment VARCHAR(20).
    """
    REPEAT_FREQUENCY_THRESHOLD = 1.2
    is_repeat = profile["avg_frequency"] > REPEAT_FREQUENCY_THRESHOLD
    repeat_profile = profile[is_repeat]
    one_time_profile = profile[~is_repeat]

    labels = {}

    repeat_monetary_median = repeat_profile["avg_monetary"].median()
    for i in repeat_profile.index:
        high_value = profile.loc[i, "avg_monetary"] >= repeat_monetary_median
        label = "High-Value Loyal" if high_value else "Frequent Small-Txn"
        labels[profile.loc[i, cluster_col]] = label

    n_one_time = len(one_time_profile)
    money_rank = one_time_profile["avg_monetary"].rank(method="min", ascending=False)
    for i in one_time_profile.index:
        rank = money_rank[i]
        if rank <= n_one_time / 3:
            label = "High-Value One-Time"
        elif rank > 2 * n_one_time / 3:
            label = "Low-Value One-Time"
        else:
            label = "Standard One-Time"
        labels[profile.loc[i, cluster_col]] = label

    assert all(len(v) <= 20 for v in labels.values()), "segment label exceeds VARCHAR(20)"
    return labels


def write_customers(engine, df: pd.DataFrame) -> int:
    """TRUNCATE + COPY into finsight.customers (bulk_load, same fast path as
    db_connect's loan/transaction/stock loaders - a row-by-row UPSERT over
    6M+ customers would be far too slow).
    """
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE finsight.customers"))
    return bulk_load(engine, df, "finsight.customers", CUSTOMER_SCHEMA_COLUMNS)


# risk_score (0-100, higher = more disengagement risk): a percentile-rank blend of the same
# three RFM fields already persisted on finsight.customers, run as a single SQL UPDATE rather
# than round-tripping 6.35M rows through pandas. Weighted 50% Recency / 25% Frequency / 25%
# Monetary - Frequency gets a reduced weight deliberately, because 99.85% of customers sit at
# Frequency=1 (see notebooks/06_customer_segmentation_rfm.ipynb Section 2), so it barely
# differentiates anyone; this is a lighter-weight, dashboard-facing heuristic derived from the
# already-computed RFM fields, not a re-run of the K-Means model or a validated churn score -
# treat it as a rough ranking signal, not a calibrated probability.
RISK_SCORE_SQL = """
    UPDATE finsight.customers c
    SET risk_score = sub.risk_score
    FROM (
        SELECT customer_id,
               ROUND((100 * (
                   0.50 * PERCENT_RANK() OVER (ORDER BY last_txn_date DESC)
                   + 0.25 * PERCENT_RANK() OVER (ORDER BY total_txn_count DESC)
                   + 0.25 * PERCENT_RANK() OVER (ORDER BY total_txn_value DESC)
               ))::numeric, 2) AS risk_score
        FROM finsight.customers
    ) AS sub
    WHERE c.customer_id = sub.customer_id;
"""


def write_risk_scores(engine) -> int:
    """Backfills finsight.customers.risk_score for every row via RISK_SCORE_SQL.
    Requires segment/RFM fields to already be populated (i.e. run after write_customers()).
    """
    with engine.begin() as conn:
        result = conn.execute(text(RISK_SCORE_SQL))
        return result.rowcount
