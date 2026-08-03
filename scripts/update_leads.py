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
        "$order": "current_status_date DESC"
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
# DATE CLEANING
# =============================

# Filing date can arrive in different formats
if "filing_date" in df.columns:

    df["filing_date"] = pd.to_datetime(
        df["filing_date"],
        errors="coerce",
        format="mixed"
    )


if "current_status_date" in df.columns:

    df["current_status_date"] = pd.to_datetime(
        df["current_status_date"],
        errors="coerce"
    )



print("\nLatest dates:")

print(
    df[
        [
            "filing_date",
            "current_status_date"
        ]
    ].head(10)
)



# =============================
# LAST 7 DAYS
# =============================

cutoff = (
    datetime.now()
    -
    timedelta(days=DAYS_BACK)
)



df["lead_type"] = "ACTIVE PROJECT"



recent_status = (
    df["current_status_date"]
    >= cutoff
)



recent_filing = (
    df["filing_date"]
    >= cutoff
)



df.loc[
    recent_filing,
    "lead_type"
] = "NEW FILING"



df = df[
    recent_status
    |
    recent_filing
]



print(
    f"After 7 day filter: {len(df)}"
)



if df.empty:

    print("No recent permits")

    exit()



# =============================
# REMOVE BAD STATUS
# =============================

bad_status = [
    "Withdrawn",
    "Rejected",
    "Denied"
]


if "filing_status" in df.columns:

    df = df[
        ~df["filing_status"]
        .isin(bad_status)
    ]



print(
    f"After status filter: {len(df)}"
)



# =============================
# SCORE LEADS
# =============================

def score(row):

    points = 0


    if row["lead_type"] == "NEW FILING":
        points += 50

    else:
        points += 25



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
# DUPLICATES
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
# SAVE EXCEL
# =============================

new_leads.to_excel(
    OUTPUT_FILE,
    index=False
)



seen.update(
    new_leads[ID_COLUMN]
    .tolist()
)



pd.DataFrame(
    {
        ID_COLUMN:
        list(seen)
    }
).to_csv(
    SEEN_FILE,
    index=False
)



# =============================
# DISCORD TOP LEADS ONLY
# =============================

message = (
    "🏗️ NYC Construction Leads\n"
    f"{datetime.now().strftime('%d/%m/%Y')}\n"
    f"Total new leads: {len(new_leads)}\n\n"
)



for _, row in new_leads.head(20).iterrows():

    address = (
        f"{row.get('house_no','')} "
        f"{row.get('street_name','')}"
    )


    message += (

        f"🔥 Score: {row['lead_score']}\n"
        f"🆕 {row['lead_type']}\n"
        f"📍 {address}, {row.get('borough','')}\n"
        f"👤 {row.get('owner_s_business_name','Unknown')}\n"
        f"💰 ${row.get('initial_cost','Unknown')}\n"
        f"📌 {row.get('filing_status','Unknown')}\n"
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
