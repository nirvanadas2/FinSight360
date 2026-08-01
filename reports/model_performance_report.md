# Model Performance Report — Credit Default Prediction

**Notebook:** `notebooks/04_model_credit_default.ipynb` | **Module:** `src/credit_risk_model.py`
**Data source:** PostgreSQL `finsight.loans` (via `src/db_connect.py`), post-cleaning (see `src/data_cleaning.py`)

## 1. Population & Target Definition

The model predicts **loan default** using a binary target derived from `loan_status`:

- **Target population**: closed loans only — `Fully Paid`, `Charged Off`, `Default`. Loans still `Current`,
  `Late (16-30/31-120 days)`, or `In Grace Period` have no final outcome yet and are excluded — training on
  them would mean labeling not-yet-defaulted active loans as "good," which they may not turn out to be.
- **Target**: `1` if `Charged Off` or `Default`, else `0` (`Fully Paid`).

| Metric | Value |
|---|---|
| Total loans in `finsight.loans` | 2,260,668 |
| Closed loans (modeling population) | 1,348,099 (59.6% of all loans) |
| Default rate within closed loans | 19.98% |
| Modeling sample (deterministic — ordered by `MD5(loan_id)`, reproducible across re-runs) | 300,000 loans |
| Train / test split | 240,000 / 60,000 (80/20, stratified), both 20.05% default |

## 2. Feature Leakage Check: grade / sub_grade / interest_rate / installment

**Concern**: `grade`/`sub_grade` are LendingClub's own risk assessment, assigned from essentially the same
signals (FICO, DTI, income, credit history) the model is trying to learn independently from. `interest_rate`
is priced directly off `sub_grade`, and `installment` is a deterministic function of `loan_amount`,
`term_months`, and `interest_rate` — so it would smuggle `interest_rate` back in even if `interest_rate`
itself were dropped.

**Empirical check performed:**

- Correlation between `grade` (ordinal A=1..G=7) and `interest_rate`: **r = 0.954** (R² ≈ 0.91) — grade alone
  explains ~91% of interest_rate's variance.
- Within-`sub_grade` interest_rate spread averages 14.44 points (56.2% of the portfolio-wide 25.68-point
  range) — this initially looks like sub_grade doesn't pin down rate tightly, but it's a vintage artifact:
  loans span 2007–2018, and LendingClub's own rate table drifted over that decade on top of the sub_grade
  effect. Example: sub_grade A1 alone ranges 5.31%–7.37% (a 2.06-point spread), much tighter than the
  portfolio-wide range.
- **Decision: exclude `grade`, `sub_grade`, `interest_rate`, and `installment`** from the feature set. An
  underwriting model should independently assess risk from raw application data; a model that sees
  LendingClub's own pricing decision (or a near-perfect proxy for it) would mostly be learning to decode
  that decision rather than doing independent risk assessment, and its apparent accuracy wouldn't hold up
  when pricing a genuinely new application.

**Post-hoc empirical confirmation** (Section 7 below): adding `grade` back into the trained model lifts
AUC-ROC from 0.6878 to 0.7117 (+0.0238) and `grade` immediately becomes the single most important feature
by a wide margin — direct evidence the exclusion was correct, not just a theoretical concern.

## 3. Feature Set

**Engineered** (`src/credit_risk_model.py::engineer_features`):
- `dti_bucket` — dti binned into 0-10 / 10-20 / 20-30 / 30-40 / 40+
- `fico_band` — fico_range_low binned into Subprime (<660) / Near-Prime (660-719) / Prime (720+)
- `credit_utilization_ratio` — `revol_util / 100`

**Included (raw)**: `loan_amount`, `term_months`, `annual_income`, `dti`, `delinq_2yrs`, `open_accounts`,
`total_accounts`, `employment_length`, `home_ownership`, `verification_status`, `purpose`.

**Excluded (leakage)**: `grade`, `sub_grade`, `interest_rate`, `installment` (see Section 2).

**Excluded (out of scope)**: `funded_amount` (near-duplicate of `loan_amount`, r≈1.00 per the EDA
notebook), `state` (high cardinality, left for future work), loan/member identifiers.

One-hot encoding categorical features produced **45 model columns**. Numeric features were standardized
(fit on train, applied to test) before Logistic Regression; the same scaled matrix was reused for XGBoost
since tree models are scale-invariant.

