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


params = {
    "$limit": 5000,
    "$order": "latest_action_date DESC"
}


response = requests.get(
    API_URL,
    params=params
)


print(response.url)


response.raise_for_status()


df = pd.DataFrame(
    response.json()
)


print(
    f"Downloaded {len(df)} records"
)


if df.empty:
    print("No data returned")
    exit()



# =============================
# DATE CLEANING
# =============================

for col in [
    "pre__filing_date",
    "latest_action_date"
]:

    if col in df.columns:

        df[col] = pd.to_datetime(
            df[col],
            format="%m/%d/%Y",
            errors="coerce"
        )


# =============================
# LAST 7 DAYS FILTER
# =============================

cutoff = (
    datetime.now()
    -
    timedelta(days=7)
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
    f"After 7 day filter: {len(df)}"
)



if df.empty:

    print("No recent permits")
    exit()



# =============================
# CONSTRUCTION FILTER
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
# REMOVE CLOSED JOBS
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



if df.empty:

    print("No construction leads")
    exit()



# =============================
# SCORE LEADS
# =============================

def calculate_score(row):

    score = 0


    if row["job_type"] == "NB":

        score += 100


    elif row["job_type"] == "A1":

        score += 70


    elif row["job_type"] == "A2":

        score += 40



    try:

        cost = float(
            row.get(
                "initial_cost",
                0
            )
        )


        if cost >= 5000000:

            score += 75


        elif cost >= 1000000:

            score += 50


        elif cost >= 500000:

            score += 25


    except:

        pass


    return score



df["lead_score"] = df.apply(
    calculate_score,
    axis=1
)



df = df.sort_values(
    "lead_score",
    ascending=False
)



# =============================
# REMOVE PREVIOUSLY SENT
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

    seen_jobs = set(
        old["job__"].astype(str)
    )


else:

    seen_jobs = set()



new_leads = df[
    ~df["job__"].isin(
        seen_jobs
    )
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
            seen_jobs.union(
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
    "🏗️ **NYC Construction Leads**\n"
    f"📅 {datetime.now().strftime('%d %B %Y')}\n\n"
)



for _, row in new_leads.head(20).iterrows():

    address = (
        f"{row.get('house__','')} "
        f"{row.get('street_name','')}"
    )


    message += (

        f"🔥 Score: {row['lead_score']}\n"
        f"🏢 Type: {row.get('job_type')}\n"
        f"📍 {address}, {row.get('borough','')}\n"
        f"👤 Owner: {row.get('owner_s_business_name','Unknown')}\n"
        f"💰 Cost: ${row.get('initial_cost','Unknown')}\n"
        f"🆔 Job: {row.get('job__')}\n\n"

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
