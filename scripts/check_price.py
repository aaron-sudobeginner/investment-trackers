"""
Checks every instrument listed in data/watchlist.json, tracks each one's running
peak and drawdown tiers independently, and:
  1. Saves each instrument's latest state to data/{key}.json (the PWA reads this)
  2. Opens a GitHub Issue (auto-emailed to the repo owner) whenever a NEW tier
     is crossed since that instrument's last all-time high

To track a new instrument: add an entry to data/watchlist.json. No code changes needed.
    { "key": "goldbees", "ticker": "GOLDBEES.NS", "name": "Gold BeES" }

Runs on a schedule via .github/workflows/price_check.yml
No secrets needed beyond the GITHUB_TOKEN that Actions provides automatically.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
import urllib.request
import urllib.error

WATCHLIST_FILE = "data/watchlist.json"
TIERS = [5, 10, 15, 20, 25, 30, 35, 40]

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")


def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        print(f"No {WATCHLIST_FILE} found -- nothing to check.")
        return []
    with open(WATCHLIST_FILE) as f:
        return json.load(f)


def fetch_current_price(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    result = data["chart"]["result"][0]
    price = result["meta"].get("regularMarketPrice")
    if price is None:
        closes = result["indicators"]["quote"][0]["close"]
        price = next((c for c in reversed(closes) if c is not None), None)
    if price is None:
        raise RuntimeError("Could not extract price from Yahoo response")
    return float(price)


def fetch_true_52w_high(ticker, fallback_price):
    """Uses the same chart endpoint with a 1-year range to get the real 52-week
    high, so a newly-tracked instrument starts from the actual peak rather than
    just whatever price we happened to see on the first check."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1y"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        result = data["chart"]["result"][0]
        highs = result["indicators"]["quote"][0]["high"]
        valid_highs = [h for h in highs if h is not None]
        if valid_highs:
            return max(max(valid_highs), fallback_price)
    except Exception as e:
        print(f"Could not fetch 52w high for {ticker}, using current price as peak instead: {e}")
    return fallback_price


def load_state(key):
    path = f"data/{key}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def save_state(key, state):
    path = f"data/{key}.json"
    os.makedirs("data", exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def create_github_issue(title, body, labels):
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        print("No GITHUB_TOKEN/GITHUB_REPOSITORY in env, skipping issue creation.")
        return
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
    payload = json.dumps({"title": title, "body": body, "labels": labels}).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "dip-tracker-bot",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Issue created: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"Failed to create issue: {e.code} {e.read().decode()}")


def check_one(entry):
    key = entry["key"]
    ticker = entry["ticker"]
    name = entry.get("name", ticker)

    try:
        price = fetch_current_price(ticker)
    except Exception as e:
        print(f"[{key}] FAILED to fetch price for {ticker}: {e}")
        return
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{key}] {name} ({ticker}) = {price} at {now}")

    state = load_state(key)
    if state is None:
        peak = fetch_true_52w_high(ticker, price)
        state = {
            "name": name, "ticker": ticker, "price": price, "peak": peak,
            "peakDate": now, "tiersHit": [], "lastChecked": now,
        }
        save_state(key, state)
        print(f"[{key}] Initialized for the first time with peak=Rs{peak:.2f} (true 52w high). Nothing to alert on yet.")
        return

    state["price"] = price
    state["lastChecked"] = now

    if price >= state["peak"]:
        state["peak"] = price
        state["peakDate"] = now
        state["tiersHit"] = []
        save_state(key, state)
        print(f"[{key}] New peak recorded, ladder reset.")
        return

    drawdown_pct = (state["peak"] - price) / state["peak"] * 100
    newly_triggered = None
    for t in TIERS:
        if drawdown_pct >= t and t not in state["tiersHit"]:
            newly_triggered = t
            state["tiersHit"].append(t)
            break

    save_state(key, state)

    if newly_triggered is not None:
        title = f"Dip alert: {name} down {newly_triggered}% from peak"
        body = (
            f"**{name}** ({ticker}) has crossed a new drawdown tier.\n\n"
            f"- Current price: Rs {price:.2f}\n"
            f"- Peak: Rs {state['peak']:.2f} (on {state['peakDate'][:10]})\n"
            f"- Drawdown: {drawdown_pct:.1f}%\n"
            f"- Tier triggered: -{newly_triggered}%\n\n"
            f"Check the tracker app to log your deployment for this tier."
        )
        create_github_issue(title, body, labels=["dip-alert", key])
        print(f"[{key}] Tier -{newly_triggered}% triggered, issue created.")
    else:
        print(f"[{key}] No new tier. Current drawdown: {drawdown_pct:.1f}%")


def main():
    watchlist = load_watchlist()
    if not watchlist:
        return
    for entry in watchlist:
        check_one(entry)
        time.sleep(0.5)  # be polite to Yahoo between requests


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