## 4. Model Results @ Default 0.5 Threshold

| Model | AUC-ROC | Precision | Recall | F1 | TN | FP | FN | TP |
|---|---|---|---|---|---|---|---|---|
| Logistic Regression | 0.6821 | 0.5517 | 0.0346 | 0.0651 | 47,633 | 338 | 11,613 | 416 |
| XGBoost | 0.6878 | 0.5395 | 0.0482 | 0.0885 | 47,476 | 495 | 11,449 | 580 |

XGBoost edges out Logistic Regression on AUC-ROC and roughly doubles recall at the same threshold, but the
gap is modest — most of the predictive signal is close to linear, which is consistent with a genuinely
leakage-free feature set (no single feature dominates the way `grade` does when it's included — see
Section 7). Both models have very low recall at 0.5 by construction: neither was class-weighted, and the
whole point of Section 5 below is to fix this deliberately via threshold selection rather than by
reweighting the loss function.

## 5. Threshold Tuning: A Business Tradeoff, Not a Single "Optimal" Number

**Business framing**: a false negative (predicted safe, actually defaults) costs the lender the unpaid
principal; a false positive (predicted risky, actually would have paid) only costs a marginally-qualified
applicant a rejection. That asymmetry means recall on the default class should be weighted well above
precision — but that's not the same as saying "maximize recall regardless of what it costs to act on."

**Starting point — the pure F2-maximizing threshold** (recall weighted 4x precision, via
`select_recall_favoring_threshold()` in `src/credit_risk_model.py`): **threshold = 0.110**, precision
0.235, recall 0.919, flagging **47,098 of 60,000 test loans (78.5% of the portfolio)**. Mathematically
optimal for F2, but not something any underwriting/review team could act on — rejecting or manually
reviewing four out of five applicants isn't a deployable policy. It's reported below only as the
theoretical ceiling on recall.

**The deployable question is the reverse one**: for a review queue that can actually handle roughly
15%, 25%, or 35% of loan volume, what recall does that buy? `threshold_tradeoff_table()` calibrates the
threshold directly to each target flagged-rate (via the quantile of predicted probability) instead of
optimizing a metric and hoping the resulting flag rate happens to be practical:

| Review capacity | Threshold | Precision | Recall | Defaulters caught | Loans flagged | TN | FP | FN | TP |
|---|---|---|---|---|---|---|---|---|---|
| ~15% of portfolio | 0.317 | 0.400 | 0.300 | 3,603 of 12,029 | 9,000 | 42,574 | 5,397 | 8,426 | 3,603 |
| ~25% of portfolio | 0.258 | 0.353 | 0.440 | 5,289 of 12,029 | 15,000 | 38,260 | 9,711 | 6,740 | 5,289 |
| ~35% of portfolio | 0.219 | 0.322 | 0.562 | 6,759 of 12,029 | 21,000 | 33,730 | 14,241 | 5,270 | 6,759 |
| F2-optimal (reference only, not deployable) | 0.110 | 0.235 | 0.919 | ~11,057 of 12,029 | 47,098 | — | — | — | — |

**This is presented as a business decision, not a modeling one** — there's no universally "correct" row:

- **~15%** is the cheapest to staff but catches only 30% of defaulters — appropriate if review capacity is
  the binding constraint.
- **~35%** catches nearly twice the defaulters (56%) but roughly doubles both the review workload and the
  false-positive count relative to ~15% — appropriate if missed defaults are far more costly than review
  labor.
- **~25%** sits in between on every axis.
- The right pick depends on how many loans the underwriting/collections team can actually review per
  cycle — a staffing/capacity question that this table is meant to inform, not answer unilaterally.

## 6. SHAP Feature Importance (XGBoost)

Top 8 features by mean |SHAP value|, computed on a 2,000-row sample of the test set:

| Rank | Feature | Mean \|SHAP\| |
|---|---|---|
| 1 | `term_months` | 0.3329 |
| 2 | `fico_band_Prime (720+)` | 0.1825 |
| 3 | `dti` | 0.1469 |
| 4 | `annual_income` | 0.1465 |
| 5 | `loan_amount` | 0.1313 |
| 6 | `total_accounts` | 0.1263 |
| 7 | `open_accounts` | 0.1255 |
| 8 | `home_ownership_MORTGAGE` | 0.1026 |

