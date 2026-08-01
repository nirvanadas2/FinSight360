# Business Insights Summary

**To:** Chief Risk Officer
**From:** FinSight360 Risk Analytics
**Re:** Credit, Fraud, Market Risk & Customer Segmentation — Recommendations

*Sourced from `reports/model_performance_report.md` (credit risk, fraud detection sections) and the
equivalent live-database-verified results in `notebooks/07_var_and_forecasting.ipynb` (market risk) and
`notebooks/06_customer_segmentation_rfm.ipynb` (segmentation) — no estimated or illustrative figures.*

## Credit Risk — LendingClub Loan Book

- **Recommend a ~25%-of-portfolio manual review queue** for new applications: at that threshold our model
  catches an estimated **44% of eventual defaulters at 35% precision** — a meaningfully better hit rate
  than an unscored review process.
- Review capacity should drive the exact cutoff, not the model: a tighter **~15% queue** still catches
  **30% of defaults at 40% precision** for teams with less review bandwidth; a wider **~35% queue** catches
  **56%** but roughly doubles both the review workload and the false-positive count. We recommend Risk Ops
  pick the row that matches actual staffing, not a single "optimal" number.
- Default risk is already steeply graded by LendingClub's own letter grade alone — **3.28%** for the
  safest tier (A) versus **38.07%** for the riskiest (G) — confirming grade-based pricing tiers remain a
  strong, cheap first-pass signal worth preserving in policy.
- Loan **term length is the single strongest predictor** of default in our independently-built model,
  ahead of FICO band, DTI, and income — 60-month loans carry materially more risk than 36-month loans and
  may warrant tighter eligibility or pricing terms at the longer tenor.

## Fraud Detection — Transaction Monitoring

- **Keep the existing balance-drain rule as the primary, automated block trigger.** It already achieves
  **100% precision and 97.5% recall**, catching **8,008 of 8,213** known fraudulent transactions with
  **zero false positives** — there is no case for replacing it.
- **Recommend piloting the anomaly-detection model as a secondary, non-blocking review queue only**, not a
  standalone detector: it recovers **18.5% of the fraud the rule misses** (38 of 205 residual cases), a
  real but modest signal.
- That signal comes at a real review cost: only **1 in ~210 of the model's incremental flags is actually
  fraud** (0.48% precision) — a review team would need to work through roughly 8,000 alerts to find those
  38 cases. **Do not deploy it as an automated block**; its full-population precision (0.61%) is two
  orders of magnitude below the rule's.
- Recommend re-evaluating the secondary queue's economics after a real pilot quarter of alert volume —
  sub-1%-precision alerts are only worth the review-team labor cost if catching that residual 18.5% of
  fraud clearly outweighs it.

## Market Risk — NSE Equity Portfolio (5 Tickers)

- The current equal-weighted 5-stock portfolio already delivers a **measurable diversification benefit**:
  1-day 95% VaR of **1.55% of portfolio value**, versus **2.11%** average if holding any one of the five
  stocks alone — the diversification case is real, not theoretical, in this data.
- **ICICIBANK.NS and RELIANCE.NS currently offer the best risk-adjusted returns** in the portfolio (Sharpe
  ratios of **0.62** and **0.13**); **TCS.NS and INFY.NS are currently negative** (**-0.32**, **-0.30**)
  over the trailing 5 years — worth a position-sizing review if this holds.
- **TCS.NS and INFY.NS are highly correlated (0.73)** — both IT services — and should not be sized as
  independent bets; HDFCBANK.NS/ICICIBANK.NS (both banking) are the next-most correlated pair (0.50).
  Recommend evaluating a genuine sector split, not just a 5-ticker split, for real diversification.
- Recommend treating the **99% VaR figures as directional only** — they're drawn from roughly a dozen
  extreme-day observations per ticker given the 5-year data window, not a precise capital-allocation input.

## Customer Segmentation

- **99.85% of the transaction customer base makes only one transaction** in the observed window — this is
  not, today, a repeat-customer business. The only segment with demonstrated repeat behavior
  ("High-Value Loyal") is **~9,300 customers (0.15% of the base)**. Recommend against investing in broad
  loyalty-program infrastructure until repeat behavior is more established at scale.
- That High-Value Loyal segment already carries the **highest average transaction value of any segment
  (₹366,625)** — recommend prioritizing retention outreach here first: it's the smallest, cheapest segment
  to target, and already has demonstrated repeat behavior to build on.
- The largest pool of transaction value outside the loyal segment sits in **"High-Value One-Time"**
  (**2.2M customers, ~35% of the base, ₹266,274 average**) — recommend a targeted "second transaction"
  campaign here as the highest-leverage lever for growing the loyal segment: even a small conversion rate
  on this large population would outweigh marginal gains elsewhere.
- Recommend deferring any customer-treatment decisions based on the new `risk_score` field until it's
  validated further — it's currently a lightweight, recency-weighted percentile-rank heuristic, not a
  calibrated churn/attrition probability.
