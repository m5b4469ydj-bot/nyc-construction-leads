import requests
import pandas as pd
from datetime import datetime, timedelta
import os


# -----------------------------
# SETTINGS
# -----------------------------

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

OUTPUT_FILE = "data/nyc_construction_leads.xlsx"
SEEN_FILE = "data/seen_jobs.csv"

API_URL = "https://data.cityofnewyork.us/resource/w9ak-ipjd.json"


# -----------------------------
# DOWNLOAD DATA
# -----------------------------

print("Downloading NYC DOB permits...")


params = {
    "$limit": 5000,
    "$order": "pre__filing_date DESC"
}


response = requests.get(
    API_URL,
    params=params
)

response.raise_for_status()

data = response.json()


df = pd.DataFrame(data)


if df.empty:
    print("No data returned")
    exit()


print(f"Downloaded {len(df)} records")


# -----------------------------
# DATE FILTER
# -----------------------------

if "pre__filing_date" in df.columns:

    df["pre__filing_date"] = pd.to_datetime(
        df["pre__filing_date"],
        errors="coerce"
    )


    cutoff = datetime.now() - timedelta(days=30)


    df = df[
        df["pre__filing_date"] >= cutoff
    ]


# -----------------------------
# FILTER CONSTRUCTION TYPES
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


# -----------------------------
# FILTER ACTIVE JOBS
# -----------------------------

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

    print("No matching construction leads")
    exit()


# -----------------------------
# CREATE LEAD SCORE
# -----------------------------


def score(row):

    points = 0


    if row.get("job_type") == "NB":
        points += 100

    elif row.get("job_type") == "ALT-1":
        points += 70


    try:

        cost = float(
            row.get(
                "initial_cost",
                0
            )
        )

        if cost > 1000000:
            points += 50

        elif cost > 500000:
            points += 25

    except:

        pass


    if row.get("building_type"):

        points += 10


    return points



df["lead_score"] = df.apply(
    score,
    axis=1
)


df = df.sort_values(
    "lead_score",
    ascending=False
)


# -----------------------------
# REMOVE OLD LEADS
# -----------------------------

os.makedirs(
    "data",
    exist_ok=True
)


if "job__" not in df.columns:

    print("No job numbers found")
    exit()



df["job__"] = df["job__"].astype(str)



if os.path.exists(SEEN_FILE):

    old = pd.read_csv(SEEN_FILE)

    seen = set(
        old["job__"].astype(str)
    )

else:

    seen = set()



new = df[
    ~df["job__"].isin(seen)
]


if new.empty:

    print("No new leads")
    exit()



# -----------------------------
# SAVE FILES
# -----------------------------

new.to_excel(
    OUTPUT_FILE,
    index=False
)



updated_seen = pd.DataFrame(
    {
        "job__": list(
            seen.union(
                set(new["job__"])
            )
        )
    }
)


updated_seen.to_csv(
    SEEN_FILE,
    index=False
)



# -----------------------------
# DISCORD
# -----------------------------


message = (
    "🏗️ **NYC Construction Leads**\n"
    f"📅 {datetime.now().strftime('%d %B %Y')}\n\n"
)



for _, row in new.head(10).iterrows():


    address = (
        str(row.get("house__", ""))
        + " "
        + str(row.get("street_name", ""))
    )


    owner = row.get(
        "owner_s_business_name",
        "Unknown"
    )


    borough = row.get(
        "borough",
        ""
    )


    cost = row.get(
        "initial_cost",
        "Unknown"
    )


    message += (
        f"🔥 Score: {row['lead_score']}\n"
        f"🏢 {row.get('job_type')}\n"
        f"📍 {address}, {borough}\n"
        f"👤 {owner}\n"
        f"💰 ${cost}\n\n"
    )



if DISCORD_WEBHOOK:


    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": message
        }
    )


print(
    f"Sent {len(new)} new leads"
)
