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
    "filing_date",
    "current_status_date"
]:

    if col in df.columns:

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
# STATUS FILTER
# =============================

remove_status = [
    "Withdrawn",
    "Rejected",
    "Denied"
]


if "filing_status" in df.columns:

    df = df[
        ~df["filing_status"]
        .isin(remove_status)
    ]


print(
    f"After status filter: {len(df)}"
)



# =============================
# LEAD SCORING
# =============================

def calculate_score(row):

    score = 0


    status = str(
        row.get(
            "filing_status",
            ""
        )
    )


    if "Permit" in status:
        score += 50

    if "Approved" in status:
        score += 40



    try:

        cost = float(
            row.get(
                "initial_cost",
                0
            )
        )


        if cost >= 5000000:
            score += 100

        elif cost >= 1000000:
            score += 70

        elif cost >= 500000:
            score += 40

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
# DUPLICATE CONTROL
# =============================

os.makedirs(
    "data",
    exist_ok=True
)


ID_COLUMN = "job_filing_number"


df[ID_COLUMN] = (
    df[ID_COLUMN]
    .astype(str)
)



seen = set()



if os.path.exists(SEEN_FILE):

    old = pd.read_csv(
        SEEN_FILE
    )


    if ID_COLUMN in old.columns:

        seen = set(
            old[ID_COLUMN]
            .astype(str)
        )



new_leads = df[
    ~df[ID_COLUMN]
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
# EXPORT EXCEL
# =============================

new_leads.to_excel(
    OUTPUT_FILE,
    index=False
)



all_seen = (
    seen
    .union(
        set(
            new_leads[ID_COLUMN]
        )
    )
)



pd.DataFrame(
    {
        ID_COLUMN:
        list(all_seen)
    }
).to_csv(
    SEEN_FILE,
    index=False
)



# =============================
# DISCORD MESSAGE
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
        f"💰 Cost: {row.get('initial_cost','Unknown')}\n"
        f"📌 Status: {row.get('filing_status','')}\n"
        f"🆔 {row[ID_COLUMN]}\n\n"
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
