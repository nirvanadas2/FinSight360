-- 07_market_and_segment_views.sql  (materialized views feeding the Market Risk and
-- Customer Segmentation dashboard pages, same pattern as 06_kpi_views.sql)

DROP MATERIALIZED VIEW IF EXISTS finsight.mv_market_risk_kpis;
DROP MATERIALIZED VIEW IF EXISTS finsight.mv_market_risk_correlation;
DROP MATERIALIZED VIEW IF EXISTS finsight.mv_segment_summary;

-- Per-ticker annualized return/volatility, Sharpe ratio, and historical + parametric VaR
-- at 95%/99% confidence. Mirrors src/market_risk.py exactly (validated against it row for
-- row) so the dashboard and the notebook never quietly disagree:
--   - Annualized return: (1 + mean daily return)^252 - 1, same formula as market_risk.py /
--     notebooks/03_eda_market.ipynb.
--   - Sharpe ratio: risk-free rate hardcoded to 0.07 (7%), the same static India 10Y G-Sec
--     proxy as src/market_risk.py's INDIA_RISK_FREE_RATE - a stated assumption, not a
--     live-pulled rate. Update both places together if that constant ever changes.
--   - Historical VaR: PERCENTILE_CONT gives the empirical 5th/1st percentile of daily
--     returns directly - no distributional assumption.
--   - Parametric VaR: assumes returns ~ Normal(mean, std); z=1.645 (95%) / z=2.326 (99%)
--     are the standard one-tailed normal critical values, hardcoded since Postgres has no
--     inverse-normal-CDF function and only two confidence levels are ever needed here.
--   - As in the notebook: with ~1,239 observations per ticker, the 99% column's empirical
--     tail (historical_var_99_pct) is drawn from only ~12 data points - directional, not
--     precise. Surface that caveat next to the number on the dashboard, don't drop it.
--
-- Includes a 6th row, ticker = 'PORTFOLIO (equal-wt)': the same statistics computed on the
-- equal-weighted portfolio's daily return (mean of all 5 tickers' returns each trading day,
-- only on days every ticker traded - matches src/market_risk.py::portfolio_returns exactly,
-- validated to the 3rd-4th decimal against notebooks/07_var_and_forecasting.ipynb Section 4's
-- printed figures). Putting it in the same view/column shape as the per-ticker rows means one
-- table/bar-chart visual can show portfolio VaR alongside single-ticker VaR without an extra
-- join - filter or color by ticker = 'PORTFOLIO (equal-wt)' to call it out on the dashboard.
CREATE MATERIALIZED VIEW finsight.mv_market_risk_kpis AS
WITH per_ticker AS (
    SELECT ticker,
           COUNT(daily_return) AS n_obs,
           AVG(daily_return) AS mean_return,
           STDDEV(daily_return) AS stddev_return,
           PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY daily_return) AS pctile_05,
           PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY daily_return) AS pctile_01
    FROM finsight.stock_prices
    WHERE daily_return IS NOT NULL
    GROUP BY ticker
),
portfolio_returns AS (
    -- One row per trade_date, only where every ticker has a return that day (equal-weight
    -- average requires all legs present - mirrors portfolio_returns()'s dropna(how="any")).
    SELECT trade_date, AVG(daily_return) AS daily_return
    FROM finsight.stock_prices
    WHERE daily_return IS NOT NULL
    GROUP BY trade_date
    HAVING COUNT(*) = (SELECT COUNT(DISTINCT ticker) FROM finsight.stock_prices)
),
portfolio AS (
    SELECT 'PORTFOLIO (equal-wt)' AS ticker,
           COUNT(*) AS n_obs,
           AVG(daily_return) AS mean_return,
           STDDEV(daily_return) AS stddev_return,
           PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY daily_return) AS pctile_05,
           PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY daily_return) AS pctile_01
    FROM portfolio_returns
),
stats AS (
    SELECT * FROM per_ticker
    UNION ALL
    SELECT * FROM portfolio
)
SELECT ticker,
       n_obs,
       ROUND(((POWER(1 + mean_return, 252) - 1) * 100)::numeric, 2) AS annualized_return_pct,
       ROUND((stddev_return * SQRT(252) * 100)::numeric, 2) AS annualized_volatility_pct,
       ROUND((((POWER(1 + mean_return, 252) - 1) - 0.07) / (stddev_return * SQRT(252)))::numeric, 3) AS sharpe_ratio,
       ROUND((-pctile_05 * 100)::numeric, 4) AS historical_var_95_pct,
       ROUND((-pctile_01 * 100)::numeric, 4) AS historical_var_99_pct,
       ROUND((-(mean_return - 1.645 * stddev_return) * 100)::numeric, 4) AS parametric_var_95_pct,
       ROUND((-(mean_return - 2.326 * stddev_return) * 100)::numeric, 4) AS parametric_var_99_pct
