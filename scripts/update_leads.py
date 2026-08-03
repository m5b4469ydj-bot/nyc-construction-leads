import requests
import pandas as pd
from datetime import datetime, timedelta
import os


# =============================
# SETTINGS
# =============================

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

OUTPUT_FILE = "data/nyc_construction_leads.xlsx"
SEEN_FILE = "data/seen_jobs.csv"

API_URL = "https://data.cityofnewyork.us/resource/rvhx-8trz.json"


# =============================
# DOWNLOAD NYC DOB DATA
# =============================

print("Downloading NYC DOB data...")

response = requests.get(
    API_URL,
    params={
        "$limit": 5000
    }
)

response.raise_for_status()

records = response.json()

df = pd.DataFrame(records)


if df.empty:
    print("No data returned from NYC")
    exit()


print(f"Downloaded {len(df)} records")


# =============================
# DATE FILTER
# =============================

if "pre__filing_date" in df.columns:

    df["pre__filing_date"] = pd.to_datetime(
        df["pre__filing_date"],
        errors="coerce"
    )

    cutoff = datetime.now() - timedelta(days=30)

    df = df[
        df["pre__filing_date"] >= cutoff
    ]


# =============================
# JOB TYPE FILTER
# =============================

if "job_type" in df.columns:

    df = df[
        df["job_type"].isin(
            [
                "NB",
                "ALT-1"
            ]
        )
    ]


# =============================
# STATUS FILTER
# =============================

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


# =============================
# SCORE LEADS
# =============================

def lead_score(row):

    score = 0

    if row.get("job_type") == "NB":
        score += 100

    if row.get("job_type") == "ALT-1":
        score += 70


    try:

        cost = float(
            row.get(
                "initial_cost",
                0
            )
        )

        if cost >= 1000000:
            score += 50

        elif cost >= 500000:
            score += 25

    except:

        pass


    if row.get("building_type"):
        score += 10


    return score



df["lead_score"] = df.apply(
    lead_score,
    axis=1
)


df = df.sort_values(
    "lead_score",
    ascending=False
)


# =============================
# ONLY NEW JOBS
# =============================

os.makedirs(
    "data",
    exist_ok=True
)


if "job__" not in df.columns:

    print("No job number field found")
    exit()


df["job__"] = df["job__"].astype(str)


if os.path.exists(SEEN_FILE):

    old = pd.read_csv(SEEN_FILE)

    seen_jobs = set(
        old["job__"].astype(str)
    )

else:

    seen_jobs = set()



new_leads = df[
    ~df["job__"].isin(seen_jobs)
]


if new_leads.empty:

    print("No new leads today")
    exit()


# =============================
# SAVE EXCEL
# =============================

new_leads.to_excel(
    OUTPUT_FILE,
    index=False
)


updated_seen = pd.DataFrame(
    {
        "job__": list(
            seen_jobs.union(
                set(new_leads["job__"])
            )
        )
    }
)


updated_seen.to_csv(
    SEEN_FILE,
    index=False
)


# =============================
# SEND DISCORD
# =============================

message = (
    "🏗️ **NYC Construction Leads**\n"
    f"📅 {datetime.now().strftime('%d %B %Y')}\n\n"
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
        f"🏢 Type: {row.get('job_type')}\n"
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
    f"Sent {len(new_leads)} new leads to Discord"
)
