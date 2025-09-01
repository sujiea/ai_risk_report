import os
import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser, requests
from datetime import date, timedelta

from utils import (
    compute_risk_metrics, to_markdown_table,
    compute_portfolio_returns, var_es, stress_scenarios, historical_worst_days
)
from filings import fetch_sec_filings_atom, fetch_asx_announcements
from summarizer import summarize_urls
from pdf_export import markdown_to_pdf_bytes
from esg import fetch_esg_for_tickers

st.set_page_config(page_title="AI Risk Report (Web) – EN", page_icon="🧾", layout="wide")
st.title("🧾 AI Risk Report – Web (English)")
st.caption("Low-cost data sources -> risk analytics -> one-click report (Markdown/PDF) with sources.")

# Sidebar
with st.sidebar:
    tickers = st.text_input("Tickers (comma-separated)", "AAPL,MSFT,GOOG")
    start = st.date_input("Start date", date.today() - timedelta(days=365))
    news_query = st.text_input("News query (Google News RSS)", "bank risk liquidity")
    fred_series = st.text_input("FRED series (optional)", "DGS10")
    fred_api = st.text_input("FRED API key (optional)", "")
    sec_company = st.text_input("SEC company/CIK (optional)", "Microsoft")
    asx_code = st.text_input("ASX issuer code (optional)", "CBA")
    st.markdown("---")
    st.markdown("**Risk analytics**")
    do_var = st.checkbox("Compute VaR/ES (historical)", value=True)
    do_stress = st.checkbox("Stress scenarios (uniform shocks + worst days)", value=True)
    st.markdown("---")
    st.markdown("**ESG (Yahoo Sustainability)**")
    do_esg = st.checkbox("Fetch ESG metrics", value=False)
    st.markdown("---")
    st.markdown("**LLM (optional)**")
    use_llm = st.checkbox("Summarize SEC/ASX with LLM", value=False)
    openai_key = st.text_input("OpenAI API Key (optional)", type="password")
    st.caption("If empty, the app will try OPENAI_API_KEY environment variable.")
    submit = st.button("Run")

def fetch_prices(tickers: str, start):
    import pandas as pd, yfinance as yf

    syms = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not syms:
        return pd.DataFrame()

    # auto_adjust=True returns already-adjusted prices under "Close"
    data = yf.download(
        syms,
        start=str(start),
        progress=False,
        auto_adjust=True,
        threads=False,
    )

    if data is None or data.empty:
        return pd.DataFrame()

    # If single column DataFrame or Series
    if isinstance(data, pd.Series):
        close = data.to_frame(name=syms[0])
        return close

    # Try simple flat columns first
    if "Close" in data.columns:
        close = data["Close"]
    elif "Adj Close" in data.columns:
        close = data["Adj Close"]
    # Handle MultiIndex (level 0: field, level 1: ticker)
    elif isinstance(data.columns, pd.MultiIndex):
        lvl0 = set(data.columns.get_level_values(0))
        if "Close" in lvl0:
            close = data.xs("Close", axis=1, level=0, drop_level=True)
        elif "Adj Close" in lvl0:
            close = data.xs("Adj Close", axis=1, level=0, drop_level=True)
        else:
            # last fallback: pick the last level that looks like close
            candidates = [k for k in lvl0 if k.lower().startswith("close")]
            if candidates:
                close = data.xs(candidates[0], axis=1, level=0, drop_level=True)
            else:
                raise KeyError(f"No Close/Adj Close in columns: {lvl0}")
    else:
        raise KeyError(f"Unexpected columns: {list(data.columns)}")

    if isinstance(close, pd.Series):
        close = close.to_frame()

    # Clean up empty columns (e.g., invalid tickers)
    close = close.dropna(how="all", axis=1)

    if close.empty:
        raise ValueError("No usable close prices returned. Check tickers/date range or API throttling.")

    return close


from urllib.parse import quote_plus

def fetch_google_news(query: str):
    # Encode query so spaces and special chars are safe in the URL
    q = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}"
    feed = feedparser.parse(url)
    items = [(e.title, e.link) for e in feed.entries[:10]]
    return items, url

def fetch_fred(series_id, api_key):
    if not api_key:
        return None, None
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json"
    r = requests.get(url, timeout=12)
    try:
        js = r.json()
    except Exception:
        return None, url
    obs = js.get("observations", [])
    if not obs:
        return None, url
    df = pd.DataFrame(obs)[["date","value"]]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna().set_index("date")
    df.index = pd.to_datetime(df.index)
    return df, url

