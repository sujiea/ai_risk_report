import os, requests
from bs4 import BeautifulSoup
from typing import Optional, List

def fetch_url_text(url: str, max_len: int = 20000, timeout: int = 15) -> str:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "AI-Risk-Report/1.0 (contact: you@example.com)"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:max_len]
    except Exception as e:
        return f"[FETCH_ERROR] {url}: {e}"

def llm_summarize(text: str, url: str, api_key: Optional[str], model: str = "gpt-4o-mini") -> str:
    """Summarize a disclosure/article into risk-relevant bullets via OpenAI. If no key, return a disabled note."""
    if not api_key:
        return f"- {url}\n  - [LLM disabled] Provide OpenAI API key to enable summaries.\n"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = f"""
You are a risk analyst. Summarize the following disclosure/article into 3-5 concise bullets.
- Focus on risk-relevant points, numbers, timelines, regulatory/compliance implications.
- Keep it factual; avoid speculation.
- End with a one-line takeaway.
TEXT BEGIN
{text[:6000]}
TEXT END
Include the source URL inline.
"""
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You write concise, factual risk summaries."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=450,
        )
        out = resp.choices[0].message.content.strip()
        if url not in out:
            out += f"\n(Source: {url})"
        return out
    except Exception as e:
        return f"- {url}\n  - [LLM_ERROR] {e}\n"

def summarize_urls(urls: List[str], api_key: Optional[str], max_items: int = 3) -> str:
    urls = [u for u in urls if u][:max_items]
    md_parts = []
    for u in urls:
        text = fetch_url_text(u)
        md = llm_summarize(text, u, api_key=api_key)
        md_parts.append(md)
    return "\n\n".join(md_parts)
