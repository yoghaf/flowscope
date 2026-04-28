import json
import httpx

BASE = "http://46.247.108.88:8000"
resp = httpx.get(f"{BASE}/performance/report/data", timeout=30)
data = resp.json()

rows = data.get("rows", [])
out = []
out.append(f"Total trades: {data.get('total_rows')}")
out.append(f"Scope: {data.get('scope')} | Tag: {data.get('active_tag')} | Since: {data.get('active_since')}")
out.append("")

wins = [t for t in rows if t["result"] == "win"]
losses = [t for t in rows if t["result"] == "loss"]
opens_t = [t for t in rows if t["result"] == "open"]
timeouts = [t for t in rows if t["result"] == "timeout"]

out.append(f"Wins: {len(wins)} | Losses: {len(losses)} | Open: {len(opens_t)} | Timeout: {len(timeouts)}")
closed = len(wins) + len(losses)
wr = len(wins) / closed * 100 if closed else 0
out.append(f"Win Rate: {wr:.1f}%")

total_pnl = sum(t["pnl_pct"] or 0 for t in rows if t["result"] in ("win", "loss"))
total_usd = sum(t["realized_pnl_usd"] or 0 for t in rows if t["result"] in ("win", "loss"))
out.append(f"Total PnL: {total_pnl:.2f}% | USD: ${total_usd:.2f}")

if wins:
    avg_win = sum(t["pnl_pct"] or 0 for t in wins) / len(wins)
    avg_win_usd = sum(t["realized_pnl_usd"] or 0 for t in wins) / len(wins)
    out.append(f"Avg Win: {avg_win:.2f}% (${avg_win_usd:.2f})")
if losses:
    avg_loss = sum(t["pnl_pct"] or 0 for t in losses) / len(losses)
    avg_loss_usd = sum(t["realized_pnl_usd"] or 0 for t in losses) / len(losses)
    out.append(f"Avg Loss: {avg_loss:.2f}% (${avg_loss_usd:.2f})")

# Expectancy
if closed:
    win_rate = len(wins) / closed
    avg_w = sum(t["pnl_pct"] or 0 for t in wins) / len(wins) if wins else 0
    avg_l = abs(sum(t["pnl_pct"] or 0 for t in losses) / len(losses)) if losses else 0
    expectancy = (win_rate * avg_w) - ((1 - win_rate) * avg_l)
    out.append(f"Expectancy per trade: {expectancy:.2f}%")

out.append("")
out.append("=== BY SETUP TYPE ===")
setups = {}
for t in rows:
    st = t.get("setup_type") or "Unknown"
    if st not in setups:
        setups[st] = {"w": 0, "l": 0, "o": 0, "pnl": 0}
    if t["result"] == "win":
        setups[st]["w"] += 1
        setups[st]["pnl"] += t["pnl_pct"] or 0
    elif t["result"] == "loss":
        setups[st]["l"] += 1
        setups[st]["pnl"] += t["pnl_pct"] or 0
    elif t["result"] == "open":
        setups[st]["o"] += 1
for st, d in setups.items():
    c = d["w"] + d["l"]
    wr2 = d["w"] / c * 100 if c else 0
    out.append(f"  {st}: W={d['w']} L={d['l']} O={d['o']} WR={wr2:.0f}% PnL={d['pnl']:.2f}%")

out.append("")
out.append("=== BY BIAS ===")
biases = {}
for t in rows:
    b = t.get("bias") or "?"
    if b not in biases:
        biases[b] = {"w": 0, "l": 0, "o": 0, "pnl": 0}
    if t["result"] == "win":
        biases[b]["w"] += 1
        biases[b]["pnl"] += t["pnl_pct"] or 0
    elif t["result"] == "loss":
        biases[b]["l"] += 1
        biases[b]["pnl"] += t["pnl_pct"] or 0
    elif t["result"] == "open":
        biases[b]["o"] += 1
for b, d in biases.items():
    c = d["w"] + d["l"]
    wr3 = d["w"] / c * 100 if c else 0
    out.append(f"  {b}: W={d['w']} L={d['l']} O={d['o']} WR={wr3:.0f}% PnL={d['pnl']:.2f}%")

out.append("")
out.append("=== BY QUALITY SCORE ===")
quals = {}
for t in rows:
    q = t.get("quality_score") or "?"
    if q not in quals:
        quals[q] = {"w": 0, "l": 0, "o": 0, "pnl": 0}
    if t["result"] == "win":
        quals[q]["w"] += 1
        quals[q]["pnl"] += t["pnl_pct"] or 0
    elif t["result"] == "loss":
        quals[q]["l"] += 1
        quals[q]["pnl"] += t["pnl_pct"] or 0
    elif t["result"] == "open":
        quals[q]["o"] += 1
for q, d in sorted(quals.items()):
    c = d["w"] + d["l"]
    wr4 = d["w"] / c * 100 if c else 0
    out.append(f"  {q}: W={d['w']} L={d['l']} O={d['o']} WR={wr4:.0f}% PnL={d['pnl']:.2f}%")

out.append("")
out.append("=== CLOSE REASONS ===")
reasons = {}
for t in rows:
    cr = t.get("close_reason") or "Still Open"
    reasons[cr] = reasons.get(cr, 0) + 1
for cr, cnt in sorted(reasons.items(), key=lambda x: -x[1]):
    out.append(f"  {cr}: {cnt}")

out.append("")
out.append("=== ALL TRADES (newest first) ===")
sorted_rows = sorted(rows, key=lambda t: t.get("created_at", ""), reverse=True)
for t in sorted_rows:
    pnl2 = t.get("pnl_pct") or 0
    sym = t["symbol"]
    res = t["result"]
    bias = t.get("bias", "?")
    setup = t.get("setup_type", "?")
    conf = t.get("confidence_pct", 0)
    qual = t.get("quality_score", "?")
    cap = t.get("capital_per_trade", 0)
    rr1 = t.get("planned_rr_tp1", 0)
    cr = t.get("close_reason", "Open")
    created = str(t.get("created_at", ""))[:16]
    out.append(
        f"  {created} | {sym:12s} | {bias:8s} | {setup:15s} | {res:7s} | PnL={pnl2:+.2f}% | Conf={conf:.0f}% | Q={qual} | Cap=${cap:.0f} | RR1={rr1:.1f} | {cr}"
    )

report = "\n".join(out)
import os
outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf_analysis.txt")
with open(outpath, "w", encoding="utf-8") as f:
    f.write(report)
print("Report written to", outpath)
