"""
Fetches NSE's official master lists -- both regular equities AND ETFs -- and
merges them into data/nse_securities.json for the PWA's search-as-you-type feature.

This is NOT scheduled -- run it manually (via Actions "Run workflow" button)
whenever you want to refresh the list, e.g. every couple of months.
"""

import json
import csv
import io
import os
import urllib.request

EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
ETF_URL = "https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv"
OUTPUT_FILE = "data/nse_securities.json"


def fetch_csv_list(url, kind):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    securities = []
    for row in reader:
        symbol = (row.get("SYMBOL") or "").strip()
        name = (row.get("NAME OF COMPANY") or row.get("Underlying") or row.get("SECURITY NAME") or "").strip()
        if symbol and name:
            securities.append({"symbol": symbol, "name": name, "ticker": f"{symbol}.NS", "type": kind})
    return securities


def main():
    all_securities = []

    try:
        equities = fetch_csv_list(EQUITY_URL, "equity")
        print(f"Fetched {len(equities)} equities from NSE.")
        all_securities.extend(equities)
    except Exception as e:
        print(f"WARNING: could not fetch equities list: {e}")

    try:
        etfs = fetch_csv_list(ETF_URL, "etf")
        print(f"Fetched {len(etfs)} ETFs from NSE.")
        all_securities.extend(etfs)
    except Exception as e:
        print(f"WARNING: could not fetch ETF list: {e}")

    # de-duplicate by symbol, in case of overlap
    seen = set()
    deduped = []
    for s in all_securities:
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            deduped.append(s)

    print(f"Total combined (deduped): {len(deduped)}")
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(deduped, f, indent=2)
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
