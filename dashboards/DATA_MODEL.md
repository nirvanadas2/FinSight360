# Dashboard Data Model

Spec for the 5 dashboard pages: **Overview**, **Credit Risk**, **Fraud Detection**, **Market
Risk**, **Customer Segmentation**. Connect Power BI / Tableau directly to the `finsight` schema
in PostgreSQL (`src/db_connect.py::get_engine()` has the connection parameters). Every
table/view referenced below has been verified to exist and return correct data against the live
database as of this writing.

## Read this first

**There is no single global date filter that works across all 5 pages.** The three source
datasets are on three unrelated time axes, and a shared date slicer would silently misrepresent
one of them:

- `finsight.loans.issue_date` - real calendar dates, roughly 2007-2018 (LendingClub).
- `finsight.transactions` - PaySim's `step` (hours since an arbitrary simulation start,
  1-743, ~31 simulated days), anchored in SQL to a synthetic `TIMESTAMP '2023-01-01'` purely so
  `mv_fraud_kpis.txn_day` has a real DATE type to bucket on. **`txn_day` values in January 2023
  are not real calendar dates** - they're simulated-day 1 through 31, relabeled. Same anchor
  logic covers `finsight.customers.signup_date` / `last_txn_date`.
- `finsight.stock_prices.trade_date` - real calendar dates, 2021-08-02 to 2026-07-30 (NSE).

Build the Fraud Detection and Customer Segmentation pages' date filters as **relative /
ordinal** ("simulated day N"), not calendar-labeled, and keep each page's date filter scoped to
that page only.

**Two source tables are large enough to matter for import-mode BI tools**:
`finsight.transactions` (6,362,620 rows) and `finsight.customers` (6,353,307 rows). Prefer
DirectQuery/live connection over import for anything hitting them at row level, or pre-aggregate
further server-side. The materialized views below are already aggregated and safe to import.

**Materialized views need a manual refresh after any pipeline re-run** - none of them are on an
auto-refresh schedule. Run `REFRESH MATERIALIZED VIEW finsight.<view_name>;` for all 5 views
(`mv_credit_kpis`, `mv_fraud_kpis`, `mv_market_risk_kpis`, `mv_market_risk_correlation`,
`mv_segment_summary`) before pulling fresh dashboard data, same as the existing two.

---

## Sources at a glance

| Source | Kind | Rows | Feeds |
|---|---|---|---|
| `finsight.loans` | table | 2,260,668 | Credit Risk |
| `finsight.mv_credit_kpis` | matview (`grade` x `purpose`) | 98 | Credit Risk, Overview |
| `finsight.transactions` | table (now includes `anomaly_score`, `is_flagged_iforest`) | 6,362,620 | Fraud Detection |
| `finsight.mv_fraud_kpis` | matview (`txn_day` x `txn_type`) | 152 | Fraud Detection, Overview |
| `finsight.stock_prices` | table | 6,195 | Market Risk |
| `finsight.mv_market_risk_kpis` | matview (1 row/ticker + 1 portfolio row) **new** | 6 | Market Risk, Overview |
| `finsight.mv_market_risk_correlation` | matview (ticker pair) **new** | 25 | Market Risk |
| `finsight.customers` | table (now includes populated `risk_score`) | 6,353,307 | Customer Segmentation |
| `finsight.mv_segment_summary` | matview (1 row/segment) **new** | 4 | Customer Segmentation, Overview |

`mv_market_risk_kpis`, `mv_market_risk_correlation`, and `mv_segment_summary` are new
(`sql/07_market_and_segment_views.sql`), added for this dashboard. All three have been created
in the live database and validated against the equivalent Python calculations in
`src/market_risk.py` and `notebooks/06_customer_segmentation_rfm.ipynb` (matching to the
displayed rounding).

---

## Page 1: Overview

Landing page - one KPI-card row per domain, no row-level detail. Pulls exclusively from the
already-aggregated matviews, so it's cheap to import.

