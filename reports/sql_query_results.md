# SQL Query Results

Run against the loaded `finsight` schema in PostgreSQL 15 (2,260,668 loans / 6,362,620 transactions / 6,195 stock price rows).


## 03_credit_risk_queries.sql


### Q1: Default rate by loan grade

```sql
SELECT grade,
       COUNT(*) AS total_loans,
       SUM(CASE WHEN loan_status IN ('Charged Off','Default') THEN 1 ELSE 0 END) AS defaults,
       ROUND(100.0 * SUM(CASE WHEN loan_status IN ('Charged Off','Default') THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS default_rate_pct
FROM finsight.loans
GROUP BY grade
ORDER BY grade;
```


| grade   | total_loans   | defaults   | default_rate_pct   |
|:--------|:--------------|:-----------|:-------------------|
| A       | 433027        | 14214      | 3.28               |
| B       | 663557        | 52661      | 7.94               |
| C       | 650053        | 85805      | 13.20              |
| D       | 324424        | 61264      | 18.88              |
| E       | 135639        | 36199      | 26.69              |
| F       | 41800         | 14585      | 34.89              |
| G       | 12168         | 4632       | 38.07              |


### Q2: DTI and FICO band vs. default rate

```sql
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
```


| fico_band            | avg_dti   | default_rate_pct   |
|:---------------------|:----------|:-------------------|
| Subprime (<660)      | 14.01     | 30.88              |
| Near-Prime (660-719) | 19.05     | 13.67              |
| Prime (720+)         | 18.10     | 6.15               |


### Q3: Vintage analysis - default rate by loan issue quarter

```sql
SELECT DATE_TRUNC('quarter', issue_date) AS vintage_quarter,
       COUNT(*) AS loans_issued,
       ROUND(100.0 * SUM(CASE WHEN loan_status IN ('Charged Off','Default') THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS default_rate_pct
FROM finsight.loans
GROUP BY vintage_quarter
ORDER BY vintage_quarter;
```


_Showing first 20 of 47 rows._

| vintage_quarter           | loans_issued   | default_rate_pct   |
|:--------------------------|:---------------|:-------------------|
| 2007-04-01 00:00:00+00:00 | 24             | 12.50              |
| 2007-07-01 00:00:00+00:00 | 190            | 21.05              |
| 2007-10-01 00:00:00+00:00 | 389            | 29.56              |
| 2008-01-01 00:00:00+00:00 | 1013           | 23.10              |
| 2008-04-01 00:00:00+00:00 | 498            | 22.09              |
| 2008-07-01 00:00:00+00:00 | 298            | 17.45              |
| 2008-10-01 00:00:00+00:00 | 584            | 17.12              |
| 2009-01-01 00:00:00+00:00 | 895            | 13.74              |
| 2009-04-01 00:00:00+00:00 | 1098           | 14.39              |
| 2009-07-01 00:00:00+00:00 | 1364           | 12.76              |
| 2009-10-01 00:00:00+00:00 | 1924           | 13.93              |
| 2010-01-01 00:00:00+00:00 | 2172           | 11.69              |
| 2010-04-01 00:00:00+00:00 | 3006           | 14.67              |
| 2010-07-01 00:00:00+00:00 | 3568           | 15.05              |
| 2010-10-01 00:00:00+00:00 | 3791           | 13.85              |
| 2011-01-01 00:00:00+00:00 | 4126           | 13.69              |
| 2011-04-01 00:00:00+00:00 | 5102           | 15.35              |
| 2011-07-01 00:00:00+00:00 | 5876           | 14.65              |
| 2011-10-01 00:00:00+00:00 | 6617           | 16.44              |
| 2012-01-01 00:00:00+00:00 | 8076           | 16.15              |


## 04_fraud_queries.sql


### Q4: Fraud rate by transaction type

