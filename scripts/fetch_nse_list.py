"""
Fetches NSE's official master list of listed equities and saves it as
data/nse_securities.json for the PWA's search-as-you-type feature.

This is NOT scheduled -- run it manually (via Actions "Run workflow" button)
whenever you want to refresh the list, e.g. every couple of months.
"""

import json
import csv
import io
import urllib.request

NSE_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
OUTPUT_FILE = "data/nse_securities.json"


def fetch_nse_list():
    req = urllib.request.Request(NSE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    securities = []
    for row in reader:
        symbol = row.get("SYMBOL", "").strip()
        name = row.get("NAME OF COMPANY", "").strip()
        if symbol and name:
            securities.append({
                "symbol": symbol,
                "name": name,
                "ticker": f"{symbol}.NS",
            })
    return securities


def main():
    securities = fetch_nse_list()
    print(f"Fetched {len(securities)} listed securities from NSE.")
    import os
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(securities, f, indent=2)
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
