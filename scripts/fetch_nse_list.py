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


def fetch_equity_list():
    req = urllib.request.Request(EQUITY_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    securities = []
    for row in reader:
        symbol = (row.get("SYMBOL") or "").strip()
        name = (row.get("NAME OF COMPANY") or "").strip()
        if symbol and name:
            securities.append({
                "symbol": symbol, "name": name, "ticker": f"{symbol}.NS", "type": "equity",
                "search_blob": f"{symbol} {name}".lower(),
            })
    return securities


def fetch_etf_list():
    # NSE's ETF file uses DIFFERENT column names than the equity file:
    # Symbol, Underlying, SecurityName, DateofListing, MarketLot, ISINNumber, FaceValue
    req = urllib.request.Request(ETF_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    securities = []
    for row in reader:
        symbol = (row.get("Symbol") or "").strip()
        underlying = (row.get("Underlying") or "").strip()
        security_name = (row.get("SecurityName") or "").strip()
        if not symbol:
            continue
        # NSE's ETF names are inconsistent -- sometimes Underlying is a readable
        # name, sometimes SecurityName is, sometimes both are smushed together
        # with no spaces. Prefer whichever looks most like readable words for
        # display, but combine everything into search_blob so search still finds
        # it regardless of which field actually has useful text.
        display_name = underlying if " " in underlying else (security_name if " " in security_name else (underlying or security_name or symbol))
        securities.append({
            "symbol": symbol, "name": display_name, "ticker": f"{symbol}.NS", "type": "etf",
            "search_blob": f"{symbol} {underlying} {security_name}".lower(),
        })
    return securities


def main():
    all_securities = []

    try:
        equities = fetch_equity_list()
        print(f"Fetched {len(equities)} equities from NSE.")
        all_securities.extend(equities)
    except Exception as e:
        print(f"WARNING: could not fetch equities list: {e}")

    try:
        etfs = fetch_etf_list()
        print(f"Fetched {len(etfs)} ETFs from NSE.")
        all_securities.extend(etfs)
    except Exception as e:
        print(f"WARNING: could not fetch ETF list: {e}")

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