```sql
SELECT txn_type,
       COUNT(*) AS total_txns,
       SUM(is_fraud) AS fraud_txns,
       ROUND(100.0 * SUM(is_fraud) / COUNT(*), 4) AS fraud_rate_pct
FROM finsight.transactions
GROUP BY txn_type
ORDER BY fraud_rate_pct DESC;
```


| txn_type   | total_txns   | fraud_txns   | fraud_rate_pct   |
|:-----------|:-------------|:-------------|:-----------------|
| TRANSFER   | 532909       | 4097         | 0.76880          |
| CASH_OUT   | 2237500      | 4116         | 0.18400          |
| CASH_IN    | 1399284      | 0            | 0.00000          |
| DEBIT      | 41432        | 0            | 0.00000          |
| PAYMENT    | 2151495      | 0            | 0.00000          |


### Q5: High-risk pattern - account emptied in a single transaction

```sql
SELECT sender_id, txn_id, amount, sender_bal_before, sender_bal_after
FROM finsight.transactions
WHERE sender_bal_before > 0
  AND sender_bal_after = 0
  AND amount = sender_bal_before
  AND txn_type IN ('TRANSFER','CASH_OUT')
ORDER BY txn_id;
```


_Showing first 20 of 8,008 rows._

| sender_id   | txn_id   | amount       | sender_bal_before   | sender_bal_after   |
|:------------|:---------|:-------------|:--------------------|:-------------------|
| C1305486145 | 3        | 181.00       | 181.00              | 0.00000            |
| C840083671  | 4        | 181.00       | 181.00              | 0.00000            |
| C1420196421 | 252      | 2,806.00     | 2,806.00            | 0.00000            |
| C2101527076 | 253      | 2,806.00     | 2,806.00            | 0.00000            |
| C137533655  | 681      | 20,128.00    | 20,128.00           | 0.00000            |
| C1118430673 | 682      | 20,128.00    | 20,128.00           | 0.00000            |
| C1334405552 | 970      | 1,277,212.77 | 1,277,212.77        | 0.00000            |
| C467632528  | 971      | 1,277,212.77 | 1,277,212.77        | 0.00000            |
| C1364127192 | 1116     | 35,063.63    | 35,063.63           | 0.00000            |
| C1635772897 | 1117     | 35,063.63    | 35,063.63           | 0.00000            |
| C669700766  | 1870     | 25,071.46    | 25,071.46           | 0.00000            |
| C1275464847 | 1871     | 25,071.46    | 25,071.46           | 0.00000            |
| C1872047468 | 2302     | 235,238.66   | 235,238.66          | 0.00000            |
| C1499825229 | 2303     | 235,238.66   | 235,238.66          | 0.00000            |
| C1093223281 | 3060     | 1,096,187.24 | 1,096,187.24        | 0.00000            |
| C77163673   | 3061     | 1,096,187.24 | 1,096,187.24        | 0.00000            |
| C1440057381 | 3163     | 963,532.14   | 963,532.14          | 0.00000            |
| C430329518  | 3164     | 963,532.14   | 963,532.14          | 0.00000            |
| C140702728  | 3272     | 14,949.84    | 14,949.84           | 0.00000            |
| C395257482  | 3273     | 14,949.84    | 14,949.84           | 0.00000            |


### Q6: Rule-engine precision check

```sql
SELECT
    SUM(CASE WHEN is_flagged_rule = 1 AND is_fraud = 1 THEN 1 ELSE 0 END) AS true_positives,
    SUM(CASE WHEN is_flagged_rule = 1 AND is_fraud = 0 THEN 1 ELSE 0 END) AS false_positives,
    ROUND(100.0 * SUM(CASE WHEN is_flagged_rule = 1 AND is_fraud = 1 THEN 1 ELSE 0 END)
          / NULLIF(SUM(is_flagged_rule),0), 2) AS rule_precision_pct
FROM finsight.transactions;
```


| true_positives   | false_positives   | rule_precision_pct   |
|:-----------------|:------------------|:---------------------|
| 0                | 0                 |                      |


## 05_market_queries.sql


### Q7: 30-day rolling volatility per ticker

