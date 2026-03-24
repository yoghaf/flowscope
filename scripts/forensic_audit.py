# -*- coding: utf-8 -*-
import json
import sys
import urllib.parse
import urllib.request

API_URL = "http://localhost:8000/api/scanner"

def fetch_snapshots():
    params = {
        "timeframe": "1h",
        "symbol": "ALL",
        "snapshot_id": "latest",
        "min_score": "0.0",
        "max_score": "1.0",
    }
    query_string = urllib.parse.urlencode(params)
    url = f"{API_URL}?{query_string}"
    
    print(f"Fetching latest snapshots from {url}...\n")
    req = urllib.request.Request(url, headers={"User-Agent": "FlowScope-Forensic-Auditor"})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("items", [])
    except Exception as e:
        print(f"Error fetching data: {e}")
        print("Make sure your backend is running on localhost:8000")
        sys.exit(1)

def main():
    items = fetch_snapshots()
    if not items:
        print("No snapshots returned. Is the backend populated?")
        sys.exit(1)

    highest_rel = max(items, key=lambda x: x.get("reliability_score", 0))

    non_neutral = [x for x in items if x.get("signal") != "Neutral" and x.get("market_state") != "Neutral"]
    lowest_rel_non_neutral = min(non_neutral, key=lambda x: x.get("reliability_score", 0)) if non_neutral else None

    neutral = [x for x in items if x.get("signal") == "Neutral" and x.get("market_state") == "Neutral"]
    neutral_asset = neutral[0] if neutral else None

    def print_audit(label, asset):
        print("=" * 80)
        print(f">>> FORENSIC AUDIT: {label}")
        print("=" * 80)
        if not asset:
            print("No asset matching criteria found.\n")
            return
        
        print(f"Symbol:           {asset.get('symbol')}")
        print(f"Timestamp:        {asset.get('timestamp')}")
        print(f"Market State:     {asset.get('market_state')}")
        print(f"Signal:           {asset.get('signal')}")
        print(f"Reliability:      {asset.get('reliability_score', 0):.4f}")
        print("-" * 80)
        print("DEBUG TRACE:")
        trace = asset.get("debug_trace")
        if trace:
            print(json.dumps(trace, indent=2))
        else:
            print("WARNING: No debug_trace found in this snapshot! (Wait for the next engine cycle)")
        print("\n")

    print_audit("1. HIGHEST RELIABILITY", highest_rel)
    print_audit("2. LOWEST RELIABILITY (NON-NEUTRAL)", lowest_rel_non_neutral)
    print_audit("3. NEUTRAL ASSET", neutral_asset)

if __name__ == "__main__":
    main()
