"""
Computes fundamentals (PE, ROCE, PEG-inputs) + 52-week high/low for ONE ticker,
triggered on-demand from the PWA via a workflow_dispatch call.

Reads TICKER and KEY from environment variables (passed in by the workflow).
Saves result to data/fundamentals/{key}.json
"""

import json
import os
import sys
import yfinance as yf

TICKER = os.environ.get("TICKER")
KEY = os.environ.get("KEY")


def compute_roce(financials, balance_sheet, col):
    try:
        ebit = None
        for row_name in ["EBIT", "Operating Income", "OperatingIncome"]:
            if row_name in financials.index:
                ebit = financials.loc[row_name, col]
                break
        total_assets = None
        for row_name in ["Total Assets", "TotalAssets"]:
            if row_name in balance_sheet.index:
                total_assets = balance_sheet.loc[row_name, col]
                break
        current_liab = None
        for row_name in ["Current Liabilities", "CurrentLiabilities", "Total Current Liabilities"]:
            if row_name in balance_sheet.index:
                current_liab = balance_sheet.loc[row_name, col]
                break
        if ebit is None or total_assets is None or current_liab is None:
            return None
        capital_employed = total_assets - current_liab
        if capital_employed == 0:
            return None
        return round(float(ebit) / float(capital_employed) * 100, 2)
    except Exception:
        return None


def main():
    if not TICKER or not KEY:
        print("ERROR: TICKER and KEY environment variables are required.", file=sys.stderr)
        sys.exit(1)

    print(f"Computing fundamentals for {TICKER} (key={KEY})...")
    t = yf.Ticker(TICKER)
    info = t.info

    trailing_pe = info.get("trailingPE")
    forward_pe = info.get("forwardPE")
    roe = info.get("returnOnEquity")
    peg = info.get("trailingPegRatio") or info.get("pegRatio")
    earnings_growth = info.get("earningsGrowth")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")

    # 52-week high/low from 1 year of history
    week52_high, week52_low = None, None
    try:
        hist = t.history(period="1y")
        if not hist.empty:
            week52_high = round(float(hist["High"].max()), 2)
            week52_low = round(float(hist["Low"].min()), 2)
    except Exception as e:
        print(f"Could not fetch 52w history: {e}")

    # ROCE from latest annual financials
    roce = None
    try:
        fin = t.financials
        bs = t.balance_sheet
        if fin is not None and not fin.empty and bs is not None and not bs.empty:
            common_cols = [c for c in fin.columns if c in bs.columns]
            if common_cols:
                roce = compute_roce(fin, bs, common_cols[0])
    except Exception as e:
        print(f"Could not compute ROCE: {e}")

    # manual PEG fallback
    peg_manual = None
    if trailing_pe and earnings_growth and earnings_growth > 0.01:
        peg_manual = round(trailing_pe / (earnings_growth * 100), 2)

    result = {
        "ticker": TICKER,
        "key": KEY,
        "currentPrice": current_price,
        "trailingPE": trailing_pe,
        "forwardPE": forward_pe,
        "roe": roe,
        "peg": peg_manual or peg,
        "roce": roce,
        "week52High": week52_high,
        "week52Low": week52_low,
        "computedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }

    os.makedirs("data/fundamentals", exist_ok=True)
    out_path = f"data/fundamentals/{KEY}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Saved to {out_path}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
