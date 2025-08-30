import yfinance as yf
import pandas as pd

def fetch_esg_yahoo(ticker: str) -> pd.DataFrame | None:
    try:
        t = yf.Ticker(ticker)
        s = t.sustainability  # DataFrame for some tickers
        if s is None or (hasattr(s, "empty") and s.empty):
            return None
        if isinstance(s, pd.DataFrame):
            df = s.copy()
            df.columns = ["Value"]
            df.index.name = "Metric"
            return df
        return None
    except Exception:
        return None

def fetch_esg_for_tickers(tickers: list[str]) -> dict[str, pd.DataFrame | None]:
    out = {}
    for tk in tickers:
        out[tk] = fetch_esg_yahoo(tk)
    return out
