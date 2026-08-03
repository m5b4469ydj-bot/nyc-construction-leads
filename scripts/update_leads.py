import requests
import pandas as pd
from datetime import datetime, timedelta
import os


# =============================
# SETTINGS
# =============================

API_URL = "https://data.cityofnewyork.us/resource/w9ak-ipjd.json"

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
        "$limit": 5000,
        "$order": "filing_date DESC"
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
    print("No data")
    exit()



# =============================
# DATE FILTER
# =============================

for col in [
    "filing_date",
    "current_status_date"
]:

    df[col] = pd.to_datetime(
        df[col],
        errors="coerce"
    )



cutoff = (
    datetime.now()
    -
    timedelta(days=DAYS_BACK)
)



df = df[
    (
        df["filing_date"] >= cutoff
    )
    |
    (
        df["current_status_date"] >= cutoff
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

# Keep active construction activity

bad_status = [
    "Withdrawn",
    "Rejected",
    "Denied"
]


df = df[
    ~df["filing_status"].isin(
        bad_status
    )
]


print(
    f"After status filter: {len(df)}"
)



# =============================
# LEAD SCORE
# =============================

def score(row):

    points = 0


    status = str(
        row.get(
            "filing_status",
            ""
        )
    )


    if "Permit" in status:
        points += 50

    if "Approved" in status:
        points += 40



    try:

        cost = float(
            row.get(
                "initial_cost",
                0
            )
        )


        if cost >= 5000000:
            points += 100

        elif cost >= 1000000:
            points += 70

        elif cost >= 500000:
            points += 40


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
# REMOVE ALREADY SENT
# =============================

os.makedirs(
    "data",
    exist_ok=True
)


df["job_filing_number"] = (
    df["job_filing_number"]
    .astype(str)
)



if os.path.exists(SEEN_FILE):

    old = pd.read_csv(
        SEEN_FILE
    )

    seen = set(
        old["job_filing_number"]
        .astype(str)
    )

else:

    seen = set()



new_leads = df[
    ~df["job_filing_number"]
    .isin(seen)
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
        "job_filing_number":
        list(
            seen.union(
                set(
                    new_leads[
                        "job_filing_number"
                    ]
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
        f"{row.get('house_no','')} "
        f"{row.get('street_name','')}"
    )


    message += (

        f"🔥 Score: {row['lead_score']}\n"
        f"📍 {address}, {row.get('borough','')}\n"
        f"👤 {row.get('owner_s_business_name','Unknown')}\n"
        f"💰 ${row.get('initial_cost','Unknown')}\n"
        f"📌 Status: {row.get('filing_status')}\n"
        f"🆔 {row.get('job_filing_number')}\n\n"

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
