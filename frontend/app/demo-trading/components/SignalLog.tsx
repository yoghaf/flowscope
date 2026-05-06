"use client";

import { useState } from "react";
import { Activity, Filter } from "lucide-react";
import type { SignalEvent } from "@/lib/types";

import SignalBadge from "./SignalBadge";
import SetupBadge from "./SetupBadge";

interface SignalLogProps {
  signals: SignalEvent[];
  isLoading: boolean;
}

type FilterType = "all" | "long" | "short" | "win" | "loss";

export default function SignalLog({ signals, isLoading }: SignalLogProps) {
  const [filter, setFilter] = useState<FilterType>("all");

  const filteredSignals = signals.filter((signal) => {
    if (filter === "all") return true;
    if (filter === "long") return signal.side === "Long";
    if (filter === "short") return signal.side === "Short";
    if (filter === "win")
      return signal.status === "closed" && signal.pnl && signal.pnl > 0;
    if (filter === "loss")
      return signal.status === "closed" && signal.pnl && signal.pnl <= 0;
    return true;
  });

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-6">
        <p className="text-muted-foreground">Loading signals...</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">Signal Log</h3>

        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as FilterType)}
            className="rounded-lg border border-white/10 bg-muted px-3 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            <option value="all">All</option>
            <option value="long">Long Only</option>
            <option value="short">Short Only</option>
            <option value="win">Wins</option>
            <option value="loss">Losses</option>
          </select>
        </div>
      </div>

      <div className="max-h-[400px] space-y-2 overflow-y-auto">
        {filteredSignals.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Activity className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <p className="text-muted-foreground">No signals yet</p>
            <p className="text-sm text-muted-foreground/70">
              Start demo trading to see signals
            </p>
          </div>
        ) : (
          filteredSignals.map((signal, index) => (
            <div
              key={signal.id || index}
              className="flex items-start gap-3 rounded-lg border border-white/10 bg-muted/30 p-3 transition hover:border-white/20"
            >
              <div className="flex-shrink-0">
                <div className="flex items-center justify-center rounded-full bg-primary/10 p-2">
                  <Activity className="h-4 w-4 text-primary" />
                </div>
              </div>

              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <SignalBadge side={signal.side} />
                  <span className="font-bold text-foreground">
                    {signal.symbol}
                  </span>
                  <SetupBadge setupType={signal.setup_type} />
                  {signal.status === "closed" && (
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-semibold ${
                        signal.pnl && signal.pnl > 0
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {signal.pnl && signal.pnl > 0 ? "✅ WIN" : "❌ LOSS"}
                    </span>
                  )}
                </div>

                <div className="text-sm text-muted-foreground">
                  {signal.message}
                </div>

                <div className="flex items-center gap-4 text-xs text-muted-foreground/70">
                  <span>{new Date(signal.timestamp).toLocaleString()}</span>
                  {signal.clarity && (
                    <span>Clarity: {signal.clarity.toFixed(2)}</span>
                  )}
                  {signal.pnl && signal.entry_price && signal.size && (
                    <span
                      className={
                        signal.pnl > 0 ? "text-emerald-400" : "text-red-400"
                      }
                    >
                      PnL: ${signal.pnl.toFixed(2)} (
                      {(
                        (signal.pnl / (signal.entry_price * signal.size)) *
                        100
                      ).toFixed(2)}
                      %)
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