if submit:
    with st.spinner("Fetching data and computing analytics..."):
        prices = fetch_prices(tickers, start)
        st.subheader("Prices (Adj. Close, auto-adjusted)")
        st.dataframe(prices.tail())
        st.line_chart(prices)


        # Core metrics
        metrics = compute_risk_metrics(prices)
        ann_vol = metrics["ann_vol"].to_frame("Annualized Volatility")
        sharpe = metrics["sharpe"].to_frame("Sharpe (naive)")
        mdd = metrics["mdd"].to_frame("Max Drawdown")

        col1, col2, col3 = st.columns(3)
        with col1: st.dataframe(ann_vol)
        with col2: st.dataframe(sharpe)
        with col3: st.dataframe(mdd)

        st.subheader("Correlation Matrix")
        st.dataframe(metrics["corr"])

        # Portfolio analytics
        weights = None  # equal weight
        port = compute_portfolio_returns(prices, weights)
        if do_var:
            st.subheader("Portfolio VaR/ES (Historical Simulation)")
            var_df = var_es(port)
            st.dataframe(var_df)
        if do_stress:
            st.subheader("Stress Scenarios")
            st.markdown("Uniform price shocks and sample worst daily losses")
            shocks_df = stress_scenarios(prices, weights)
            st.dataframe(shocks_df)
            worst_df = historical_worst_days(port, k=5)
            st.dataframe(worst_df)

        # News
        news, news_url = fetch_google_news(news_query)
        st.subheader("Top News (Google News RSS)")
        for title, link in news:
            st.markdown(f"- [{title}]({link})")

        # FRED
        fred_df, fred_url = fetch_fred(fred_series, fred_api)
        if fred_df is not None:
            st.subheader(f"FRED: {fred_series}")
            st.line_chart(fred_df)

        # SEC & ASX
        sec_items, sec_url = ([], None)
        if sec_company:
            sec_items, sec_url = fetch_sec_filings_atom(sec_company, count=10)
            st.subheader("SEC Filings (Atom)")
            if sec_items:
                for it in sec_items:
                    st.markdown(f"- [{it.get('title','filing')}]({it.get('link','')})")

        asx_items, asx_url = ([], None)
        if asx_code:
            asx_items, asx_url = fetch_asx_announcements(asx_code, limit=10)
            st.subheader("ASX Announcements")
            if asx_items:
                for it in asx_items:
                    st.markdown(f"- [{it['title']}]({it['link']})")

        # Optional LLM summaries
        sec_urls = [it.get("link","") for it in sec_items][:5] if sec_items else []
        asx_urls = [it.get("link","") for it in asx_items][:5] if asx_items else []
        if use_llm and (sec_urls or asx_urls):
            st.subheader("AI Summaries (SEC/ASX)")
            api_key_eff = openai_key or os.getenv("OPENAI_API_KEY")
            sec_md = summarize_urls(sec_urls, api_key_eff, max_items=3) if sec_urls else ""
            asx_md = summarize_urls(asx_urls, api_key_eff, max_items=3) if asx_urls else ""
            if sec_md:
                st.markdown("**SEC**")
                st.markdown(sec_md)
            if asx_md:
                st.markdown("**ASX**")
                st.markdown(asx_md)

        # ESG (best-effort)
        esg_summaries = {}
        if do_esg:
            syms = [t.strip().upper() for t in tickers.split(",") if t.strip()]
            esg_map = fetch_esg_for_tickers(syms)
            st.subheader("ESG Metrics (Yahoo Sustainability)")
            for tk, df_esg in esg_map.items():
                st.markdown(f"**{tk}**")
                if df_esg is not None and not df_esg.empty:
                    st.dataframe(df_esg)
                    esg_summaries[tk] = df_esg.head(10)
                else:
                    st.info("No ESG data available for this ticker.")

        # Build markdown report
        md_parts = []
        md_parts.append(f"# Risk Report\n\n**Tickers:** {tickers}\n\n**Period Start:** {start}\n")
        md_parts.append(to_markdown_table(ann_vol, "Annualized Volatility"))
        md_parts.append(to_markdown_table(sharpe, "Sharpe (naive)"))
        md_parts.append(to_markdown_table(mdd, "Max Drawdown"))
        md_parts.append("### Correlation Matrix\n\n" + metrics["corr"].to_markdown() + "\n")
        if do_var:
            md_parts.append("\n## VaR / ES (Historical)\n")
            md_parts.append(var_df.to_markdown() + "\n")
        if do_stress:
            md_parts.append("\n## Stress Scenarios\n")
            md_parts.append(shocks_df.to_markdown() + "\n")
            md_parts.append("\n**Worst Daily Returns**\n\n")
            md_parts.append(worst_df.to_markdown() + "\n")
        if do_esg and esg_summaries:
            md_parts.append("\n## ESG Metrics (Yahoo Sustainability)\n")
            for tk, df_esg in esg_summaries.items():
                md_parts.append(f"\n**{tk}**\n")
                md_parts.append(df_esg.to_markdown() + "\n")
        if use_llm and (sec_urls or asx_urls):
            md_parts.append("\n## Disclosure Summaries (AI)\n")
            if sec_urls:
                md_parts.append("\n**SEC**\n")
                md_parts.append(sec_md + "\n")
            if asx_urls:
                md_parts.append("\n**ASX**\n")
                md_parts.append(asx_md + "\n")

        # Sources
        md_parts.append("## Sources\n")
        md_parts.append(f"- Yahoo Finance via `yfinance` for prices\n")
        md_parts.append(f"- Google News RSS: {news_url}\n")
        if fred_df is not None:
            md_parts.append(f"- FRED API: {fred_url}\n")
        if sec_items:
            md_parts.append(f"- SEC EDGAR Atom: {sec_url}\n")
        if asx_items:
            md_parts.append(f"- ASX Announcements: {asx_url}\n")

        report_md = "\n".join(md_parts)
        st.subheader("📄 Generated Markdown")
        st.code(report_md, language="markdown")
        st.download_button("Download report.md", data=report_md.encode("utf-8"), file_name="risk_report.md")

        # PDF export
        pdf_bytes = markdown_to_pdf_bytes(report_md)
        st.download_button("Download report.pdf", data=pdf_bytes, file_name="risk_report.pdf", mime="application/pdf")

else:
    st.info("Fill the sidebar and click **Run** to generate a report.")
