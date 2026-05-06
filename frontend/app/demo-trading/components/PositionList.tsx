"use client";

import { Clock } from "lucide-react";
import type { DemoPosition } from "@/lib/types";

interface PositionListProps {
  positions: DemoPosition[];
  isLoading: boolean;
}

export default function PositionList({
  positions,
  isLoading,
}: PositionListProps) {
  if (isLoading) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-6">
        <p className="text-muted-foreground">Loading positions...</p>
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 text-center">
        <div className="mb-4 flex justify-center">
          <Clock className="h-12 w-12 text-muted-foreground/50" />
        </div>
        <h3 className="text-lg font-semibold text-foreground">
          No Active Positions
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Positions will appear here when trades are opened
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur">
      <h3 className="mb-4 text-lg font-semibold text-foreground">
        Active Positions
      </h3>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10 text-muted-foreground">
              <th className="py-3 text-left font-medium">Symbol</th>
              <th className="py-3 text-right font-medium">Size</th>
              <th className="py-3 text-right font-medium">Entry</th>
              <th className="py-3 text-right font-medium">Mark</th>
              <th className="py-3 text-right font-medium">PnL</th>
              <th className="py-3 text-right font-medium">ROE</th>
              <th className="py-3 text-left font-medium">Margin</th>
              <th className="py-3 text-center font-medium">Lev</th>
              <th className="py-3 text-right font-medium">Liq Price</th>
              <th className="py-3 text-center font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position, index) => {
              const roe = position.roe ?? 0;
              const roeColor = roe > 0 ? "text-green-500" : roe < 0 ? "text-red-500" : "text-muted-foreground";
              const pnlColor = position.unrealized_pnl > 0 ? "text-green-500" : position.unrealized_pnl < 0 ? "text-red-500" : "text-muted-foreground";
              
              return (
                <tr
                  key={
                    position.id ??
                    `${position.symbol}-${position.entry_time}-${index}`
                  }
                  className="border-b border-white/5 transition hover:bg-white/5"
                >
                  <td className="py-4">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-foreground">{position.symbol}</span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                        position.side === "Long" 
                          ? "bg-green-500/20 text-green-400" 
                          : "bg-red-500/20 text-red-400"
                      }`}>
                        {position.side}
                      </span>
                    </div>
                  </td>
                  <td className="py-4 text-right font-medium text-foreground">
                    {position.size.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-4 text-right text-foreground">
                    ${(position.entry_price ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-4 text-right text-foreground">
                    ${(position.mark_price ?? position.current_price ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className={`py-4 text-right font-medium ${pnlColor}`}>
                    ${(position.unrealized_pnl ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className={`py-4 text-right font-medium ${roeColor}`}>
                    {roe.toFixed(2)}%
                  </td>
                  <td className="py-4 text-left text-foreground">
                    <div className="text-xs">
                      <div className="font-medium">{position.margin_type ?? "CROSS"}</div>
                      <div className="text-muted-foreground">
                        ${(position.isolated_margin ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                    </div>
                  </td>
                  <td className="py-4 text-center text-foreground">
                    <span className="inline-block px-2 py-1 bg-white/10 rounded text-xs font-medium">
                      {position.leverage ?? 1}x
                    </span>
                  </td>
                  <td className="py-4 text-right text-foreground">
                    ${(position.liquidation_price ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-4 text-center">
                    <button
                      className="px-3 py-1.5 text-xs font-medium bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition"
                      onClick={() => {
                        // TODO: Implement close position logic
                        console.log("Close position:", position.symbol);
                      }}
                    >
                      Close
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
