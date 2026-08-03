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
        "$limit": 5000,
        "$order": "pre__filing_date DESC"
    }
)


response.raise_for_status()


df = pd.DataFrame(
    response.json()
)


if df.empty:

    print("No data returned")
    exit()


print(
    f"Downloaded {len(df)} records"
)


# =============================
# CLEAN DATES
# =============================

if "pre__filing_date" in df.columns:

    df["pre__filing_date"] = pd.to_datetime(
        df["pre__filing_date"],
        errors="coerce"
    )


cutoff = (
    datetime.now()
    -
    timedelta(days=90)
)


df = df[
    df["pre__filing_date"].notna()
]


df = df[
    df["pre__filing_date"] >= cutoff
]


print(
    f"After date filter: {len(df)}"
)


# =============================
# FILTER JOB TYPES
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
# FILTER STATUS
# =============================

# NYC codes:
# Keep active applications
# Remove closed/withdrawn


df = df[
    ~df["job_status"].isin(
        [
            "X",
            "D",
            "U"
        ]
    )
]


print(
    f"After status filter: {len(df)}"
)


if df.empty:

    print("No leads")
    exit()


# =============================
# SCORE LEADS
# =============================

def calculate_score(row):

    score = 0


    job = row.get(
        "job_type"
    )


    if job == "NB":

        score += 100


    elif job == "A1":

        score += 70


    elif job == "A2":

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



    if row.get(
        "building_type"
    ):

        score += 10


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
# REMOVE PREVIOUSLY SENT JOBS
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



# =============================
# SAVE EXCEL
# =============================

new_leads.to_excel(
    OUTPUT_FILE,
    index=False
)



all_seen = pd.DataFrame(
    {
        "job__": list(
            seen_jobs.union(
                set(
                    new_leads["job__"]
                )
            )
        )
    }
)


all_seen.to_csv(
    SEEN_FILE,
    index=False
)



# =============================
# DISCORD MESSAGE
# =============================

message = (
    "🏗️ **NYC Construction Leads**\n"
    f"📅 {datetime.now().strftime('%d %B %Y')}\n\n"
)



for _, row in new_leads.head(15).iterrows():


    address = (
        str(
            row.get(
                "house__",
                ""
            )
        )
        +
        " "
        +
        str(
            row.get(
                "street_name",
                ""
            )
        )
    )


    owner = row.get(
        "owner_s_business_name",
        "Unknown"
    )


    cost = row.get(
        "initial_cost",
        "Unknown"
    )


    message += (

        f"🔥 Score: {row['lead_score']}\n"

        f"🏢 Type: {row.get('job_type')}\n"

        f"📍 {address}, {row.get('borough','')}\n"

        f"👤 Owner: {owner}\n"

        f"💰 Cost: ${cost}\n\n"

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
