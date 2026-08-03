import requests
import pandas as pd
from datetime import datetime, timedelta
import os


# =============================
# SETTINGS
# =============================

API_URL = "https://data.cityofnewyork.us/resource/rvhx-8trz.json"

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

OUTPUT_FILE = "data/nyc_construction_leads.xlsx"
SEEN_FILE = "data/seen_jobs.csv"

DAYS_BACK = 7



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


df = pd.DataFrame(
    response.json()
)


print(
    f"Downloaded {len(df)} records"
)


if df.empty:
    print("No records")
    exit()



# =============================
# SHOW RAW DATES
# =============================

print("\nRaw newest dates returned:")

print(
    df[
        [
            "pre__filing_date",
            "latest_action_date"
        ]
    ].head(10)
)



# =============================
# CONVERT DATES
# =============================

for col in [
    "pre__filing_date",
    "latest_action_date"
]:

    df[col] = pd.to_datetime(
        df[col],
        format="%m/%d/%Y",
        errors="coerce"
    )



print("\nConverted newest dates:")

print(
    df[
        [
            "pre__filing_date",
            "latest_action_date"
        ]
    ].head(10)
)



# =============================
# SORT BY REAL DATE
# =============================

df = df.sort_values(
    "latest_action_date",
    ascending=False
)



# =============================
# LAST 7 DAYS
# =============================

cutoff = (
    datetime.now()
    -
    timedelta(days=DAYS_BACK)
)


df = df[
    (
        df["pre__filing_date"] >= cutoff
    )
    |
    (
        df["latest_action_date"] >= cutoff
    )
]


print(
    f"\nAfter 7 day filter: {len(df)}"
)



if df.empty:

    print("No recent permits")

    exit()



# =============================
# JOB TYPE FILTER
# =============================

df = df[
    df["job_type"].isin(
        [
            "NB",
            "A1",
            "A2"
        ]
    )
]


print(
    f"After job type filter: {len(df)}"
)



# =============================
# STATUS FILTER
# =============================

df = df[
    ~df["job_status"].isin(
        [
            "X",
            "D"
        ]
    )
]


print(
    f"After status filter: {len(df)}"
)



# =============================
# SCORE
# =============================

def score(row):

    points = 0

    if row["job_type"] == "NB":
        points += 100

    elif row["job_type"] == "A1":
        points += 70

    elif row["job_type"] == "A2":
        points += 40


    try:

        cost = float(
            row.get(
                "initial_cost",
                0
            )
        )

        if cost >= 5000000:
            points += 75

        elif cost >= 1000000:
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
# REMOVE OLD LEADS
# =============================

os.makedirs(
    "data",
    exist_ok=True
)


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
        "No new leads today"
    )

    exit()



print(
    f"New leads: {len(new_leads)}"
)



# =============================
# SAVE EXCEL
# =============================

new_leads.to_excel(
    OUTPUT_FILE,
    index=False
)



pd.DataFrame(
    {
        "job__": list(
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
    "🏗️ NYC Construction Leads\n"
    f"{datetime.now().strftime('%d/%m/%Y')}\n\n"
)



for _, row in new_leads.head(20).iterrows():

    address = (
        f"{row.get('house__','')} "
        f"{row.get('street_name','')}"
    )


    message += (

        f"🔥 Score: {row['lead_score']}\n"
        f"🏢 {row.get('job_type')}\n"
        f"📍 {address}, {row.get('borough','')}\n"
        f"👤 {row.get('owner_s_business_name','Unknown')}\n"
        f"💰 ${row.get('initial_cost','Unknown')}\n"
        f"🆔 {row.get('job__')}\n\n"

    )



if DISCORD_WEBHOOK:

    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": message
        }
    )


print(
    f"SUCCESS - Sent {len(new_leads)} leads"
)
