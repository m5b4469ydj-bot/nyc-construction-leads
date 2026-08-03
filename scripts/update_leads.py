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
# DOWNLOAD DATA
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

    print("No data returned")
    exit()


print(f"Downloaded {len(df)} records")


# =============================
# SHOW NYC VALUES
# =============================

print("\nAVAILABLE COLUMNS:")
print(list(df.columns))


if "job_type" in df.columns:

    print("\nJOB TYPES FOUND:")
    print(
        df["job_type"]
        .value_counts()
        .head(20)
    )


if "job_status" in df.columns:

    print("\nSTATUSES FOUND:")
    print(
        df["job_status"]
        .value_counts()
        .head(20)
    )


# =============================
# DATE FILTER
# =============================

if "pre__filing_date" in df.columns:

    df["pre__filing_date"] = pd.to_datetime(
        df["pre__filing_date"],
        errors="coerce"
    )


    cutoff = (
        datetime.now()
        -
        timedelta(days=60)
    )


    df = df[
        df["pre__filing_date"] >= cutoff
    ]


print(
    f"\nAfter date filter: {len(df)} records"
)


# =============================
# TEMP FILTER
# KEEP ALL CONSTRUCTION
# =============================

# We are deliberately NOT filtering
# job_type/status yet.
# The debug output above tells us
# the correct values.


# =============================
# SCORE LEADS
# =============================

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


        if cost >= 1000000:

            points += 50


        elif cost >= 500000:

            points += 25


    except:

        pass


    return points



df["lead_score"] = df.apply(
    score,
    axis=1
)


df = df.sort_values(
    "lead_score",
    ascending=False
)


# =============================
# REMOVE OLD JOBS
# =============================

os.makedirs(
    "data",
    exist_ok=True
)


if "job__" not in df.columns:

    print("No job number column found")
    exit()


df["job__"] = df["job__"].astype(str)



if os.path.exists(SEEN_FILE):

    old = pd.read_csv(
        SEEN_FILE
    )

    seen = set(
        old["job__"].astype(str)
    )


else:

    seen = set()



new_leads = df[
    ~df["job__"].isin(seen)
]


if new_leads.empty:

    print(
        "No new leads"
    )

    exit()


# =============================
# SAVE EXCEL
# =============================

new_leads.to_excel(
    OUTPUT_FILE,
    index=False
)


pd.DataFrame(
    {
        "job__":
        list(
            seen.union(
                set(
                    new_leads["job__"]
                )
            )
        )
    }
).to_csv(
    SEEN_FILE,
    index=False
)


# =============================
# DISCORD
# =============================

message = (
    "🏗️ **NYC Construction Leads**\n\n"
)


for _, row in new_leads.head(10).iterrows():


    address = (
        str(row.get("house__", ""))
        +
        " "
        +
        str(row.get("street_name", ""))
    )


    message += (
        f"🔥 Score: {row['lead_score']}\n"
        f"🏢 Type: {row.get('job_type')}\n"
        f"📍 {address}\n"
        f"💰 {row.get('initial_cost','Unknown')}\n\n"
    )


if DISCORD_WEBHOOK:


    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": message
        }
    )


print(
    f"SUCCESS: Sent {len(new_leads)} leads"
)
