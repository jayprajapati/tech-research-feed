import os
import json
from datetime import date, datetime
from openai import AzureOpenAI
from schema import Report, Section, Table, Card
from blob_writer import upload_report, update_index


client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_KEY"],
    api_version="2024-08-01-preview",
)
model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")


SYSTEM_PROMPT = """You are a professional equity research analyst specializing in Indian markets (NSE).
Your task is to research and generate a structured daily market report.

Use the Bing search tool to find current data on:
1. Nifty/Bank Nifty levels, trend, and key moves
2. FII/DII flow data
3. Sector performance and rotation
4. 52-week high/low breakout candidates
5. Key news catalysts

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
  "model": "gpt-4o"
}

IMPORTANT: Return ONLY valid JSON. No markdown wrapping, no explanation."""


def generate_report(report_type: str, report_date: str | None = None) -> Report:
    today = report_date or date.today().isoformat()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Generate a {report_type} for {today}. Research current market data online using Bing search."},
        ],
        tools=[{
            "type": "bing_search",
        }],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)
    # Inject date/slug if not provided by model
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
