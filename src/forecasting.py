"""ARIMA forecasting for Nifty ticker / equal-weighted portfolio index prices.

ARIMA (statsmodels), not Prophet, despite both being listed in requirements.txt: each
ticker has ~1,239 daily observations (reports/data_inventory.md - 6,195 rows / 5 tickers),
and after a chronological holdout there are ~1,100-1,200 training days left. That's short
for Prophet's changepoint/holiday machinery to add anything over a plain ARIMA, and pulls in
a heavier compiled (cmdstan) backend for no clear benefit at this data volume - ARIMA is the
more honest choice here, not just the more convenient one.

Every split in this module is chronological: train_holdout_split() takes the *last*
`holdout_days` rows as holdout, never a random sample - shuffling daily price data would
leak future information into training and make the evaluation meaningless.

Headline honesty note (mirrors the credit risk leakage write-up and the segmentation
module's caveats): stock prices are close to a random walk, so the naive last-value
baseline (tomorrow's price = today's price) is a genuinely hard bar to beat, not a
strawman. Where ARIMA's RMSE/MAPE come out close to or worse than the naive baseline's in
notebooks/07_var_and_forecasting.ipynb, that is reported as-is rather than reframed as a
win - a short daily series with no strong seasonal or trend structure is not fertile ground
for beating a random walk, and claiming otherwise would overstate what this model can do.

RANDOM_STATE is kept for consistency with the rest of the project (customer_segmentation.py,
fraud_detection.py) even though statsmodels' ARIMA fit here is a deterministic MLE with no
random component to seed.
"""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

import market_risk as mr

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

HOLDOUT_DAYS = 60  # ~3 trading months, held out chronologically
SEASONAL_LAG_DAYS = 5  # 1 trading week, for the "same day last week" naive baseline


def train_holdout_split(series: pd.Series, holdout_days: int = HOLDOUT_DAYS):
    """Last `holdout_days` observations become the holdout, in original chronological
    order - no shuffling, no random sampling.
    """
    series = series.dropna().sort_index()
    if holdout_days >= len(series):
        raise ValueError(f"holdout_days={holdout_days} >= series length {len(series)}")
    return series.iloc[:-holdout_days], series.iloc[-holdout_days:]


def select_arima_order(train: pd.Series, p_range=range(0, 3), d_range=(0, 1),
                        q_range=range(0, 3)) -> tuple:
    """Grid search (p,d,q) by in-sample AIC, fit on the training series only - the
    holdout is never touched during model selection, so this can't leak into evaluation.
    Small grid (up to 3x2x3=18 combos), cheap enough given the short series; combinations
    that fail to converge are skipped rather than raising.

    Orders capped at 2 deliberately: in-sample AIC alone has no way to penalize a
    multi-step forecast that diverges once extrapolated - higher-order (3+) fits on a
    ~1,100-day noisy daily series occasionally win AIC by a hair while producing an
    unstable, exploding 60-day-ahead forecast. Capping at 2 trades a small amount of
    in-sample fit for forecasts that stay numerically sane, which matters more here.
    """
    best_aic, best_order = np.inf, (1, 1, 0)
    for p in p_range:
        for d in d_range:
            for q in q_range:
                if p == 0 and q == 0:
                    continue
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        fit = ARIMA(train, order=(p, d, q)).fit()
                    if fit.aic < best_aic:
                        best_aic, best_order = fit.aic, (p, d, q)
                except Exception:
                    continue
    return best_order


def fit_arima(train: pd.Series, order: tuple):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ARIMA(train, order=order).fit()


def forecast_arima(model_fit, steps: int, index) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        forecast = model_fit.forecast(steps=steps)
    return pd.Series(np.asarray(forecast), index=index, name="arima")


def naive_last_value_forecast(train: pd.Series, holdout_index) -> pd.Series:
    """Random-walk baseline: every holdout-period forecast equals the last observed
    training value, frozen for the whole horizon. For daily equity prices this is the
    standard, genuinely hard-to-beat baseline (efficient-market / random-walk assumption) -
    and it's the fair, apples-to-apples comparison against ARIMA's forecast here, since both
    use only information available at the train/holdout cutoff and never update.
    """
    return pd.Series(train.iloc[-1], index=holdout_index, name="naive_last_value")


