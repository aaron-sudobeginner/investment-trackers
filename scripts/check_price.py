"""
Checks Nifty BeES price, tracks the running peak and drawdown tiers, and:
  1. Saves the latest state to data/niftybees.json (the PWA reads this directly)
  2. Opens a GitHub Issue (which GitHub emails to the repo owner automatically)
     whenever a NEW tier is crossed since the last all-time high

Runs on a schedule via .github/workflows/price_check.yml
No secrets needed beyond the GITHUB_TOKEN that Actions provides automatically.
"""

import json
import os
import sys
from datetime import datetime, timezone
import urllib.request
import urllib.error

TICKER = "NIFTYBEES.NS"
DISPLAY_NAME = "Nifty BeES"
DATA_FILE = "data/niftybees.json"
TIERS = [5, 10, 15, 20, 25, 30, 35, 40]

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")  # e.g. "yourname/nifty-toolkit"


def fetch_current_price(ticker):
    """Fetch latest price via Yahoo Finance's public chart endpoint (server-side, no CORS issue here)."""
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


def load_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return None


def save_state(state):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(state, f, indent=2)


def create_github_issue(title, body):
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        print("No GITHUB_TOKEN/GITHUB_REPOSITORY in env, skipping issue creation.")
        return
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
    payload = json.dumps({
        "title": title,
        "body": body,
        "labels": ["dip-alert", "nifty-bees"],
    }).encode()
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


def main():
    price = fetch_current_price(TICKER)
    now = datetime.now(timezone.utc).isoformat()
    print(f"Fetched {DISPLAY_NAME} price: {price} at {now}")

    state = load_state()
    if state is None:
        # first run ever -- seed with current price as the peak
        state = {
            "name": DISPLAY_NAME,
            "ticker": TICKER,
            "price": price,
            "peak": price,
            "peakDate": now,
            "tiersHit": [],
            "lastChecked": now,
        }
        save_state(state)
        print("Initialized state file for the first time. Nothing to alert on yet.")
        return

    state["price"] = price
    state["lastChecked"] = now

    # new all-time high resets the tier ladder
    if price >= state["peak"]:
        state["peak"] = price
        state["peakDate"] = now
        state["tiersHit"] = []
        save_state(state)
        print("New peak recorded, ladder reset.")
        return

    drawdown_pct = (state["peak"] - price) / state["peak"] * 100
    newly_triggered = None
    for t in TIERS:
        if drawdown_pct >= t and t not in state["tiersHit"]:
            newly_triggered = t
            state["tiersHit"].append(t)
            break  # only alert one new tier per run; next run will catch further tiers if any

    save_state(state)

    if newly_triggered is not None:
        title = f"Dip alert: {DISPLAY_NAME} down {newly_triggered}% from peak"
        body = (
            f"**{DISPLAY_NAME}** has crossed a new drawdown tier.\n\n"
            f"- Current price: Rs {price:.2f}\n"
            f"- Peak: Rs {state['peak']:.2f} (on {state['peakDate'][:10]})\n"
            f"- Drawdown: {drawdown_pct:.1f}%\n"
            f"- Tier triggered: -{newly_triggered}%\n\n"
            f"Check the tracker app to log your deployment for this tier."
        )
        create_github_issue(title, body)
        print(f"Tier -{newly_triggered}% triggered, issue created.")
    else:
        print(f"No new tier. Current drawdown: {drawdown_pct:.1f}%")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