| Visual | Type | Source | Fields | Notes |
|---|---|---|---|---|
| Total loans / overall default rate | KPI cards | `mv_credit_kpis` | `SUM(loan_count)`; weighted avg of `default_rate_pct` by `loan_count` | Weighted avg, not a plain average across the 98 grade/purpose rows |
| Total transactions / overall fraud rate | KPI cards | `mv_fraud_kpis` | `SUM(txn_count)`, `SUM(fraud_count)` | fraud_rate = `SUM(fraud_count)/SUM(txn_count)` |
| Portfolio Sharpe ratio / volatility | KPI cards | `mv_market_risk_kpis` | `sharpe_ratio`, `annualized_volatility_pct` WHERE `ticker = 'PORTFOLIO (equal-wt)'` | Use the portfolio row directly, not `AVG()` across the 5 ticker rows - averaging ticker-level Sharpe/vol ignores cross-ticker correlation and won't match the portfolio row's true (lower) volatility |
| Total customers / top segment | KPI card + label | `mv_segment_summary` | `SUM(n_customers)`; `segment` with max `n_customers` | |
| Default rate by grade (mini) | Bar, small multiple | `mv_credit_kpis` | X=`grade`, Y=avg `default_rate_pct` | Link/drill to Credit Risk page |
| Fraud rate by txn_type (mini) | Bar, small multiple | `mv_fraud_kpis` | X=`txn_type`, Y=`SUM(fraud_count)/SUM(txn_count)` | Link/drill to Fraud page |
| Sharpe ratio by ticker (mini) | Bar, small multiple | `mv_market_risk_kpis` | X=`ticker`, Y=`sharpe_ratio` | Link/drill to Market Risk page |
| Customers by segment (mini) | Donut | `mv_segment_summary` | Category=`segment`, Value=`n_customers` | Link/drill to Segmentation page |

No page-level date filter (see "Read this first").

---

## Page 2: Credit Risk

| Visual | Type | Source | Fields | Notes |
|---|---|---|---|---|
| Total loans / overall default rate | KPI cards | `mv_credit_kpis` | as Overview | |
| Default rate by grade | Bar | `mv_credit_kpis` | X=`grade` (sort A→G), Y=avg `default_rate_pct` weighted by `loan_count` | Color by `grade` (sequential, A=lowest risk) |
| Loan count & default rate by purpose | Bar (dual-axis or two charts) | `mv_credit_kpis` | X=`purpose` sorted by `default_rate_pct` desc, Y1=`default_rate_pct`, Y2=`loan_count` | |
| Avg interest rate by grade/purpose | Heatmap/matrix | `mv_credit_kpis` | Rows=`grade`, Cols=`purpose`, Value=`avg_interest_rate` | |
| Default rate by vintage quarter | Line | `finsight.loans` (live query) | X=`DATE_TRUNC('quarter', issue_date)`, Y=default rate calc | Not in a matview - build the aggregation in-tool, or reuse `sql/03_credit_risk_queries.sql` Q3 as the source query |
| Default rate by U.S. state | Choropleth map | `finsight.loans` (live query) | Geo=`state`, Value=default rate calc | 51 distinct states, 0 nulls - map-ready as-is |
| FICO vs. DTI vs. outcome | Scatter (sampled) | `finsight.loans` (live query) | X=`dti`, Y=`fico_range_low`, color=`loan_status` | Sample or aggregate into bins - 2.26M raw points won't render usefully |
| Filters | Slicers | - | `grade`, `purpose`, `state`, `issue_date` range | |

**Known gap**: model performance (AUC-ROC, precision/recall by threshold, the chosen
recall-favoring F2 threshold, XGBoost-vs-logistic-regression comparison) lives only in
`reports/model_performance_report.md` as static analysis - none of it is written to Postgres.
There's no per-loan predicted-probability column in `finsight.loans` either. Represent this on
the page as a static text/image panel pulled from that report, not a live-connected visual.
Similarly, `grade`/`sub_grade`/`interest_rate`/`installment` appear here purely as *observed*
loan attributes (fine for a default-rate-by-grade chart) - they're excluded as *model features*
in `src/credit_risk_model.py` for leakage reasons that don't apply to this reporting use.

---

## Page 3: Fraud Detection

