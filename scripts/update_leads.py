import requests
import pandas as pd
from datetime import datetime, timedelta
import os

# NYC Open Data DOB NOW Build dataset
URL = "https://data.cityofnewyork.us/resource/rvhx-8trz.json"

# Look back 30 days
date_limit = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

params = {
    "$limit": 5000,
    "$where": f"filing_date > '{date_limit}'"
}

print("Downloading NYC DOB data...")

response = requests.get(URL, params=params)
data = response.json()

df = pd.DataFrame(data)

if df.empty:
    print("No new applications found")
    exit()

# Keep valuable jobs
keep_types = [
    "NB",
    "ALT-1",
    "ALT-2"
]

if "job_type" in df.columns:
    df = df[df["job_type"].isin(keep_types)]


# Keep active jobs
active_status = [
    "PRE-FILED",
    "FILED",
    "IN REVIEW",
    "PLAN EXAM",
    "APPROVED"
]

if "job_status" in df.columns:
    df = df[df["job_status"].isin(active_status)]


# Sort newest first
if "filing_date" in df.columns:
    df = df.sort_values(
        "filing_date",
        ascending=False
    )


# Save Excel
os.makedirs("data", exist_ok=True)

output = "data/nyc_construction_leads.xlsx"

df.to_excel(
    output,
    index=False
)

print(f"Saved {len(df)} leads")
