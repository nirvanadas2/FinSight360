-- 04_fraud_queries.sql

-- Q4: Fraud rate by transaction type
SELECT txn_type,
       COUNT(*) AS total_txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 4) AS fraud_rate_pct
FROM finsight.transactions
GROUP BY txn_type
ORDER BY fraud_rate_pct DESC;

-- Q5: High-risk pattern — account emptied in a single transaction (common fraud signature)
SELECT sender_id, txn_id, amount, sender_bal_before, sender_bal_after
FROM finsight.transactions
WHERE sender_bal_before > 0
  AND sender_bal_after = 0
  AND amount = sender_bal_before
  AND txn_type IN ('TRANSFER','CASH_OUT');

-- Q6: Rule-engine precision check — how many rule-flagged txns were actually fraud
SELECT
    SUM(CASE WHEN is_flagged_rule = 1 AND is_fraud = 1 THEN 1 ELSE 0 END) AS true_positives,
    SUM(CASE WHEN is_flagged_rule = 1 AND is_fraud = 0 THEN 1 ELSE 0 END) AS false_positives,
    ROUND(100.0 * SUM(CASE WHEN is_flagged_rule = 1 AND is_fraud = 1 THEN 1 ELSE 0 END)
          / NULLIF(SUM(is_flagged_rule),0), 2) AS rule_precision_pct
FROM finsight.transactions;
