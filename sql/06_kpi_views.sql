-- 06_kpi_views.sql  (materialized views feeding Power BI directly)

DROP MATERIALIZED VIEW IF EXISTS finsight.mv_credit_kpis;
DROP MATERIALIZED VIEW IF EXISTS finsight.mv_fraud_kpis;

CREATE MATERIALIZED VIEW finsight.mv_credit_kpis AS
SELECT grade, purpose,
       COUNT(*) AS loan_count,
       ROUND(AVG(interest_rate),2) AS avg_interest_rate,
       ROUND(100.0*SUM(CASE WHEN loan_status IN ('Charged Off','Default') THEN 1 ELSE 0 END)/COUNT(*),2) AS default_rate_pct
FROM finsight.loans
GROUP BY grade, purpose;

-- PaySim's `step` is hours since an arbitrary simulation start (1..743, ~31 days),
-- not a real calendar date. `step * INTERVAL '1 hour'` alone produces an INTERVAL
-- whose hour count lives entirely in the microseconds field rather than the days
-- field, so DATE_TRUNC('day', ...) truncated every row to the same zero interval
-- and collapsed the whole table into one bucket per txn_type. Anchoring to a real
-- (arbitrary) TIMESTAMP forces proper calendar-day bucketing.
CREATE MATERIALIZED VIEW finsight.mv_fraud_kpis AS
SELECT DATE_TRUNC('day', TIMESTAMP '2023-01-01 00:00:00' + step * INTERVAL '1 hour') AS txn_day,
       txn_type, COUNT(*) AS txn_count, SUM(is_fraud) AS fraud_count,
       SUM(amount) AS total_amount
FROM finsight.transactions
GROUP BY txn_day, txn_type;