```sql
SELECT ticker, trade_date,
       ROUND(STDDEV(daily_return) OVER (
             PARTITION BY ticker ORDER BY trade_date
             ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 5) AS rolling_30d_volatility
FROM finsight.stock_prices
ORDER BY ticker, trade_date;
```


_Showing first 20 of 6,195 rows._

| ticker      | trade_date   | rolling_30d_volatility   |
|:------------|:-------------|:-------------------------|
| HDFCBANK.NS | 2021-07-30   |                          |
| HDFCBANK.NS | 2021-08-02   |                          |
| HDFCBANK.NS | 2021-08-03   | 0.00787                  |
| HDFCBANK.NS | 2021-08-04   | 0.01201                  |
| HDFCBANK.NS | 2021-08-05   | 0.01003                  |
| HDFCBANK.NS | 2021-08-06   | 0.00896                  |
| HDFCBANK.NS | 2021-08-09   | 0.00804                  |
| HDFCBANK.NS | 2021-08-10   | 0.00773                  |
| HDFCBANK.NS | 2021-08-11   | 0.00920                  |
| HDFCBANK.NS | 2021-08-12   | 0.00863                  |
| HDFCBANK.NS | 2021-08-13   | 0.00882                  |
| HDFCBANK.NS | 2021-08-16   | 0.00845                  |
| HDFCBANK.NS | 2021-08-17   | 0.00942                  |
| HDFCBANK.NS | 2021-08-18   | 0.00917                  |
| HDFCBANK.NS | 2021-08-20   | 0.00886                  |
| HDFCBANK.NS | 2021-08-23   | 0.00856                  |
| HDFCBANK.NS | 2021-08-24   | 0.00941                  |
| HDFCBANK.NS | 2021-08-25   | 0.00925                  |
| HDFCBANK.NS | 2021-08-26   | 0.00912                  |
| HDFCBANK.NS | 2021-08-27   | 0.00909                  |


### Q8: Best/worst performing stocks over trailing 1 year

```sql
SELECT ticker,
       ROUND(100.0 * (MAX(close_price) - MIN(close_price)) / MIN(close_price), 2) AS pct_range
FROM finsight.stock_prices
WHERE trade_date >= (SELECT MAX(trade_date) - INTERVAL '365 days' FROM finsight.stock_prices)
GROUP BY ticker
ORDER BY pct_range DESC;
```


| ticker       | pct_range   |
|:-------------|:------------|
| INFY.NS      | 71.50       |
| TCS.NS       | 67.70       |
| HDFCBANK.NS  | 38.46       |
| RELIANCE.NS  | 26.49       |
| ICICIBANK.NS | 22.93       |


## 06_kpi_views.sql - Materialized Views


**Fix applied:** `mv_fraud_kpis` originally computed `DATE_TRUNC('day', step * INTERVAL '1 hour')`. In PostgreSQL, multiplying an hour-unit interval by an integer stores the result entirely in the interval's microseconds field, never carrying into the days field. `DATE_TRUNC('day', ...)` on that interval therefore truncated every row to the same zero interval, collapsing the whole table into 5 rows (one per `txn_type`) instead of a daily breakdown. Fixed by anchoring the interval to a real (arbitrary) timestamp: `DATE_TRUNC('day', TIMESTAMP '2023-01-01' + step * INTERVAL '1 hour')`, which correctly buckets `step` (PaySim hours-since-start) into 31 real calendar days. Both views were dropped and recreated with `DROP MATERIALIZED VIEW IF EXISTS` guards for idempotent re-runs, and both `REFRESH MATERIALIZED VIEW` successfully with no errors.


### mv_credit_kpis (sample)

```sql
SELECT * FROM finsight.mv_credit_kpis ORDER BY default_rate_pct DESC;
```


_Showing first 20 of 98 rows._

