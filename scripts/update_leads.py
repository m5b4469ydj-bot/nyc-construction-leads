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
# FRIENDLY TRANSLATIONS
# =============================

BOROUGH_MAP = {
    "MN": "Manhattan",
    "BK": "Brooklyn",
    "BX": "Bronx",
    "QN": "Queens",
    "SI": "Staten Island"
}


JOB_TYPE_MAP = {

    "NB": "New Building",

    "A1": "Major Alteration",

    "A2": "Alteration",

    "A3": "Minor Alteration",

    "DM": "Demolition",

    "SC": "Subdivision",

    "SI": "Sign Work"
}


STATUS_MAP = {

    "Approved":
        "Approved",

    "LOC Issued":
        "Permit Issued",

    "Permit Entire":
        "Permit Issued",

    "Filed":
        "Application Filed"
}



# =============================
# DOWNLOAD NEW FILINGS
# =============================


print(
    "Downloading NYC DOB filings..."
)



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
        "filing_date DESC",

    "$where":
        f"filing_date >= '{cutoff_string}'"

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
    f"Downloaded {len(df)} filings"
)



if df.empty:

    print(
        "No new filings"
    )

    exit()



# =============================
# CLEAN DATES
# =============================


df["filing_date"] = pd.to_datetime(
    df["filing_date"],
    errors="coerce"
)



df = df[
    df["filing_date"].notna()
]



print(
    f"Valid filings: {len(df)}"
)



# =============================
# REMOVE OLD JOBS
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
        "No new filings today"
    )

    exit()



print(
    f"New filings: {len(new_leads)}"
)



# =============================
# FRIENDLY FIELDS
# =============================


new_leads["Borough"] = (
    new_leads["borough"]
    .map(BOROUGH_MAP)
    .fillna(
        new_leads["borough"]
    )
)



new_leads["Project Type"] = (
    new_leads["job_type"]
    .map(JOB_TYPE_MAP)
    .fillna(
        new_leads["job_type"]
    )
)



new_leads["Status"] = (
    new_leads["filing_status"]
    .map(STATUS_MAP)
    .fillna(
        new_leads["filing_status"]
    )
)



new_leads["Address"] = (

    new_leads["house_no"]
    .astype(str)

    + " "

    + new_leads["street_name"]

    + ", "

    + new_leads["Borough"]

)



# =============================
# LEAD SCORE
# =============================


def score(row):

    points = 0


    project = str(
        row["Project Type"]
    )


    if project == "New Building":
        points += 100


    elif project == "Major Alteration":
        points += 75


    elif project == "Alteration":
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

            points += 60

        elif cost >= 500000:

            points += 30


    except:

        pass


    return points



new_leads["Lead Score"] = (
    new_leads.apply(
        score,
        axis=1
    )
)



new_leads = new_leads.sort_values(
    "Lead Score",
    ascending=False
)



# =============================
# EXPORT FRIENDLY EXCEL
# =============================


export_columns = [

    "Lead Score",

    "Project Type",

    "Address",

    "Borough",

    "owner_s_business_name",

    "Status",

    "filing_date",

    "initial_cost",

    ID_COLUMN,

    "job_description",

    "applicant_first_name",

    "applicant_last_name"

]



export_columns = [

    c for c in export_columns

    if c in new_leads.columns

]



new_leads[
    export_columns
].to_excel(
    OUTPUT_FILE,
    index=False
)



# =============================
# UPDATE SEEN
# =============================


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
# DISCORD
# =============================


message = (

    "🏗️ NYC NEW CONSTRUCTION FILINGS\n"

    f"New opportunities: {len(new_leads)}\n\n"

)



for _, row in new_leads.head(20).iterrows():


    message += (

        f"🔥 Score: {row['Lead Score']}\n"

        f"🔨 {row['Project Type']}\n"

        f"📍 {row['Address']}\n"

        f"🏢 {row.get('owner_s_business_name','Unknown')}\n"

        f"💰 ${row.get('initial_cost','Unknown')}\n"

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
