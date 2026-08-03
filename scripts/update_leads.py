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

ID_COLUMN = "job_filing_number"



# =============================
# DOWNLOAD NYC DOB DATA
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



print("\nDate check:")

print(
    df[
        [
            "filing_date",
            "current_status_date"
        ]
    ].head(10)
)



# =============================
# ONLY LAST 7 DAYS
# =============================

cutoff = (
    datetime.now()
    -
    timedelta(days=DAYS_BACK)
)



df["recent_filing"] = (
    df["filing_date"].notna()
    &
    (df["filing_date"] >= cutoff)
)


df["recent_status"] = (
    df["current_status_date"].notna()
    &
    (df["current_status_date"] >= cutoff)
)



df["lead_type"] = "ACTIVE PROJECT"



df.loc[
    df["recent_filing"],
    "lead_type"
] = "NEW FILING"



df = df[
    df["recent_filing"]
    |
    df["recent_status"]
]



print(
    f"After 7 day filter: {len(df)}"
)



if df.empty:

    print(
        "No recent permits"
    )

    exit()



# =============================
# STATUS FILTER
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
# LEAD SCORE
# =============================

def calculate_score(row):

    score = 0


    if row["lead_type"] == "NEW FILING":
        score += 50

    else:
        score += 25



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
# DISCORD TOP 20
# =============================

message = (
    "🏗️ NYC Construction Leads\n"
    f"{datetime.now().strftime('%d/%m/%Y')}\n"
    f"New leads: {len(new_leads)}\n\n"
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
        f"💰 Cost: {row.get('initial_cost','Unknown')}\n"
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