| grade   | purpose            | loan_count   | avg_interest_rate   | default_rate_pct   |
|:--------|:-------------------|:-------------|:--------------------|:-------------------|
| G       | renewable_energy   | 18           | 27.59               | 55.56              |
| G       | vacation           | 44           | 28.04               | 47.73              |
| F       | educational        | 11           | 16.69               | 45.45              |
| G       | small_business     | 602          | 26.83               | 43.19              |
| F       | renewable_energy   | 59           | 24.31               | 40.68              |
| E       | educational        | 37           | 15.61               | 40.54              |
| G       | medical            | 132          | 27.38               | 40.15              |
| G       | moving             | 147          | 27.75               | 39.46              |
| G       | car                | 69           | 28.10               | 39.13              |
| G       | debt_consolidation | 7594         | 28.22               | 38.83              |
| F       | small_business     | 1337         | 24.52               | 37.32              |
| F       | debt_consolidation | 26993        | 25.47               | 36.39              |
| G       | major_purchase     | 257          | 28.36               | 36.19              |
| G       | other              | 1365         | 28.10               | 35.97              |
| G       | credit_card        | 864          | 28.15               | 35.76              |
| F       | major_purchase     | 894          | 25.81               | 35.46              |
| G       | house              | 302          | 27.75               | 34.77              |
| D       | educational        | 53           | 14.65               | 33.96              |
| F       | car                | 275          | 25.39               | 33.45              |
| G       | home_improvement   | 740          | 27.94               | 33.38              |


### mv_fraud_kpis (sample)

```sql
SELECT * FROM finsight.mv_fraud_kpis ORDER BY txn_day, txn_type;
```


_Showing first 20 of 152 rows._

| txn_day             | txn_type   | txn_count   | fraud_count   | total_amount      |
|:--------------------|:-----------|:------------|:--------------|:------------------|
| 2023-01-01 00:00:00 | CASH_IN    | 123531      | 0             | 21,151,016,401.06 |
| 2023-01-01 00:00:00 | CASH_OUT   | 203803      | 138           | 37,383,704,757.49 |
| 2023-01-01 00:00:00 | DEBIT      | 4379        | 0             | 27,610,730.03     |
| 2023-01-01 00:00:00 | PAYMENT    | 192949      | 0             | 2,173,296,353.88  |
| 2023-01-01 00:00:00 | TRANSFER   | 46377       | 127           | 31,004,074,339.14 |
| 2023-01-02 00:00:00 | CASH_IN    | 99512       | 0             | 16,790,302,347.10 |
| 2023-01-02 00:00:00 | CASH_OUT   | 164323      | 154           | 30,132,786,891.44 |
| 2023-01-02 00:00:00 | DEBIT      | 2489        | 0             | 12,545,791.12     |
| 2023-01-02 00:00:00 | PAYMENT    | 148372      | 0             | 1,651,884,844.64  |
| 2023-01-02 00:00:00 | TRANSFER   | 38065       | 151           | 22,502,347,028.16 |
| 2023-01-03 00:00:00 | CASH_IN    | 827         | 0             | 136,335,397.08    |
| 2023-01-03 00:00:00 | CASH_OUT   | 1109        | 153           | 332,581,569.79    |
| 2023-01-03 00:00:00 | DEBIT      | 136         | 0             | 461,688.28        |
| 2023-01-03 00:00:00 | PAYMENT    | 3982        | 0             | 31,469,638.11     |
| 2023-01-03 00:00:00 | TRANSFER   | 695         | 153           | 427,326,338.90    |
| 2023-01-04 00:00:00 | CASH_IN    | 3982        | 0             | 639,050,102.67    |
| 2023-01-04 00:00:00 | CASH_OUT   | 5127        | 136           | 1,055,152,181.95  |
| 2023-01-04 00:00:00 | DEBIT      | 222         | 0             | 1,736,752.40      |
| 2023-01-04 00:00:00 | PAYMENT    | 10555       | 0             | 98,908,049.57     |
| 2023-01-04 00:00:00 | TRANSFER   | 2018        | 136           | 1,357,000,843.42  |
