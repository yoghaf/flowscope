"use client";

import { useState } from "react";
import { History, Download } from "lucide-react";
import type { DemoTrade } from "@/lib/types";

import SignalBadge from "./SignalBadge";
import SetupBadge from "./SetupBadge";
import PnLIndicator from "./PnLIndicator";

interface TradeHistoryProps {
  trades: DemoTrade[];
  isLoading: boolean;
}

export default function TradeHistory({ trades, isLoading }: TradeHistoryProps) {
  const [sortBy, setSortBy] = useState<"date" | "pnl" | "r_multiple">("date");

  const sortedTrades = [...trades].sort((a, b) => {
    if (sortBy === "date") {
      return (
        new Date(b.exit_time || b.entry_time).getTime() -
        new Date(a.exit_time || a.entry_time).getTime()
      );
    }
    if (sortBy === "pnl") {
      return (b.pnl || 0) - (a.pnl || 0);
    }
    if (sortBy === "r_multiple") {
      return (b.r_multiple || 0) - (a.r_multiple || 0);
    }
    return 0;
  });

  const handleExport = () => {
    const csvContent = [
      [
        "ID",
        "Symbol",
        "Side",
        "Setup",
        "Entry Time",
        "Exit Time",
        "Entry Price",
        "Exit Price",
        "Size",
        "PnL",
        "R Multiple",
        "Exit Reason",
      ],
      ...sortedTrades.map((t) => [
        t.id,
        t.symbol,
        t.side,
        t.setup_type,
        t.entry_time,
        t.exit_time || "",
        t.entry_price.toFixed(2),
        (t.exit_price || 0).toFixed(2),
        t.size.toFixed(4),
        (t.pnl || 0).toFixed(2),
        (t.r_multiple || 0).toFixed(2),
        t.exit_reason || "",
      ]),
    ]
      .map((row) => row.join(","))
      .join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `demo_trades_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-6">
        <p className="text-muted-foreground">Loading trade history...</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">Trade History</h3>

        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="rounded-lg border border-white/10 bg-muted px-3 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            <option value="date">Sort by Date</option>
            <option value="pnl">Sort by PnL</option>
            <option value="r_multiple">Sort by R Multiple</option>
          </select>

          {trades.length > 0 && (
            <button
              onClick={handleExport}
              className="flex items-center gap-2 rounded-lg bg-primary/10 px-3 py-1 text-sm font-medium text-primary transition hover:bg-primary/20"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </button>
          )}
        </div>
      </div>

      {trades.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <History className="mb-4 h-12 w-12 text-muted-foreground/50" />
          <p className="text-muted-foreground">No trades yet</p>
          <p className="text-sm text-muted-foreground/70">
            Closed trades will appear here
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10">
                <th className="py-3 text-left font-medium text-muted-foreground">
                  Symbol
                </th>
                <th className="py-3 text-left font-medium text-muted-foreground">
                  Side
                </th>
                <th className="py-3 text-left font-medium text-muted-foreground">
                  Setup
                </th>
                <th className="py-3 text-left font-medium text-muted-foreground">
                  Entry
                </th>
                <th className="py-3 text-left font-medium text-muted-foreground">
                  Exit
                </th>
                <th className="py-3 text-right font-medium text-muted-foreground">
                  PnL
                </th>
                <th className="py-3 text-right font-medium text-muted-foreground">
                  R Mult
                </th>
                <th className="py-3 text-left font-medium text-muted-foreground">
                  Reason
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedTrades.map((trade) => (
                <tr
                  key={trade.id}
                  className="border-b border-white/5 transition hover:bg-muted/30"
                >
                  <td className="py-3 font-medium text-foreground">
                    {trade.symbol}
                  </td>
                  <td className="py-3">
                    <SignalBadge side={trade.side} />
                  </td>
                  <td className="py-3">
                    <SetupBadge setupType={trade.setup_type} />
                  </td>
                  <td className="py-3 text-muted-foreground">
                    $
                    {trade.entry_price.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </td>
                  <td className="py-3 text-muted-foreground">
                    {trade.exit_price
                      ? `$${trade.exit_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                      : "—"}
                  </td>
                  <td className="py-3 text-right">
                    <PnLIndicator
                      value={trade.pnl || 0}
                      percentage={
                        trade.pnl && trade.entry_price && trade.size
                          ? (trade.pnl / (trade.entry_price * trade.size)) * 100
                          : 0
                      }
                    />
                  </td>
                  <td className="py-3 text-right font-medium text-foreground">
                    {(trade.r_multiple || 0).toFixed(2)}R
                  </td>
                  <td className="py-3 text-xs text-muted-foreground">
                    {trade.exit_reason || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
