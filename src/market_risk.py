"""Returns, volatility, Sharpe ratio, historical & parametric VaR, correlation matrix.

VaR here is single-day, expressed as a positive fraction of position value (e.g. 0.023 =
a 2.3% one-day loss at the given confidence level) - not scaled to a longer holding period,
since the only data available is daily closes.

- `historical_var`: empirical VaR, the (1-confidence) quantile of the actual observed daily
  return distribution. Makes no distributional assumption, but with ~1,239 trading days per
  ticker (see reports/data_inventory.md), the 1% tail (99% VaR) is estimated from roughly a
  dozen observations - noisy, and flagged as such in the notebook rather than overstated.
- `parametric_var`: variance-covariance VaR, assumes returns are normally distributed and
  uses the sample mean/std as the distribution's parameters. Cheaper to estimate from a short
  series than the historical tail is, but only as good as the normality assumption - equity
  returns are typically fat-tailed, so this tends to understate true tail risk.

No randomness is involved in any calculation in this module (all statistics below are closed-
form on observed data), so RANDOM_STATE (used elsewhere in the project, e.g. forecasting.py,
customer_segmentation.py) does not apply here.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from sqlalchemy import text

TICKERS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]
TRADING_DAYS_PER_YEAR = 252

# Static approximation of the India 10Y G-Sec yield, used as Sharpe's risk-free reference for
# these INR-denominated equities. Not live-pulled - a reasonable conventional proxy, not a
# precise figure, and callers can override it.
INDIA_RISK_FREE_RATE = 0.07


def load_returns_wide(engine, tickers: list = None) -> pd.DataFrame:
    """Daily returns from finsight.stock_prices, pivoted to one column per ticker
    (index = trade_date). Rows where every ticker is NaN (each series' first trading
    day, with no prior close to compute a return from - see notebooks/03_eda_market.ipynb)
    are dropped; a ticker's own first-day NaN elsewhere is left for callers to handle
    per-series (dropna()), since pairwise correlation/statistics only need pairwise data.
    """
    tickers = list(tickers or TICKERS)
    query = text("""
        SELECT ticker, trade_date, adj_close, daily_return
        FROM finsight.stock_prices
        WHERE ticker = ANY(:tickers)
        ORDER BY ticker, trade_date;
    """)
    df = pd.read_sql(query, engine, params={"tickers": tickers})
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    wide = df.pivot(index="trade_date", columns="ticker", values="daily_return")
    return wide.dropna(how="all")[tickers]


def load_prices_wide(engine, tickers: list = None) -> pd.DataFrame:
    """Adjusted close, pivoted to one column per ticker (index = trade_date)."""
    tickers = list(tickers or TICKERS)
    query = text("""
        SELECT ticker, trade_date, adj_close
        FROM finsight.stock_prices
        WHERE ticker = ANY(:tickers)
        ORDER BY ticker, trade_date;
    """)
    df = pd.read_sql(query, engine, params={"tickers": tickers})
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.pivot(index="trade_date", columns="ticker", values="adj_close")[tickers]


def portfolio_returns(returns: pd.DataFrame, weights: dict = None) -> pd.Series:
    """Equal-weighted (unless `weights` given) portfolio daily return series.

    Rows with any missing ticker return are dropped first, so every day's portfolio
    return is a true weighted blend of all tickers rather than silently reweighting
    around a missing one.
    """
    returns = returns.dropna(how="any")
    if weights is None:
        w = pd.Series(1.0 / returns.shape[1], index=returns.columns)
    else:
        w = pd.Series(weights)[returns.columns]
        w = w / w.sum()
    return (returns * w).sum(axis=1).rename("portfolio")


def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Empirical VaR: the loss at the (1-confidence) quantile of the historical
    return distribution. Returned as a positive fraction.
    """
    returns = returns.dropna()
    alpha = 1 - confidence
    return float(-np.percentile(returns, alpha * 100))


def parametric_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Variance-covariance VaR: assumes returns ~ Normal(mean, std) fit from the
    sample, and reads off the (1-confidence) quantile of that fitted distribution.
    Returned as a positive fraction.
    """
    returns = returns.dropna()
    mu, sigma = returns.mean(), returns.std()
    z = norm.ppf(1 - confidence)  # negative for confidence > 0.5
    return float(-(mu + z * sigma))


def var_summary_table(returns: pd.DataFrame, confidence_levels=(0.95, 0.99)) -> pd.DataFrame:
    """historical_var / parametric_var side by side, per ticker (or portfolio series
    column) and confidence level, in both return-fraction and percent form.
    """
    rows = []
    for col in returns.columns:
        series = returns[col].dropna()
        for cl in confidence_levels:
            rows.append({
                "ticker": col,
                "confidence": cl,
                "n_obs": len(series),
                "historical_var_pct": historical_var(series, cl) * 100,
                "parametric_var_pct": parametric_var(series, cl) * 100,
            })
    return pd.DataFrame(rows)


def annualized_return(returns: pd.DataFrame, trading_days: int = TRADING_DAYS_PER_YEAR):
    """Compounded annualized return: (1 + mean daily return)^252 - 1, same formula
    already used in notebooks/03_eda_market.ipynb.
    """
    return (1 + returns.mean()) ** trading_days - 1


def annualized_volatility(returns: pd.DataFrame, trading_days: int = TRADING_DAYS_PER_YEAR):
    """Annualized volatility: daily std * sqrt(252)."""
    return returns.std() * np.sqrt(trading_days)


def sharpe_ratio(returns: pd.DataFrame, risk_free_rate: float = INDIA_RISK_FREE_RATE,
                  trading_days: int = TRADING_DAYS_PER_YEAR):
    """Annualized Sharpe ratio: (annualized return - risk-free rate) / annualized volatility.

    Works on a Series (single ticker/portfolio) or DataFrame (one column per ticker) -
    pandas broadcasts .mean()/.std() per column either way.
    """
    return (annualized_return(returns, trading_days) - risk_free_rate) / annualized_volatility(returns, trading_days)


def risk_return_summary(returns: pd.DataFrame, risk_free_rate: float = INDIA_RISK_FREE_RATE,
                         trading_days: int = TRADING_DAYS_PER_YEAR) -> pd.DataFrame:
    """One row per column of `returns`: annualized return/volatility (%) and Sharpe ratio."""
    return pd.DataFrame({
        "annualized_return_pct": annualized_return(returns, trading_days) * 100,
        "annualized_volatility_pct": annualized_volatility(returns, trading_days) * 100,
        "sharpe_ratio": sharpe_ratio(returns, risk_free_rate, trading_days),
    }).sort_values("sharpe_ratio", ascending=False)


def correlation_matrix(returns: pd.DataFrame, method: str = "pearson") -> pd.DataFrame:
    """Cross-ticker return correlation matrix (pairwise-complete, pandas default)."""
    return returns.corr(method=method)
