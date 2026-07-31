-- 03_credit_risk_queries.sql

-- Q1: Default rate by loan grade (core underwriting KPI)
SELECT grade,
       COUNT(*) AS total_loans,
       SUM(CASE WHEN loan_status IN ('Charged Off','Default') THEN 1 ELSE 0 END) AS defaults,
       ROUND(100.0 * SUM(CASE WHEN loan_status IN ('Charged Off','Default') THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS default_rate_pct
FROM finsight.loans
GROUP BY grade
ORDER BY grade;

-- Q2: DTI and FICO band vs. default rate (risk segmentation for underwriting policy)
SELECT
    CASE
        WHEN fico_range_low < 660 THEN 'Subprime (<660)'
        WHEN fico_range_low BETWEEN 660 AND 719 THEN 'Near-Prime (660-719)'
        ELSE 'Prime (720+)'
    END AS fico_band,
    ROUND(AVG(dti),2) AS avg_dti,
    ROUND(100.0 * SUM(CASE WHEN loan_status IN ('Charged Off','Default') THEN 1 ELSE 0 END)
          / COUNT(*), 2) AS default_rate_pct
FROM finsight.loans
GROUP BY fico_band
ORDER BY default_rate_pct DESC;

-- Q3: Vintage analysis - default rate by loan issue quarter (portfolio monitoring)
SELECT DATE_TRUNC('quarter', issue_date) AS vintage_quarter,
       COUNT(*) AS loans_issued,
       ROUND(100.0 * SUM(CASE WHEN loan_status IN ('Charged Off','Default') THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS default_rate_pct
FROM finsight.loans
GROUP BY vintage_quarter
ORDER BY vintage_quarter;
