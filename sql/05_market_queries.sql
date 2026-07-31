-- 05_market_queries.sql

-- Q7: 30-day rolling volatility per ticker (window function)
SELECT ticker, trade_date,
       ROUND(STDDEV(daily_return) OVER (
             PARTITION BY ticker ORDER BY trade_date
             ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 5) AS rolling_30d_volatility
FROM finsight.stock_prices
ORDER BY ticker, trade_date;

-- Q8: Best/worst performing stocks over trailing 1 year
SELECT ticker,
       ROUND(100.0 * (MAX(close_price) - MIN(close_price)) / MIN(close_price), 2) AS pct_range
FROM finsight.stock_prices
WHERE trade_date >= (SELECT MAX(trade_date) - INTERVAL '365 days' FROM finsight.stock_prices)
GROUP BY ticker
ORDER BY pct_range DESC;