| Visual | Type | Source | Fields | Notes |
|---|---|---|---|---|
| Total transactions / fraud count / fraud rate | KPI cards | `mv_fraud_kpis` | `SUM(txn_count)`, `SUM(fraud_count)`, rate calc | |
| Rule-engine precision | KPI card | `finsight.transactions` (live query) | `SUM(CASE WHEN is_flagged_rule=1 AND is_fraud=1 THEN 1 END)` / `SUM(is_flagged_rule)` | Currently 8,008/8,008 = 100% precision in this data (`sql/04_fraud_queries.sql` Q5/Q6 pattern) - not in a matview, needs a direct aggregate query against `finsight.transactions` |
| Txn count & fraud count by simulated day | Line/area | `mv_fraud_kpis` | X=`txn_day` (label as "simulated day", not calendar date), Y=`txn_count`/`fraud_count`, series=`txn_type` | Only 31 distinct days - see "Read this first" |
| Fraud rate by transaction type | Bar | `mv_fraud_kpis` | X=`txn_type`, Y=`SUM(fraud_count)/SUM(txn_count)` | Fraud only ever occurs on `TRANSFER`/`CASH_OUT` in this data - the other 3 bars will be exactly zero, not a display bug |
| Total transaction value by type | Bar | `mv_fraud_kpis` | X=`txn_type`, Y=`SUM(total_amount)` | |
| Rule vs. Isolation Forest precision/recall | Table / KPI cards | `finsight.transactions` (live query) | Confusion matrix (`tp`/`fp`/`fn`/`tn`) for `is_flagged_rule` and, separately, `is_flagged_iforest`, both against `is_fraud` | Isolation Forest's `contamination` was matched to the rule's flagged rate (0.001259) for an apples-to-apples volume comparison - see caveat below before reading this as "which detector wins" |
| Anomaly score distribution | Histogram (sampled/binned) | `finsight.transactions` (live query) | X=`anomaly_score` (binned), color=`is_fraud` | 6.36M rows - bin server-side (`GROUP BY width_bucket(anomaly_score, ...)`) or sample, same reasoning as the Credit Risk page's FICO/DTI scatter |
| Filters | Slicers | - | `txn_type`, `txn_day` (as simulated-day ordinal), `is_fraud` | |

