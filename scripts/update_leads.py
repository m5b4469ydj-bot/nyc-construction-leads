import requests
import pandas as pd

API_URL = "https://data.cityofnewyork.us/resource/w9ak-ipjd.json"

response = requests.get(
    API_URL,
    params={
        "$limit": 10
    }
)

response.raise_for_status()

df = pd.DataFrame(response.json())

print(df.columns.tolist())

print(df.head())
