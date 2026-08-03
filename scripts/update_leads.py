import requests
import pandas as pd
from datetime import datetime, timedelta
import os


DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

OUTPUT_FILE = "data/nyc_construction_leads.xlsx"
SEEN_FILE = "data/seen_jobs.csv"

API_URL = "https://data.cityofnewyork.us/resource/rvhx-8trz.json"


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


# -----------------------------
# DATE FILTER
# -----------------------------

if "latest_action_date" in df.columns:

    df["latest_action_date"] = pd.to_datetime(
        df["latest_action_date"],
        errors="coerce"
    )

    cutoff = (
        datetime.now()
        -
        timedelta(days=60)
    )

    df = df[
        df["latest_action_date"] >= cutoff
    ]


print(
    f"After date filter: {len(df)}"
)


# -----------------------------
# CONSTRUCTION TYPE
# -----------------------------

df = df[
    df["job_type"].isin(
        [
            "NB",
            "A1"
        ]
    )
]


print(
    f"After job type filter: {len(df)}"
)


# -----------------------------
# ACTIVE STATUS
# -----------------------------

# Remove closed/completed jobs

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


if df.empty:

    print("No leads")
    exit()


# -----------------------------
# LEAD SCORE
# -----------------------------

def score(row):

    score = 0

    if row["job_type"] == "NB":
        score += 100

    if row["job_type"] == "A1":
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


    return score


df["lead_score"] = df.apply(
    score,
    axis=1
)


df = df.sort_values(
    "lead_score",
    ascending=False
)


# -----------------------------
# ONLY NEW JOBS
# -----------------------------

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



new = df[
    ~df["job__"].isin(seen)
]


if new.empty:

    print(
        "No new leads"
    )

    exit()



# -----------------------------
# SAVE EXCEL
# -----------------------------

new.to_excel(
    OUTPUT_FILE,
    index=False
)


pd.DataFrame(
    {
        "job__": list(
            seen.union(
                set(new["job__"])
            )
        )
    }
).to_csv(
    SEEN_FILE,
    index=False
)



# -----------------------------
# DISCORD
# -----------------------------

message = (
    "🏗️ **NYC Construction Leads**\n\n"
)


for _, row in new.head(10).iterrows():

    address = (
        str(row.get("house__", ""))
        +
        " "
        +
        str(row.get("street_name", ""))
    )


    message += (
        f"🔥 Score: {row['lead_score']}\n"
        f"🏢 {row['job_type']}\n"
        f"📍 {address}, {row.get('borough','')}\n"
        f"💰 ${row.get('initial_cost','Unknown')}\n\n"
    )



if DISCORD_WEBHOOK:

    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": message
        }
    )


print(
    f"SUCCESS - Sent {len(new)} leads"
)