`term_months` dominates by a wide margin — consistent with the well-known LendingClub pattern that
60-month loans carry structurally higher default risk than 36-month loans (longer exposure window, and
borrowers who need smaller monthly payments self-select into longer terms). No single feature comes close
to the concentration seen when `grade` is included (Section 2/7) — the leakage-free model spreads its
predictive weight across a genuinely distributed set of application-time signals rather than leaning on
one shortcut variable.

## 7. Empirical Leakage Confirmation

XGBoost retrained on the identical train/test split with `grade` added back in (ordinal-encoded A=1..G=7):

| Model | AUC-ROC |
|---|---|
| XGBoost, leakage-free (Section 2 decision) | 0.6878 |
| XGBoost, with `grade` added back in | 0.7117 |
| **Inflation from including `grade`** | **+0.0238** |

`grade_ordinal` immediately becomes the **#1 feature of 46** by XGBoost's built-in `feature_importances_`
(0.3065 — nearly 3x `term_months`, the next-highest at 0.1111). This confirms the Section 2 decision
empirically: even the coarse letter grade alone measurably inflates performance and dominates the model's
attention, exactly the leakage pattern the exclusion was meant to avoid.

## Summary

| Model | AUC-ROC | Precision @ 0.5 | Recall @ 0.5 |
|---|---|---|---|
| Logistic Regression | 0.6821 | 0.5517 | 0.0346 |
| XGBoost | 0.6878 | 0.5395 | 0.0482 |
| XGBoost + grade (leaky, reference only) | 0.7117 | — | — |

| XGBoost at review-capacity threshold | Precision | Recall |
|---|---|---|
| ~15% flagged | 0.400 | 0.300 |
| ~25% flagged | 0.353 | 0.440 |
| ~35% flagged | 0.322 | 0.562 |
| F2-optimal (78.5% flagged, reference only) | 0.235 | 0.919 |

XGBoost is the selected model. Rather than deploying a single "optimal" threshold, Section 5's tradeoff
table is the deliverable: pick the row that matches actual review-queue capacity.

---

# Model Performance Report — Fraud Detection (Rule Engine vs Isolation Forest)

**Notebook:** `notebooks/05_fraud_anomaly_detection.ipynb` | **Module:** `src/fraud_detection.py`
**Data source:** PostgreSQL `finsight.transactions` (via `src/db_connect.py`), 6,362,620 transactions, 8,213
fraudulent (0.1291%)

## 1. Rule Engine (Section 4 Q5)

`fraud_detection.write_rule_flags()` runs the Q5 balance-drain signature as a single `UPDATE` against
every row of `finsight.transactions`, writing 1/0 into `is_flagged_rule`: sender account fully emptied
(`sender_bal_before > 0`, `sender_bal_after = 0`, `amount = sender_bal_before`) on a TRANSFER or CASH_OUT
— the two transaction types fraud is confined to (`notebooks/02_eda_fraud.ipynb`).

| Metric | Value |
|---|---|
| Transactions flagged by rule | 8,008 (0.1259% of all transactions) |
| True positives | 8,008 |
| False positives | 0 |
| False negatives (fraud missed) | 205 |
| **Precision** (Q6) | **100.00%** |
| **Recall** | **97.50%** |
| F1 | 0.9874 |

Confirms the EDA finding: the balance-drain rule is essentially perfect precision, and catches all but 205
of the 8,213 fraudulent transactions — 164 TRANSFER (avg. amount ₹9.17M) and 41 CASH_OUT (avg. amount
₹134K) that don't match the exact drain signature.

## 2. Isolation Forest

**Features** (`fraud_detection.engineer_anomaly_features`): `amount`, raw sender/receiver balances,
engineered balance-delta and balance-error terms (e.g. `sender_balance_error = sender_bal_after -
(sender_bal_before - amount)`, which is ~0 for a consistent ledger entry and large otherwise), and
one-hot `txn_type` — 14 features total. Unsupervised: `is_fraud` is never used during training, only for
evaluation afterward.

