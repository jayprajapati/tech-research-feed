import os
import json
import re
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from openai import OpenAI
from schema import Report, Section, Table, Card
from blob_writer import upload_report, update_index


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    default_headers={"HTTP-Referer": "https://github.com/jayprajapati/trader-news"},
)
model = os.environ.get("MODEL", "nvidia/nemotron-3-super-120b-a12b:free")


def fetch_json(url: str) -> dict | list:
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


SECTORS = [
    ("nifty_it", "%5ECNXIT"),
    ("nifty_pharma", "%5ECNXPHARMA"),
    ("nifty_auto", "%5ECNXAUTO"),
    ("nifty_fmcg", "%5ECNXFMCG"),
    ("nifty_metal", "%5ECNXMETAL"),
    ("nifty_realty", "%5ECNXREALTY"),
    ("nifty_media", "%5ECNXMEDIA"),
    ("nifty_energy", "%5ECNXENERGY"),
    ("nifty_infra", "%5ECNXINFRA"),
]


def get_market_data() -> dict:
    def price_and_change(d):
        try:
            meta = d["chart"]["result"][0]["meta"]
            p = meta["regularMarketPrice"]
            pc = meta.get("chartPreviousClose") or meta.get("previousClose")
            return {"price": p, "change_pct": round(((p - pc) / pc) * 100, 2) if pc else None}
        except Exception:
            return None

    data = {}
    for name, sym in [("nifty", "%5ENSEI"), ("bank_nifty", "%5ENSEBANK"), ("sensex", "%5EBSESN")]:
        d = fetch_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}")
        data[name] = price_and_change(d)

    for name, sym in SECTORS:
        d = fetch_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}")
        data[name] = price_and_change(d)

    return data


STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "BAJFINANCE.NS", "LT.NS", "WIPRO.NS", "TITAN.NS", "AXISBANK.NS",
    "MARUTI.NS", "SUNPHARMA.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS",
    "NESTLEIND.NS", "ULTRACEMCO.NS", "HCLTECH.NS", "TATAMOTORS.NS", "M&M.NS",
    "BAJAJFINSV.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "COALINDIA.NS",
    "ADANIPORTS.NS", "ADANIENT.NS", "GRASIM.NS", "EICHERMOT.NS", "CIPLA.NS",
    "BRITANNIA.NS", "DRREDDY.NS", "HDFCLIFE.NS", "SBILIFE.NS", "ASIANPAINT.NS",
    "TRENT.NS", "BAJAJHLDNG.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "HEROMOTOCO.NS",
    "BEL.NS", "HAL.NS", "PIDILITIND.NS", "DABUR.NS", "ICICIPRULI.NS",
]


def scan_stocks(concurrent: int = 15) -> dict:
    def fetch(sym):
        d = fetch_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}")
        try:
            m = d["chart"]["result"][0]["meta"]
            return {
                "symbol": sym.replace(".NS", ""),
                "price": m.get("regularMarketPrice"),
                "high52w": m.get("fiftyTwoWeekHigh"),
                "low52w": m.get("fiftyTwoWeekLow"),
                "volume": m.get("regularMarketVolume"),
                "prev_close": m.get("chartPreviousClose") or m.get("previousClose"),
            }
        except Exception:
            return None

    results = []
    with ThreadPoolExecutor(max_workers=concurrent) as pool:
        fut = {pool.submit(fetch, sym): sym for sym in STOCKS}
        for f in as_completed(fut):
            r = f.result()
            if r:
                results.append(r)

    def pct_from(v, ref):
        return round(((v - ref) / ref) * 100, 2) if v and ref else None

    for r in results:
        r["from_high_pct"] = pct_from(r["price"], r["high52w"])
        r["from_low_pct"] = pct_from(r["price"], r["low52w"])
        del r["prev_close"]

    near_high = [r for r in results if r["from_high_pct"] is not None and r["from_high_pct"] >= -5]
    near_low = [r for r in results if r["from_low_pct"] is not None and r["from_low_pct"] <= 5 and r["from_high_pct"] < -5]
    near_high.sort(key=lambda x: x["from_high_pct"], reverse=True)
    near_low.sort(key=lambda x: x["from_low_pct"])

    return {"near_52wk_high": near_high[:8], "near_52wk_low": near_low[:5]}


