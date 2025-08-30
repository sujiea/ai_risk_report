import numpy as np
import pandas as pd

def compute_risk_metrics(prices: pd.DataFrame) -> dict:
    """Core risk metrics for individual tickers."""
    rets = prices.pct_change().dropna()
    ann_factor = 252.0
    vol = rets.std() * np.sqrt(ann_factor)
    sharpe = rets.mean() / rets.std() * np.sqrt(ann_factor)
    # Max drawdown per-asset
    mdd = {}
    for c in prices.columns:
        x = prices[c].dropna()
        cummax = x.cummax()
        dd = (x / cummax - 1.0).min()
        mdd[c] = float(dd)
    corr = rets.corr()
    return {
        "returns": rets,
        "ann_vol": vol.sort_values(ascending=False),
        "sharpe": sharpe.sort_values(ascending=False),
        "mdd": pd.Series(mdd).sort_values(),
        "corr": corr,
    }

def compute_portfolio_returns(prices: pd.DataFrame, weights: pd.Series | None = None) -> pd.Series:
    """Equal-weight portfolio daily returns unless weights provided."""
    rets = prices.pct_change().dropna()
    if weights is None:
        weights = pd.Series(1.0/len(rets.columns), index=rets.columns)
    weights = weights.reindex(rets.columns).fillna(0.0)
    port = rets.dot(weights)
    return port

def var_es(port_rets: pd.Series, alphas=(0.95, 0.99)) -> pd.DataFrame:
    """Historical-simulation VaR/ES on daily returns; outputs positive loss numbers."""
    out = {}
    losses = -port_rets.dropna()  # positive = loss
    for a in alphas:
        var = losses.quantile(a)
        tail = losses[losses >= var]
        es = tail.mean() if len(tail) else float("nan")
        out[f"VaR@{int(a*100)}"] = var
        out[f"ES@{int(a*100)}"] = es
    return pd.DataFrame(out, index=["Portfolio"]).T

def stress_scenarios(prices: pd.DataFrame, weights: pd.Series | None = None, shocks=(-0.05, -0.10, -0.20)) -> pd.DataFrame:
    """Uniform equity shocks (-5%, -10%, -20%). Returns portfolio P&L (%) per shock."""
    if weights is None:
        weights = pd.Series(1.0/len(prices.columns), index=prices.columns)
    weights = weights.reindex(prices.columns).fillna(0.0)
    res = {}
    for s in shocks:
        res[f"Shock {int(s*100)}%"] = pd.Series({"Portfolio": s*100.0})
    df = pd.DataFrame(res).T
    return df

def historical_worst_days(port_rets: pd.Series, k: int = 5) -> pd.DataFrame:
    """Worst k daily returns; include percentage loss."""
    w = port_rets.nsmallest(k).to_frame(name="Return")
    w["Loss(%)"] = -w["Return"]*100.0
    return w

def to_markdown_table(df: pd.DataFrame, title: str) -> str:
    if df is None or df.empty:
        return f"### {title}\n_No data_\n"
    md = f"### {title}\n\n" + df.to_markdown()
    return md + "\n"
