"""Feature engineering + modeling for LendingClub default prediction.

Population: closed loans only (Fully Paid / Charged Off / Default). Loans still
Current/Late/In Grace Period have no final outcome yet and are excluded rather
than treated as censored - training on them would mislabel not-yet-defaulted
loans as "good".

Target: 1 = Charged Off or Default, 0 = Fully Paid.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

CLOSED_LOAN_STATUSES = ("Fully Paid", "Charged Off", "Default")
DEFAULT_STATUSES = ("Charged Off", "Default")

NUMERIC_FEATURES = [
    "loan_amount", "term_months", "annual_income", "dti",
    "delinq_2yrs", "open_accounts", "total_accounts", "credit_utilization_ratio",
]
CATEGORICAL_FEATURES = [
    "dti_bucket", "fico_band", "employment_length",
    "home_ownership", "verification_status", "purpose",
]

# Features intentionally excluded as pricing-decision leakage - see notebook /
# report for the empirical check that motivated this. grade/sub_grade and
# interest_rate are LendingClub's own risk assessment output (not available at
# the point an independent underwriting model would need to score the loan),
# and installment is a deterministic function of loan_amount/term/interest_rate
# so it re-introduces interest_rate through the back door if included.
LEAKAGE_FEATURES = ["grade", "sub_grade", "interest_rate", "installment"]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add dti_bucket, fico_band, and credit_utilization_ratio to a loans dataframe."""
    df = df.copy()

    df["dti_bucket"] = pd.cut(
        df["dti"], bins=[-np.inf, 10, 20, 30, 40, np.inf],
        labels=["0-10", "10-20", "20-30", "30-40", "40+"],
    )

    # "<" is disallowed in XGBoost feature names, so "under 660" rather than "(<660)".
    df["fico_band"] = pd.cut(
        df["fico_range_low"], bins=[-np.inf, 659, 719, np.inf],
        labels=["Subprime (under 660)", "Near-Prime (660-719)", "Prime (720+)"],
    )

    # revol_util is a percentage (can exceed 100 for over-limit accounts) -> rescale to a ratio.
    df["credit_utilization_ratio"] = df["revol_util"] / 100.0

    return df


def make_target(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to closed loans and add a binary `default` target column."""
    df = df[df["loan_status"].isin(CLOSED_LOAN_STATUSES)].copy()
    df["default"] = df["loan_status"].isin(DEFAULT_STATUSES).astype(int)
    return df


def _sanitize_column_names(columns) -> list:
    """XGBoost rejects feature names containing '[', ']', or '<' (e.g. LendingClub's
    "< 1 year" employment_length category) - swap in safe equivalents."""
    return [str(c).replace("<", "under").replace("[", "(").replace("]", ")") for c in columns]


def build_feature_matrix(df: pd.DataFrame, numeric_cols=None, categorical_cols=None):
    """One-hot encode categoricals + return the encoded column list for reuse on new data."""
    numeric_cols = numeric_cols or NUMERIC_FEATURES
    categorical_cols = categorical_cols or CATEGORICAL_FEATURES
    X = pd.get_dummies(df[numeric_cols + categorical_cols], columns=categorical_cols, drop_first=True)
    X.columns = _sanitize_column_names(X.columns)
    return X


def align_columns(X: pd.DataFrame, reference_columns: list) -> pd.DataFrame:
    """Align a one-hot encoded frame (e.g. test set) to the training set's columns."""
    return X.reindex(columns=reference_columns, fill_value=0)


def scale_numeric(X_train: pd.DataFrame, X_test: pd.DataFrame, numeric_cols=None):
    """Fit a StandardScaler on train, apply to both. Returns scaled copies + the fitted scaler."""
    numeric_cols = numeric_cols or NUMERIC_FEATURES
    scaler = StandardScaler()
    X_train = X_train.copy()
    X_test = X_test.copy()
    X_train[numeric_cols] = scaler.fit_transform(X_train[numeric_cols])
    X_test[numeric_cols] = scaler.transform(X_test[numeric_cols])
    return X_train, X_test, scaler


def train_logistic_regression(X_train, y_train) -> LogisticRegression:
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train, y_train)
    return model


def train_xgboost(X_train, y_train) -> XGBClassifier:
    model = XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="logloss", random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_at_threshold(y_true, y_proba, threshold: float = 0.5) -> dict:
    """AUC-ROC, precision/recall/F1, and confusion matrix at a given probability threshold."""
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "threshold": threshold,
        "auc_roc": roc_auc_score(y_true, y_proba),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def precision_recall_by_threshold(y_true, y_proba) -> pd.DataFrame:
    """Precision/recall/F1/F2 across every threshold on the PR curve."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_proba)
    precision, recall = precision[:-1], recall[:-1]  # last point has no corresponding threshold
    f1 = np.where((precision + recall) > 0, 2 * precision * recall / (precision + recall + 1e-12), 0)
    f2 = np.where((precision + recall) > 0, 5 * precision * recall / (4 * precision + recall + 1e-12), 0)
    return pd.DataFrame({"threshold": thresholds, "precision": precision, "recall": recall, "f1": f1, "f2": f2})


def select_recall_favoring_threshold(y_true, y_proba, beta: float = 2.0) -> float:
    """Pick the threshold that maximizes F-beta (beta=2 weights recall 4x precision).

    Missing an actual defaulter (false negative) costs the lender the full
    remaining principal; a false positive only costs a marginally-qualified
    applicant a rejection (lost interest income, not lost principal). F2
    operationalizes "favor recall" as a single reproducible number instead of
    an eyeballed cutoff - see Section 9 Q3 of the project blueprint for the
    business framing this mirrors.
    """
    curve = precision_recall_by_threshold(y_true, y_proba)
    best_row = curve.loc[curve["f2"].idxmax()]
    return float(best_row["threshold"])


def threshold_for_flagged_rate(y_proba, flagged_rate: float) -> float:
    """Score threshold that flags approximately the riskiest `flagged_rate` fraction
    of the population (e.g. 0.15 -> flag the riskiest 15% by predicted probability).
    """
    return float(np.quantile(y_proba, 1 - flagged_rate))


def threshold_tradeoff_table(y_true, y_proba, flagged_rates=(0.15, 0.25, 0.35)) -> pd.DataFrame:
    """Precision/recall/flagged-count at thresholds calibrated to specific review-queue
    capacities, so a business owner can pick a deployable cutoff by "how many loans can
    we actually review" rather than by a pure metric-optimal (and possibly unusable)
    threshold like the F2-maximizing one from select_recall_favoring_threshold().
    """
    rows = []
    n = len(y_true)
    for target_rate in flagged_rates:
        threshold = threshold_for_flagged_rate(y_proba, target_rate)
        metrics = evaluate_at_threshold(y_true, y_proba, threshold)
        cm = metrics["confusion_matrix"]
        flagged = cm["tp"] + cm["fp"]
        rows.append({
            "target_flagged_rate": target_rate,
            "threshold": threshold,
            "actual_flagged_rate": flagged / n,
            "flagged_count": flagged,
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "defaults_caught": cm["tp"],
            "defaults_missed": cm["fn"],
        })
    return pd.DataFrame(rows)