def naive_seasonal_forecast(full_series: pd.Series, holdout_index, lag: int = SEASONAL_LAG_DAYS) -> pd.Series:
    """Seasonal-naive baseline: forecast(t) = actual value `lag` trading days earlier
    (default 5 = same day last week). Uses `full_series` (train + holdout) so the lagged
    lookup can reach back across the train/holdout boundary; only ever reads values that
    chronologically precede the date being forecast, so it stays leakage-free.

    Not an apples-to-apples comparison with the static h-step ARIMA/naive_last_value
    forecasts, though: this baseline keeps consuming real, continuously-updating holdout
    data as it walks forward, while ARIMA's forecast is generated once from the train
    cutoff and never refreshed. It will tend to look strong for that structural reason
    alone, regardless of whether stock prices have real weekly seasonality - report it
    as "a walk-forward baseline with a data-recency advantage," not "the model needs to
    add weekly seasonality to catch up."
    """
    shifted = full_series.shift(lag)
    return shifted.reindex(holdout_index).rename("naive_seasonal")


def rmse(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mape(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)


def evaluation_table(actual: pd.Series, forecasts: dict) -> pd.DataFrame:
    """RMSE/MAPE for each named forecast series (e.g. {"arima": ..., "naive_last_value": ...})
    against the same holdout actuals, sorted best (lowest RMSE) first.
    """
    rows = []
    for name, pred in forecasts.items():
        pred = pred.reindex(actual.index)
        rows.append({"model": name, "rmse": rmse(actual, pred), "mape_pct": mape(actual, pred)})
    return pd.DataFrame(rows).sort_values("rmse").reset_index(drop=True)


def portfolio_price_index(engine, tickers: list = None, weights: dict = None,
                           base_value: float = 100.0) -> pd.Series:
    """Equal-weighted (unless `weights` given) portfolio price index, built by compounding
    mr.portfolio_returns() from `base_value` on a synthetic anchor date one business day
    before the first real observation - a level series ARIMA can forecast the same way it
    would forecast a single ticker's price.
    """
    returns = mr.load_returns_wide(engine, tickers)
    port_ret = mr.portfolio_returns(returns, weights)
    index = (1 + port_ret).cumprod() * base_value
    anchor_date = index.index[0] - pd.tseries.offsets.BDay(1)
    return pd.concat([pd.Series([base_value], index=[anchor_date]), index]).rename("portfolio_index")


def run_forecast(series: pd.Series, holdout_days: int = HOLDOUT_DAYS, order: tuple = None) -> dict:
    """End-to-end pipeline for one price series: chronological train/holdout split, ARIMA
    fit (order chosen by AIC grid search on train only, unless `order` is passed explicitly),
    naive last-value + naive seasonal baselines, and an evaluation table comparing all three
    against the same holdout actuals.
    """
    train, holdout = train_holdout_split(series, holdout_days)
    order = order or select_arima_order(train)
    model_fit = fit_arima(train, order)

    forecasts = {
        "arima": forecast_arima(model_fit, len(holdout), holdout.index),
        "naive_last_value": naive_last_value_forecast(train, holdout.index),
        "naive_seasonal": naive_seasonal_forecast(series, holdout.index),
    }
    metrics = evaluation_table(holdout, forecasts)

    return {
        "order": order,
        "train": train,
        "holdout": holdout,
        "forecasts": forecasts,
        "metrics": metrics,
        "model_fit": model_fit,
    }


def run_forecast_all(engine, tickers: list = None, holdout_days: int = HOLDOUT_DAYS,
                      include_portfolio: bool = True) -> dict:
    """run_forecast() for every ticker's adj_close (+ the equal-weighted portfolio index
    if include_portfolio), keyed by ticker name (and "portfolio").
    """
    tickers = list(tickers or mr.TICKERS)
    prices = mr.load_prices_wide(engine, tickers)

    results = {ticker: run_forecast(prices[ticker], holdout_days) for ticker in tickers}
    if include_portfolio:
        results["portfolio"] = run_forecast(portfolio_price_index(engine, tickers), holdout_days)
    return results
