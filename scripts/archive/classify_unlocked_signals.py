import csv
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parents[1]

def classify_from_csv():
    csv_path = REPO_ROOT / "continuation_audit_full_v3.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path.name} not found.")
        return

    print(f"Analyzing {csv_path.name} (Pure CSV Mode)...")
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        print(f"Available Columns: {columns}")
        
        # Check required semantic columns
        # Note: These must be present in the CSV for this script to work.
        required = ["scenario", "eb_quality", "eb_reason"]
        missing = [col for col in required if col not in columns]
        
        if missing:
            print(f"\nMISSING_COLUMNS: {missing}")
            print("Please run scripts/audit_continuation_gates.py once to populate the CSV with new diagnostic fields.")
            return

        candidates = []
        for row in reader:
            if row.get("mode_c_unlocked") == "True":
                candidates.append(row)

        if not candidates:
            print("No shadow-unlocked signals found.")
            return

        results = []
        counts = defaultdict(int)

        for cand in candidates:
            quality = cand["eb_quality"]
            reason = cand["eb_reason"]
            scenario = cand["scenario"]
            
            final_status = "BLOCKED"
            if quality == "ALLOW_CANDIDATE":
                final_status = "ALLOWED"
            
            counts[quality] += 1
            if final_status == "ALLOWED":
                counts["FINAL_ALLOWED"] += 1
            else:
                counts["FINAL_BLOCKED"] += 1
                
            results.append({
                "symbol": cand["symbol"],
                "ts": cand["timestamp"].split("T")[1][:8] if "T" in cand["timestamp"] else cand["timestamp"],
                "quality": quality,
                "reason": reason,
                "scenario": scenario,
                "final": final_status
            })

        # Print Table
        header = f"{'Symbol':<10} {'TS':<10} {'Quality':<16} {'Scenario':<15} {'Final':<10} {'Reason'}"
        print("\n" + "="*110)
        print(header)
        print("-" * 110)
        for r in results:
            print(f"{r['symbol']:<10} {r['ts']:<10} {r['quality']:<16} {r['scenario']:<15} {r['final']:<10} {r['reason']}")
        
        print("="*110)
        print("\nFinal Diagnostic Counts:")
        for k in ["ALLOW_CANDIDATE", "WATCHLIST", "REDUCE_OR_WAIT", "WAIT", "BLOCK", "FINAL_ALLOWED", "FINAL_BLOCKED"]:
            print(f"  {k:<16}: {counts[k]}")
        print("="*110)

if __name__ == "__main__":
    classify_from_csv()
