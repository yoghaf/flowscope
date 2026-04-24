"use client";

import { useQuery } from "@tanstack/react-query";
import { Radar, RefreshCw, Target, Flame, TrendingUp, DollarSign } from "lucide-react";
import { api } from "@/lib/api";

function formatUsd(value: number) {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export default function WhaleRadarPage() {
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["whaleRadar"],
    refetchInterval: 60_000,
    queryFn: () => api.getWhaleRadar(),
  });

  if (isLoading || !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-muted-foreground">
          <RefreshCw className="h-8 w-8 animate-spin" />
          <p>Scanning the depths for whale accumulation...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="mb-2 flex items-center gap-3 text-4xl font-bold tracking-tight text-foreground">
          <Radar className="h-10 w-10 text-primary" />
          Whale Accumulation Radar
        </h1>
        <p className="text-lg text-muted-foreground">
          Advanced detection of smart money footprints across 300+ markets
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Squeeze Hunter */}
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <div className="mb-6 flex items-center gap-2 border-b border-white/10 pb-4">
            <Flame className="h-6 w-6 text-orange-500" />
            <div>
              <h2 className="text-xl font-bold text-foreground">Squeeze Hunter</h2>
              <p className="text-sm text-muted-foreground">High negative funding with rising price = Short Squeeze</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/5 text-muted-foreground">
                  <th className="pb-3 font-semibold">Coin</th>
                  <th className="pb-3 text-right font-semibold">Price Chg</th>
                  <th className="pb-3 text-right font-semibold">Funding</th>
                  <th className="pb-3 text-right font-semibold">Volume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.squeeze?.map((item: any) => (
                  <tr key={item.symbol} className="transition-colors hover:bg-white/5">
                    <td className="py-3 font-bold text-foreground">{item.coin}</td>
                    <td className="py-3 text-right text-emerald-400">+{item.px_chg.toFixed(1)}%</td>
                    <td className="py-3 text-right text-rose-400">{item.funding_rate.toFixed(4)}%</td>
                    <td className="py-3 text-right font-mono">{formatUsd(item.volume)}</td>
                  </tr>
                ))}
                {(!data.squeeze || data.squeeze.length === 0) && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-muted-foreground">No active squeeze targets found</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Ambush Strategy */}
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <div className="mb-6 flex items-center gap-2 border-b border-white/10 pb-4">
            <Target className="h-6 w-6 text-emerald-500" />
            <div>
              <h2 className="text-xl font-bold text-foreground">Ambush Scanner</h2>
              <p className="text-sm text-muted-foreground">Low Market Cap + Sideways + OI Spike</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/5 text-muted-foreground">
                  <th className="pb-3 font-semibold">Coin</th>
                  <th className="pb-3 text-right font-semibold">Market Cap</th>
                  <th className="pb-3 text-right font-semibold">Sideways</th>
                  <th className="pb-3 text-right font-semibold">OI Chg (6h)</th>
                  <th className="pb-3 text-right font-semibold">Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.ambush?.map((item: any) => (
                  <tr key={item.symbol} className="transition-colors hover:bg-white/5">
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-foreground">{item.coin}</span>
                        {item.undercurrent && (
                          <span className="rounded bg-indigo-500/20 px-1.5 py-0.5 text-[10px] font-bold text-indigo-400" title="Dark Undercurrent: OI Rising but Price Flat">
                            🎯
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 text-right font-mono">{formatUsd(item.market_cap)}</td>
                    <td className="py-3 text-right">{item.sideways_days}d</td>
                    <td className={`py-3 text-right ${item.oi_change_6h > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {item.oi_change_6h > 0 ? "+" : ""}{item.oi_change_6h.toFixed(1)}%
                    </td>
                    <td className="py-3 text-right">
                      <span className="inline-flex h-6 items-center justify-center rounded-full bg-emerald-500/20 px-2 font-bold text-emerald-400">
                        {item.ambush_score.toFixed(0)}
                      </span>
                    </td>
                  </tr>
                ))}
                {(!data.ambush || data.ambush.length === 0) && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-muted-foreground">No ambush targets found</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Comprehensive */}
      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
        <div className="mb-6 flex items-center gap-2 border-b border-white/10 pb-4">
          <TrendingUp className="h-6 w-6 text-blue-500" />
          <div>
            <h2 className="text-xl font-bold text-foreground">Comprehensive Overview</h2>
            <p className="text-sm text-muted-foreground">Top overall scores balancing all metrics</p>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/5 text-muted-foreground">
                <th className="pb-3 font-semibold">Asset</th>
                <th className="pb-3 font-semibold">Status</th>
                <th className="pb-3 text-right font-semibold">Market Cap</th>
                <th className="pb-3 text-right font-semibold">Sideways</th>
                <th className="pb-3 text-right font-semibold">OI (6h)</th>
                <th className="pb-3 text-right font-semibold">Funding</th>
                <th className="pb-3 text-right font-semibold">Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {data.comprehensive?.map((item: any) => (
                <tr key={item.symbol} className="transition-colors hover:bg-white/5">
                  <td className="py-3 font-bold text-foreground">{item.coin}</td>
                  <td className="py-3 text-xs">
                    <span className="rounded bg-white/5 px-2 py-1 text-muted-foreground">
                      {item.status}
                    </span>
                  </td>
                  <td className="py-3 text-right font-mono">{formatUsd(item.market_cap)}</td>
                  <td className="py-3 text-right">{item.sideways_days}d</td>
                  <td className={`py-3 text-right ${item.oi_change_6h > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {item.oi_change_6h > 0 ? "+" : ""}{item.oi_change_6h.toFixed(1)}%
                  </td>
                  <td className={`py-3 text-right ${item.funding_rate < 0 ? "text-rose-400" : ""}`}>
                    {item.funding_rate.toFixed(4)}%
                  </td>
                  <td className="py-3 text-right">
                    <span className="inline-flex h-6 items-center justify-center rounded-full bg-blue-500/20 px-2 font-bold text-blue-400">
                      {item.comp_score.toFixed(0)}
                    </span>
                  </td>
                </tr>
              ))}
              {(!data.comprehensive || data.comprehensive.length === 0) && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-muted-foreground">No comprehensive targets found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
