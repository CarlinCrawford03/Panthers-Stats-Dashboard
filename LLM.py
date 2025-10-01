import os
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from openai import OpenAI
from supabase import create_client, Client
import httpx
from dotenv import load_dotenv

# -------------------------------
# --- Load environment variables ---
# -------------------------------
load_dotenv()

endpoint = os.getenv("OPENAI_ENDPOINT")
api_key = os.getenv("OPENAI_API_KEY")
deployment_name = os.getenv("OPENAI_DEPLOYMENT")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# -------------------------------
# --- Setup OpenAI client ---
# -------------------------------
client = OpenAI(base_url=endpoint, api_key=api_key)

# -------------------------------
# --- Setup Supabase client ---
# -------------------------------
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client created")
except httpx.ConnectError as e:
    print(f"❌ Supabase connection failed: {e}")
    supabase = None
except Exception as e:
    print(f"⚠ Unexpected Supabase error: {e}")
    supabase = None

# -------------------------------
# --- Create data directory ---
# -------------------------------
os.makedirs("data", exist_ok=True)

# -------------------------------
# --- Collector: Scrape Panthers stats ---
# -------------------------------
url = "https://www.panthers.com/team/stats/"
try:
    response = requests.get(url)
    response.raise_for_status()
except requests.RequestException as e:
    print(f"❌ Failed to fetch Panthers stats: {e}")
    exit(1)

soup = BeautifulSoup(response.text, "html.parser")
tables = soup.find_all("table")

raw_blob = ""
for table in tables:
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    if headers:
        raw_blob += " | ".join(headers) + "\n"
    for row in table.find_all("tr"):
        cols = [td.get_text(strip=True) for td in row.find_all("td")]
        if cols:
            raw_blob += " | ".join(cols) + "\n"

with open("data/raw_blob.txt", "w", encoding="utf-8") as f:
    f.write(raw_blob)
print("✅ Raw blob saved to data/raw_blob.txt")

# -------------------------------
# --- Structurer: LLM ➜ JSON ---
# -------------------------------
schema_description = """
Return valid JSON with this schema:

{
  "id": "string (unique identifier, e.g. 'panthers-stats-2025')",
  "title": "string (title of the dataset)",
  "summary": "string (1-2 sentence summary of the stats)",
  "source_url": "string (URL the data came from)",
  "extracted_at": "string (ISO8601 UTC timestamp)",
  "tables": [
    {
      "table_name": "string",
      "rows": [
        {
          "column_name": "value"
        }
      ]
    }
  ]
}
Only output valid JSON. Do not include Markdown code fences or extra text.
"""

try:
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": "You are a data cleaning assistant. Only output valid JSON."},
            {"role": "user", "content": f"Here is some raw table data scraped from the Panthers website:\n\n{raw_blob}\n\n{schema_description}"}
        ]
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1].strip()

    parsed_json = json.loads(content)
    parsed_json.setdefault("source_url", url)
    parsed_json.setdefault("extracted_at", datetime.utcnow().isoformat())

    with open("data/panthers_stats_structured.json", "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2)
    print("✅ Structured JSON saved to data/panthers_stats_structured.json")
except Exception as e:
    print(f"❌ Failed to structure JSON: {e}")
    exit(1)

# -------------------------------
# --- Preview first table ---
# -------------------------------
if "tables" in parsed_json and parsed_json["tables"]:
    print("\n📊 Preview first table:")
    first_table = parsed_json["tables"][0]
    for row in first_table["rows"][:3]:
        print(row)

# -------------------------------
# --- Loader: JSON ➜ DataFrame ➜ Supabase ---
# -------------------------------
dfs = {}
for table in parsed_json.get("tables", []):
    table_name = table["table_name"].lower().replace(" ", "_")
    if table_name.endswith("_stats"):
        table_name = table_name.replace("_stats", "")
    if table_name == "defensive":
        table_name = "defense"

    df = pd.DataFrame(table["rows"])
    df["updated_at"] = datetime.utcnow().isoformat()
    dfs[table_name] = df

    print(f"\n📊 DataFrame for {table_name}:")
    print(df.head())

    if supabase is None:
        print(f"⚠ Skipping upsert for {table_name} because Supabase is not connected")
        continue

    rows = df.to_dict(orient="records")
    for row in rows:
        try:
            supabase.table(table_name).upsert(row).execute()
        except httpx.ConnectError as e:
            print(f"❌ Failed to upsert row into {table_name}: {e}")
        except Exception as e:
            print(f"⚠ Unexpected error for {table_name}: {e}")
    print(f"✅ Attempted upsert for {table_name}, {len(rows)} rows")