import requests
import pandas as pd
from datetime import datetime, timedelta
import os


# -----------------------------
# SETTINGS
# -----------------------------

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

DATA_FILE = "data/nyc_construction_leads.xlsx"
SEEN_FILE = "data/seen_jobs.csv"

API_URL = "https://data.cityofnewyork.us/resource/rvhx-8trz.json"


# -----------------------------
# GET RECENT NYC PERMITS
# -----------------------------

days_back = 7

date_limit = (
    datetime.now() - timedelta(days=days_back)
).strftime("%Y-%m-%d")


params = {
    "$limit": 5000,
    "$where": f"pre__filing_date > '{date_limit}'"
}


print("Downloading NYC construction data...")


response = requests.get(
    API_URL,
    params=params
)

response.raise_for_status()

data = response.json()


df = pd.DataFrame(data)


if df.empty:
    print("No permits found")
    exit()


# -----------------------------
# FILTER GOOD LEADS
# -----------------------------

if "job_type" in df.columns:

    df = df[
        df["job_type"].isin(
            [
                "NB",
                "ALT-1"
            ]
        )
    ]


if "job_status" in df.columns:

    df = df[
        df["job_status"].isin(
            [
                "PRE-FILED",
                "FILED",
                "IN REVIEW",
                "PLAN EXAM",
                "APPROVED"
            ]
        )
    ]


if df.empty:
    print("No suitable leads")
    exit()


# -----------------------------
# REMOVE OLD JOBS
# -----------------------------

os.makedirs(
    "data",
    exist_ok=True
)


if os.path.exists(SEEN_FILE):

    seen = pd.read_csv(SEEN_FILE)

    seen_jobs = set(
        seen["job__"].astype(str)
    )

else:

    seen_jobs = set()


df["job__"] = df["job__"].astype(str)


new_leads = df[
    ~df["job__"].isin(seen_jobs)
]


if new_leads.empty:

    print("No new leads")
    exit()


# -----------------------------
# SAVE EXCEL
# -----------------------------

new_leads.to_excel(
    DATA_FILE,
    index=False
)


# Update memory file

all_seen = pd.DataFrame(
    {
        "job__": list(
            seen_jobs.union(
                set(new_leads["job__"])
            )
        )
    }
)


all_seen.to_csv(
    SEEN_FILE,
    index=False
)


# -----------------------------
# DISCORD ALERT
# -----------------------------


message = (
    "🏗️ **NYC Construction Leads**\n"
    f"📅 {datetime.now().strftime('%d/%m/%Y')}\n\n"
)


for _, row in new_leads.head(10).iterrows():

    address = (
        str(row.get("house__", ""))
        + " "
        + str(row.get("street_name", ""))
    )


    owner = row.get(
        "owner_s_business_name",
        "Unknown"
    )


    cost = row.get(
        "initial_cost",
        "Unknown"
    )


    job_type = row.get(
        "job_type",
        ""
    )


    message += (
        f"🆕 **{job_type}**\n"
        f"📍 {address}\n"
        f"🏢 Owner: {owner}\n"
        f"💰 Cost: {cost}\n\n"
    )


if DISCORD_WEBHOOK:

    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": message
        }
    )


print(
    f"Sent {len(new_leads)} new leads"
)