SYSTEM_PROMPT = """You are an Institutional Swing Trader and Quantitative Portfolio Strategist for Indian Equity Markets (NSE). Generate a structured daily market report.

Live market data (indices with prices and % changes) is provided. Use it with your training knowledge of recent market patterns, sector rotation, FII/DII trends, and catalysts.

Output a JSON report following this schema. The "type" field for sections can be "text" (simple paragraph), "table" (structured with headers/rows), or "cards" (list of items with name/reasoning/metrics). For stock recommendations use "cards" type.

Required sections (in this order):

1. Market Context — Nifty/Bank Nifty/Sensex levels, trend (above/below 20 EMA), weekly change, FII/DII flow summary, key macro catalysts.

2. Sectoral Heatmap — table ranking all sectors by % change (top to bottom). Identify top 3 sectors with capital rotation INTO, bottom 3 with capital rotation OUT OF. Note any sector showing reversal signals. Include cap-size rotation (Midcap/Smallcap vs Nifty 50).

3. 52-Week High/Low Scan — cards with stock names from the provided live scan data. For each: price, distance from 52w high (%), volume. Rate as Tier 1 (within 2% of 52w high + sector tailwind), Tier 2 (within 5% of 52w high), or Tier 3 (near 52w low showing reversal potential + volume confirmation).

4. Swing Trade Picks — cards with specific entries:
   - Each pick: name, tier, entry zone, stop-loss, target, rationale, R:R ratio
   - Max 4-5 picks. Each max 10-12% position sizing.
   - Include time-stop rule (exit if flat after 3-4 sessions).
   - Never pick stocks in structural downtrend.

5. Technical Outlook — key support/resistance levels for Nifty, Bank Nifty. Market kill-switch level (Nifty below key support = reduce exposure). RSI, trend indicators.

JSON schema:
{
  "date": "YYYY-MM-DD",
  "type": "daily-pulse",
  "title": "concise title",
  "tags": ["nifty", "fii-dii", "sector-rotation"],
  "summary": "2-3 sentence overview with key takeaway",
  "slug": "daily-pulse",
  "sections": [
    {
      "heading": "Market Context",
      "content": "paragraph text",
      "type": "text"
    },
    {
      "heading": "Sectoral Heatmap",
      "content": {
        "headers": ["Sector", "Change %", "Trend"],
        "rows": [["Nifty IT", "+1.2", "Bullish"], ["Nifty Pharma", "-0.3", "Neutral"]],
        "caption": "Sectors ranked by performance with rotation commentary"
      },
      "type": "table"
    },
    {
      "heading": "52-Week High/Low Scan",
      "content": [
        {"name": "Stock Name", "tier": "Tier 1", "reasoning": "Breakout with 2x volume, sector tailwind", "metrics": {"Price": "2450", "Volume": "2.5x avg", "Delivery": "62%", "52W High": "2480"}},
        {"name": "Stock Name", "tier": "Tier 2", "reasoning": "Good setup, needs sector confirmation", "metrics": {"Price": "890", "Volume": "1.8x avg", "Delivery": "55%"}}
      ],
      "type": "cards"
    },
    {
      "heading": "Swing Trade Picks",
      "content": [
        {"name": "Stock Name", "tier": "Tier 1", "reasoning": "Strong breakout, sector tailwind, institutional accumulation. Entry 2450-2470, SL 2380, T1 2550 T2 2620. R:R 1:2.1", "metrics": {"Entry": "2450-2470", "Stop Loss": "2380", "Target 1": "2550", "Target 2": "2620", "R:R": "1:2.1"}},
        {"name": "Stock Name 2", "tier": "Tier 2", "reasoning": "Base breakout, needs volume confirmation. Entry 890-900, SL 865, T1 940.", "metrics": {"Entry": "890-900", "Stop Loss": "865", "Target": "940", "R:R": "1:1.8"}}
      ],
      "type": "cards"
    },
    {
      "heading": "Technical Outlook",
      "content": "Nifty support 23800, resistance 24200. RSI 58, room for upside. Market kill-switch: close below 23600 reduce 50%.",
      "type": "text"
    }
  ],
  "generatedAt": "ISO timestamp",
  "model": "string"
}

Trading Rules (NEVER violate):
- R:R minimum 1:2. No exceptions.
- Position sizing: max 10-12% per trade.
- Hard stop-loss. No averaging down.
- Time-stop: exit if flat after 3-4 days.
- No earnings gambles — exit before Q results.
- Max 2-3 stocks from same sector.
- Volume confirmation: >1.5x avg weekly volume for breakouts.
- Only buy above 20 EMA or Stage 1 breakout.

IMPORTANT: Return ONLY valid JSON. No markdown wrapping or explanation."""


def generate_report(report_type: str, report_date: str | None = None) -> Report:
    today = report_date or date.today().isoformat()
    market_data = get_market_data()
    fifty_two_scan = scan_stocks()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Generate a {report_type} report for {today}.\n\nLive Market Data (indices):\n{json.dumps(market_data, indent=2)}\n\n52-Week High/Low Stock Scan (live from Yahoo Finance):\n{json.dumps(fifty_two_scan, indent=2)}"},
        ],
    )

    raw = response.choices[0].message.content
    try:
        decoder = json.JSONDecoder()
        start = raw.index("{")
        data, _ = decoder.raw_decode(raw, start)
    except (json.JSONDecodeError, ValueError):
        raw = raw.replace("'", '"').replace("True","true").replace("False","false").replace("None","null")
        raw = re.sub(r",\s*}", "}", raw)
        decoder = json.JSONDecoder()
        start = raw.index("{")
        data, _ = decoder.raw_decode(raw, start)
    data["date"] = today
    data["slug"] = report_type
    data["generatedAt"] = datetime.utcnow().isoformat() + "Z"
    data["model"] = model

    return Report(**data)


if __name__ == "__main__":
    report_type = os.environ.get("REPORT_TYPE", "daily-pulse")
    report_date = os.environ.get("REPORT_DATE")
    report = generate_report(report_type, report_date)
    upload_report(report)
    update_index(report)
    print(f"Published {report.date}/{report.slug}.json")
