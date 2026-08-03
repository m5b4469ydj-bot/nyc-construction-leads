import requests
import pandas as pd
from datetime import datetime, timedelta
import os


API_URL = "https://data.cityofnewyork.us/resource/w9ak-ipjd.json"

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

OUTPUT_FILE = "data/nyc_construction_leads.xlsx"
SEEN_FILE = "data/seen_jobs.csv"

ID_COLUMN = "job_filing_number"


DAYS_BACK = 7



print("Downloading NYC DOB data...")


cutoff = (
    datetime.now()
    -
    timedelta(days=DAYS_BACK)
)


cutoff_string = cutoff.strftime(
    "%Y-%m-%dT00:00:00"
)



params = {

    "$limit": 5000,

    "$order":
        "current_status_date DESC",

    "$where":
        f"""
        current_status_date >= '{cutoff_string}'
        OR
        filing_date >= '{cutoff_string}'
        """
}



response = requests.get(
    API_URL,
    params=params
)


response.raise_for_status()


df = pd.DataFrame(
    response.json()
)



print(
    f"Downloaded {len(df)} records"
)



if df.empty:

    print(
        "No recent permits"
    )

    exit()



# =============================
# CLEAN DATES
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



print("\nDates returned:")

print(
    df[
        [
            "filing_date",
            "current_status_date"
        ]
    ].head(10)
)



# =============================
# FILTER
# =============================


df = df[
    (
        df["filing_date"].notna()
        |
        df["current_status_date"].notna()
    )
]


print(
    f"After date filter: {len(df)}"
)



# =============================
# SCORE
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
        points += 30


    try:

        cost = float(
            row.get(
                "initial_cost",
                0
            )
        )


        if cost > 5000000:
            points += 100

        elif cost > 1000000:
            points += 60

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
# SEEN JOBS
# =============================


os.makedirs(
    "data",
    exist_ok=True
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



df[ID_COLUMN] = (
    df[ID_COLUMN]
    .astype(str)
)



new = df[
    ~df[ID_COLUMN]
    .isin(seen)
]



if new.empty:

    print(
        "No new leads today"
    )

    exit()



print(
    f"New leads: {len(new)}"
)



# =============================
# SAVE
# =============================


new.to_excel(
    OUTPUT_FILE,
    index=False
)



seen.update(
    new[ID_COLUMN]
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
# DISCORD
# =============================


message = (
    "🏗️ NYC Construction Leads\n"
    f"New leads: {len(new)}\n\n"
)



for _, r in new.head(20).iterrows():

    message += (
        f"🔥 {r['lead_score']} pts\n"
        f"📍 {r.get('house_no','')} {r.get('street_name','')}\n"
        f"🏢 {r.get('owner_s_business_name','Unknown')}\n"
        f"💰 {r.get('initial_cost','Unknown')}\n\n"
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