FROM stats;

-- Pairwise ticker return correlation, long/tidy (ticker_a, ticker_b, correlation) rather
-- than a wide matrix, so a BI tool's matrix/heatmap visual can bind directly to it without
-- a pivot step. Includes the ticker_a = ticker_b diagonal (correlation = 1) since heatmap
-- visuals expect the full square. Not one of the two views named in the request, but added
-- because the Market Risk page's correlation heatmap (Part 8's stated deliverable) has no
-- other queryable source: Postgres has no built-in way to pivot finsight.stock_prices into
-- a correlation matrix inside a BI tool's own visual without this precomputed table.
CREATE MATERIALIZED VIEW finsight.mv_market_risk_correlation AS
SELECT a.ticker AS ticker_a,
       b.ticker AS ticker_b,
       ROUND(CORR(a.daily_return, b.daily_return)::numeric, 4) AS correlation
FROM finsight.stock_prices a
JOIN finsight.stock_prices b ON a.trade_date = b.trade_date
WHERE a.daily_return IS NOT NULL AND b.daily_return IS NOT NULL
GROUP BY a.ticker, b.ticker;

-- One row per segment: customer counts and avg RFM, pulling from finsight.customers now
-- that customer_segmentation.py has populated .segment for all 6,353,307 customers.
-- avg_recency_days_proxy is derived from last_txn_date (max(last_txn_date) across all
-- customers - each customer's last_txn_date), NOT the raw recency_hours the K-Means model
-- actually clustered on - that value isn't persisted to finsight.customers. last_txn_date
-- itself is anchored to an arbitrary TIMESTAMP '2023-01-01' base (see
-- src/customer_segmentation.py / sql/06_kpi_views.sql) since PaySim's `step` is
-- hours-since-simulation-start, not a real calendar date - this column is a same-dataset
-- relative-ordering proxy for Recency, not real calendar recency, and should be labeled
-- that way on the dashboard rather than read as "days since last real transaction".
-- avg_risk_score is the customer_segmentation.py::write_risk_scores() percentile-rank RFM
-- blend (50% Recency / 25% Frequency / 25% Monetary, 0-100, higher = more disengagement
-- risk) - run write_risk_scores() and REFRESH this view after any re-run of the RFM pipeline,
-- since risk_score is written back in a separate step from write_customers().
CREATE MATERIALIZED VIEW finsight.mv_segment_summary AS
WITH base AS (
    SELECT segment, total_txn_count, total_txn_value, avg_txn_value, last_txn_date, risk_score,
           (SELECT MAX(last_txn_date) FROM finsight.customers) AS max_last_txn_date
    FROM finsight.customers
    WHERE segment IS NOT NULL
)
SELECT segment,
       COUNT(*) AS n_customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_customers,
       ROUND(AVG(total_txn_count), 3) AS avg_frequency,
       ROUND(AVG(total_txn_value), 2) AS avg_monetary,
       ROUND(AVG(avg_txn_value), 2) AS avg_txn_value,
       SUM(total_txn_value) AS total_segment_value,
       ROUND(AVG(max_last_txn_date - last_txn_date), 2) AS avg_recency_days_proxy,
       ROUND(AVG(risk_score), 2) AS avg_risk_score
FROM base
GROUP BY segment;
