import os
import json
import re
import httpx
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


def get_market_data() -> dict:
    nifty = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI")
    banknifty = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEBANK")
    sensex = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/%5EBSESN")

    def price(d):
        try:
            return d["chart"]["result"][0]["meta"]["regularMarketPrice"]
        except Exception:
            return None

    return {
        "nifty": price(nifty),
        "bank_nifty": price(banknifty),
        "sensex": price(sensex),
    }


SYSTEM_PROMPT = """You are a professional equity research analyst specializing in Indian markets (NSE).
Your task is to generate a structured daily market report.

Live market data (Nifty, Bank Nifty, Sensex levels) is provided in the user message.
Use it along with your training knowledge of recent market patterns, sector rotation,
FII/DII trends, and catalysts to build a comprehensive report.

Output a JSON report following this schema:
{
  "date": "YYYY-MM-DD",
  "type": "daily-pulse",
  "title": "string",
  "tags": ["nifty", "fii-dii"],
  "summary": "2-3 sentence overview",
  "slug": "daily-pulse",
  "sections": [
    {
      "heading": "Market Context",
      "content": "text string or table or list of cards",
      "type": "text|table|cards|ranking"
    }
  ],
  "generatedAt": "ISO timestamp",
  "model": "string"
}

IMPORTANT: Return ONLY valid JSON. No markdown wrapping, no explanation."""


def generate_report(report_type: str, report_date: str | None = None) -> Report:
    today = report_date or date.today().isoformat()
    market_data = get_market_data()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Generate a {report_type} report for {today}.\n\nLive Market Data:\n{json.dumps(market_data, indent=2)}"},
        ],
    )

    raw = response.choices[0].message.content
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    data = json.loads(m.group() if m else raw)
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