`anomaly_score` and `is_flagged_iforest` are now populated on every row of `finsight.transactions`
(`src/fraud_detection.py::write_iforest_scores()`, called from `notebooks/05_fraud_anomaly_detection.ipynb`
Section 4) - the "known gap" from the previous version of this doc is closed. **Read the comparison
row above with the same caveat the notebook itself leads with**: at matched flagged volume, the
full-population comparison is dominated by the ~97.5% of fraud the rule already catches by
construction, so it is not a fair "which detector is better" test - `reports/model_performance_report.md`
Section 2 has the more decisive result (Isolation Forest catches 38 of the 205 fraud transactions
the rule's exact signature misses, 18.5% recall on that residual slice, at 0.475% precision on the
rule's blind spot). If this page is meant to argue Isolation Forest adds value, lead with the residual
number, not the full-population one - though note even the residual signal here is real-but-modest
(under a fifth of otherwise-missed fraud, at sub-1% precision), not a strong standalone case.

**Reproducibility pitfall, worth knowing before rebuilding anything against these columns**: an earlier
run of this pipeline produced different numbers (109 full-population TP, 91/205 residual caught) purely
because the pull query lacked `ORDER BY txn_id` - `IsolationForest` bootstraps by positional row index,
not `txn_id`, so a fixed `random_state` doesn't guarantee reproducibility unless row order is also fixed,
and `write_iforest_scores()`'s own `UPDATE` silently changed the table's physical row order between runs.
Fixed and verified deterministic (two independent fits on the now-ordered pull produced bit-identical
scores) - see `notebooks/05_fraud_anomaly_detection.ipynb`'s intro and `reports/model_performance_report.md`
Section 2 for the full writeup. If `anomaly_score`/`is_flagged_iforest` are ever regenerated, the pull
must keep `ORDER BY txn_id` or this will silently drift again.

---

## Page 4: Market Risk

| Visual | Type | Source | Fields | Notes |
|---|---|---|---|---|
| Per-ticker + portfolio summary table | Table | `mv_market_risk_kpis` | `ticker`, `annualized_return_pct`, `annualized_volatility_pct`, `sharpe_ratio` | Sortable by `sharpe_ratio`. Includes a `PORTFOLIO (equal-wt)` row alongside the 5 tickers - style it distinctly (bold row / different color) so it reads as the aggregate, not a 6th stock |
| Sharpe ratio by ticker | Bar | `mv_market_risk_kpis` | X=`ticker`, Y=`sharpe_ratio` | Diverging color at 0; include the `PORTFOLIO (equal-wt)` bar |
| 95% VaR: historical vs. parametric, per ticker + portfolio | Clustered bar | `mv_market_risk_kpis` | X=`ticker`, Y1=`historical_var_95_pct`, Y2=`parametric_var_95_pct` | `PORTFOLIO (equal-wt)`'s bar should visibly sit below every single-ticker bar - that gap *is* the diversification effect (1.55% portfolio vs. 1.82-2.56% single-ticker historical VaR at 95%) |
| 99% VaR: historical vs. parametric, per ticker + portfolio | Clustered bar | `mv_market_risk_kpis` | X=`ticker`, Y1=`historical_var_99_pct`, Y2=`parametric_var_99_pct` | Same diversification read as the 95% chart. Add a visible caveat/tooltip: ~1,239 obs/ticker means the single-ticker empirical 1% tail is ~12 points - directional, not precise (the portfolio row pools more effective observations via averaging, so is comparatively more stable) |
| Return correlation heatmap | Matrix/heatmap | `mv_market_risk_correlation` | Rows=`ticker_a`, Cols=`ticker_b`, Value=`correlation` | Diverging scale, -1 to 1, center 0; diagonal is always 1.0. Ticker-pair-only (no portfolio row) - correlation of the portfolio with itself isn't a meaningful addition here |
| Adjusted close price over time | Line | `finsight.stock_prices` (live query) | X=`trade_date`, Y=`adj_close`, color=`ticker` | |
| (Optional) 30-day rolling volatility | Line | `finsight.stock_prices` (live query) | X=`trade_date`, Y=rolling stddev of `daily_return`, color=`ticker` | Not built into a matview; reuse `sql/05_market_queries.sql` Q7 as the source query if wanted |
| Filters | Slicers | - | `ticker` (multi-select, include `PORTFOLIO (equal-wt)` as a selectable value), `trade_date` range | |

`mv_market_risk_kpis` now includes a `PORTFOLIO (equal-wt)` row (`ticker = 'PORTFOLIO (equal-wt)'`)
computed the same way as `src/market_risk.py::portfolio_returns()` - the equal-weighted average of
all 5 tickers' daily returns, only on days every ticker traded - so the "known gap" from the
previous version of this doc is closed: portfolio VaR/volatility/Sharpe is queryable alongside the
per-ticker rows in the same table, validated to match `notebooks/07_var_and_forecasting.ipynb`
Section 4's printed figures (95% historical VaR: 1.55% portfolio vs. 2.11% average single-ticker).

**Known gap**: ARIMA forecast results (`notebooks/07_var_and_forecasting.ipynb` Sections 5-7)
aren't in the database. Per that notebook's own conclusion, ARIMA ties the naive last-value
baseline and loses to the naive-seasonal baseline on every one of the 6 series tested - not a
result worth a live dashboard visual regardless; if shown at all, a static export of the
forecast-vs-actual plot with that caveat attached is more honest than a "live forecast" widget.

---

## Page 5: Customer Segmentation

| Visual | Type | Source | Fields | Notes |
|---|---|---|---|---|
| Customers by segment | Donut/bar | `mv_segment_summary` | Category=`segment`, Value=`n_customers` (or `pct_of_customers`) | |
| Avg monetary value by segment | Bar | `mv_segment_summary` | X=`segment`, Y=`avg_monetary` | |
| Total value by segment | Bar | `mv_segment_summary` | X=`segment`, Y=`total_segment_value` | Shows concentration - expect `High-Value One-Time` and `Standard One-Time` to dominate by sheer count even though `High-Value Loyal` has the highest per-customer average |
| Avg frequency by segment | Bar | `mv_segment_summary` | X=`segment`, Y=`avg_frequency` | Will look nearly flat at ~1.0 for 3 of 4 segments - expected, not a bug: 99.85% of all customers are one-shot senders (`notebooks/06_customer_segmentation_rfm.ipynb` Section 2) |
| Avg recency (proxy) by segment | Bar | `mv_segment_summary` | X=`segment`, Y=`avg_recency_days_proxy` | **Label this explicitly as a proxy** - see caveat below |
| Avg risk score by segment | Bar | `mv_segment_summary` | X=`segment`, Y=`avg_risk_score` | 0-100, higher = more disengagement risk - see formula/caveat below before treating it as a calibrated probability |
| Risk score distribution (sampled) | Histogram | `finsight.customers` (live query, sampled) | X=`risk_score` (binned), color=`segment` | Sample or extract-filter down from 6.35M rows, same reasoning as the scatter below |
| Recency vs. monetary scatter (sampled) | Scatter | `finsight.customers` (live query, sampled) | X=`last_txn_date`, Y=`total_txn_value` (log scale), size=`total_txn_count`, color=`segment` (or `risk_score`) | Sample or extract-filter down from 6.35M rows - `notebooks/06_customer_segmentation_rfm.ipynb` uses a 15,000-row seeded sample for the same reason |
| Filters | Slicers | - | `segment`, `last_txn_date` (as relative/ordinal - see "Read this first"), `risk_score` range | |

`avg_recency_days_proxy` is derived from `last_txn_date`, which is itself anchored to the same
synthetic `TIMESTAMP '2023-01-01'` base as the Fraud page's `txn_day` - it's a same-dataset
relative-ordering proxy for Recency, **not** the raw `recency_hours` (`max_step - last_step`)
the K-Means model actually clustered on, and not real calendar recency. Label it accordingly
on the dashboard rather than as "days since last real transaction."

`finsight.customers.risk_score` is now populated for all 6,353,307 rows
(`src/customer_segmentation.py::write_risk_scores()`), so the "known gap" from the previous
version of this doc is closed - but read the number for what it actually is before wiring up
KPI cards or conditional formatting against it: it's a **percentile-rank blend of the same
RFM fields already on this table** (50% Recency / 25% Frequency / 25% Monetary, 0-100, higher =
more disengagement risk), computed directly in SQL as a dashboard-facing heuristic - **not** a
re-run of the K-Means clustering model and **not** a validated churn/attrition probability.
Two things worth surfacing on the page itself rather than leaving implicit:
- Because 99.85% of customers are one-shot senders (near-constant Frequency, per
  `notebooks/06_customer_segmentation_rfm.ipynb` Section 2), the Frequency term barely
  differentiates anyone - `risk_score` is, in practice, mostly a Recency ranking with a
  Monetary tiebreaker, not a true three-factor score, for the large majority of the population.
- **Actual computed ordering (lowest to highest avg `risk_score`)**: `Standard One-Time`
  (18.92) < `High-Value Loyal` (22.70) < `High-Value One-Time` (42.81) < `Low-Value One-Time`
  (46.82). Note this is **not** "the repeat-purchase segment is lowest-risk" - `Standard
  One-Time` edges out `High-Value Loyal` because Recency (50% of the score) dominates, and
  `Standard One-Time` customers' `last_txn_date` happens to skew slightly more recent
  (`avg_recency_days_proxy` 14.87 vs. `High-Value Loyal`'s 17.29 - both still well ahead of
  `Low-Value One-Time`'s 21.64 and `High-Value One-Time`'s 24.96). `Low-Value One-Time` ends up
  worst overall despite better recency than `High-Value One-Time` because its Monetary
  percentile is dramatically worse (its avg transaction value, ~₹9,518, sits deep in the
  bottom of the population - avg monetary percentile 83.04 vs. 28.98-38.76 for the other three
  segments), which outweighs its recency edge. If a rebuild shows a materially different
  ordering, that's worth investigating (a formula or join error) - but don't assume
  "loyalty implies lowest risk" as the expected baseline; the data doesn't actually support
  that intuition once Recency and Monetary are both in play.