**Training**: `sklearn.ensemble.IsolationForest`, `n_estimators=200`, `random_state=42`
(`fraud_detection.RANDOM_STATE`, applied everywhere sampling is involved per the Part 5 reproducibility
fix). `contamination` set to 0.001259 — the rule engine's own flagged rate — so both detectors are
compared at matched review-queue volume (8,008 transactions each) rather than one flagging a much larger
or smaller set.

**Reproducibility note**: an earlier version of this report cited different numbers here (109 TP / 91
residual caught). Root cause: `IsolationForest` bootstraps each tree by *positional* row index, not by
`txn_id`, so a fixed `random_state` alone doesn't guarantee reproducibility unless the input row order is
also fixed. The notebook's pull query originally had no `ORDER BY`, and once `anomaly_score`/
`is_flagged_iforest` were written back to `finsight.transactions` (an `UPDATE` that rewrites every row's
physical position on disk), the unordered `SELECT` silently started returning a different row order than
it had the first time — changing the model's tree-level bootstrap samples despite the unchanged seed and
unchanged underlying data. Fixed by adding `ORDER BY txn_id` to the pull query
(`notebooks/05_fraud_anomaly_detection.ipynb` Section 4) and verified deterministic: two independent fits
on the now-fixed row order produced bit-identical `anomaly_score` values and an identical flagged set. The
numbers below are from that stable, reproducible run.

### Full-population comparison

| Detector | Precision | Recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| Rule engine (Q5) | 1.0000 | 0.9750 | 0.9874 | 8,008 | 0 | 205 | 6,354,407 |
| Isolation Forest | 0.0061 | 0.0060 | 0.0060 | 49 | 7,959 | 8,164 | 6,346,448 |

At matched flagged volume, Isolation Forest is dramatically worse than the rule on the full population —
expected, since ~97.5% of fraud already matches an exact, low-noise numerical signature the rule expresses
directly, while an unsupervised model has no way to know that signature is the one that matters among all
the ways a transaction can look "anomalous."

### The real test: the 205-transaction residual the rule misses

The full-population numbers above are the wrong comparison to draw a conclusion from — they're dominated
by fraud the rule already wins on by construction. The question worth asking is narrower: **of the 205
fraud transactions that don't match the rule's exact signature, does an anomaly model catch any of them
independently?**

| Detector | Residual fraud caught | Residual recall | Precision on rule's blind spot |
|---|---|---|---|
| Rule engine | 0 / 205 | 0.00% | — |
| Isolation Forest | 38 / 205 | **18.54%** | 0.475% |

Isolation Forest catches **38 of the 205** fraud transactions the rule's exact signature misses — a real,
independent signal (median anomaly score for residual fraud is -0.0202 vs. -0.3312 for an equal-sized
random legitimate sample, confirming genuine separation, not noise, even though the effect is weaker than
the earlier miscalculated run suggested). But the cost is steep: of the 7,997 transactions it flags beyond
what the rule already flags, only 0.475% (38) are actually fraud — a ~99.5% false-positive rate on those
incremental flags. Whether that trade is worth it is a review-queue capacity question, the same framing as
Section 5 of the credit risk report above: an 18.5% lift in catching the rule's blind spot, paid for with
~8,000 additional low-precision alerts per 6.36M transactions scored.

## Summary

| Detector | Scope | Precision | Recall |
|---|---|---|---|
| Rule engine (Q5 balance-drain) | Full population | 100.00% | 97.50% |
| Isolation Forest (matched volume) | Full population | 0.61% | 0.60% |
| Isolation Forest | Residual (205 fraud the rule misses) | 0.475%* | 18.54% |

\* Precision computed over Isolation Forest's incremental flags within the rule's blind spot (transactions
the rule did not already flag), not the residual fraud count itself.

**Conclusion**: the rule engine should stay as the primary detector — it is materially better everywhere
that matters, including on the volume-matched full-population comparison. Isolation Forest is not a
credible standalone replacement given its full-population precision (0.61%) is two orders of magnitude
below the rule's. Its one genuine value-add is narrow and modest: as a secondary, lower-priority review
signal targeted specifically at transactions the rule engine did *not* flag, where it recovers under a
fifth of otherwise-missed fraud, at a cost of a sub-1%-precision add-on queue — a real but limited signal,
not the "40%+ lift" this report previously (incorrectly) claimed before the reproducibility fix above.
