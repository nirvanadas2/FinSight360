"""Tests for src/data_cleaning.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

import data_cleaning as dc


def _valid_loan_row(loan_id, **overrides) -> dict:
    """A minimal but fully-valid raw LendingClub row (all LOAN_RAW_COLUMNS populated)
    that survives clean_loans()'s required-field dropna - individual tests override
    just the field(s) they care about.
    """
    row = {
        "id": loan_id,
        "member_id": 12345,
        "loan_amnt": 10000,
        "funded_amnt": 10000,
        "term": " 36 months",
        "int_rate": 13.5,
        "installment": 300.0,
        "grade": "B",
        "sub_grade": "B3",
        "emp_length": "5 years",
        "home_ownership": "RENT",
        "annual_inc": 60000,
        "verification_status": "Verified",
        "issue_d": "Jan-2015",
        "loan_status": "Fully Paid",
        "purpose": "debt_consolidation",
        "dti": 15.0,
        "delinq_2yrs": 0,
        "fico_range_low": 700,
        "fico_range_high": 704,
        "open_acc": 8,
        "total_acc": 20,
        "revol_util": 45.0,
        "addr_state": "CA",
    }
    row.update(overrides)
    return row


def test_winsorize_caps_at_expected_percentile():
    """winsorize() (the mechanism clean_loans uses for dti/annual_income/loan_amount)
    should clip to exactly the requested [lower, upper] quantile bounds, and leave
    values strictly inside that range untouched.
    """
    series = pd.Series(range(1, 101))  # 1..100

    result = dc.winsorize(series, lower=0.01, upper=0.99)

    assert result.min() == series.quantile(0.01)
    assert result.max() == series.quantile(0.99)
    assert result.iloc[50] == series.iloc[50]  # untouched mid-range value


def test_clean_loans_strips_credit_policy_prefix():
    """LendingClub's 'Does not meet the credit policy. Status:X' rows should have the
    prefix stripped down to the true outcome status X, so they still match the
    canonical status strings every downstream WHERE loan_status IN (...) filter uses -
    see the loan_status truncation bug in README.md.
    """
    raw = pd.DataFrame([
        _valid_loan_row(1, loan_status="Does not meet the credit policy. Status:Fully Paid"),
        _valid_loan_row(2, loan_status="Charged Off"),
    ])

    cleaned = dc.clean_loans(raw)
    statuses = cleaned.set_index("loan_id")["loan_status"]

    assert statuses.loc[1] == "Fully Paid"
    assert statuses.loc[2] == "Charged Off"


def test_clean_loans_drops_duplicate_loan_ids():
    """Duplicate loan_id rows should be deduped (keep first), never double-counted."""
    raw = pd.DataFrame([
        _valid_loan_row(5, loan_amnt=10000),
        _valid_loan_row(5, loan_amnt=99999),  # duplicate loan_id, different payload
        _valid_loan_row(6),
    ])

    cleaned = dc.clean_loans(raw)

    assert len(cleaned) == 2
    assert sorted(cleaned["loan_id"].tolist()) == [5, 6]
    assert cleaned.set_index("loan_id").loc[5, "loan_amount"] == 10000  # first occurrence kept


def test_clean_loans_drops_rows_missing_required_fields():
    """Rows missing an identity/core-analysis field (grade, in this case) should be
    dropped rather than imputed - e.g. LendingClub's footer summary rows.
    """
    raw = pd.DataFrame([
        _valid_loan_row(10),
        _valid_loan_row(11, grade=None),
    ])

    cleaned = dc.clean_loans(raw)

    assert cleaned["loan_id"].tolist() == [10]
