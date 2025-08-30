import requests, feedparser
from bs4 import BeautifulSoup

UA = {"User-Agent": "your-email@example.com AI-Risk-Report-Demo"}  # Replace with your real contact email per SEC rules

def fetch_sec_filings_atom(company_or_cik: str, count: int = 10):
    """Fetch recent SEC filings via EDGAR Atom feed. Returns (items, url)."""
    url = ("https://www.sec.gov/cgi-bin/browse-edgar"
           f"?action=getcompany&company={company_or_cik}&owner=exclude&count={count}&output=atom")
    try:
        resp = requests.get(url, headers=UA, timeout=12)
        feed = feedparser.parse(resp.text)
        items = [{
            "title": e.title,
            "link": e.link,
            "updated": getattr(e, "updated", ""),
        } for e in feed.entries[:count]]
        if not items:
            url2 = ("https://www.sec.gov/cgi-bin/browse-edgar"
                    f"?action=getcompany&CIK={company_or_cik}&owner=exclude&count={count}&output=atom")
            resp2 = requests.get(url2, headers=UA, timeout=12)
            feed2 = feedparser.parse(resp2.text)
            items = [{
                "title": e.title,
                "link": e.link,
                "updated": getattr(e, "updated", ""),
            } for e in feed2.entries[:count]]
            return items, url2
        return items, url
    except Exception as e:
        return ([{"title": f"SEC fetch error: {e}", "link": "", "updated": ""}], url)

def fetch_asx_announcements(issuer_code: str, limit: int = 10):
    """Lightweight scrape of ASX announcements page; fallback to Google News RSS if structure changes."""
    base = "https://www2.asx.com.au/markets/trade-our-cash-market/announcements"
    try:
        r = requests.get(base, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            txt = a.get_text(strip=True)
            if issuer_code.upper() in (txt or "").upper() or issuer_code.upper() in href.upper():
                if href.startswith("/"):
                    href = "https://www2.asx.com.au" + href
                items.append({"title": txt or "ASX announcement", "link": href})
                if len(items) >= limit:
                    break
        if not items:
            rss = f"https://news.google.com/rss/search?q=site:asx.com.au+{issuer_code}+announcement"
            feed = feedparser.parse(rss)
            for e in feed.entries[:limit]:
                items.append({"title": e.title, "link": e.link})
        return items, base
    except Exception as e:
        return ([{"title": f"ASX fetch error: {e}", "link": ""}], base)
