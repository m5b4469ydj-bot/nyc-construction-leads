import requests
import pandas as pd

API_URL = "https://data.cityofnewyork.us/resource/rvhx-8trz.json"

response = requests.get(
    API_URL,
    params={
        "$limit": 20,
        "$order": "dobrundate DESC"
    }
)

response.raise_for_status()

df = pd.DataFrame(response.json())

print(df.columns.tolist())

print("\nDATES:")
print(
    df[
        [
            "pre__filing_date",
            "latest_action_date",
            "dobrundate"
        ]
    ].head(20)
)
