"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowUpRight, ShieldCheck, ShieldX } from "lucide-react";

import { api } from "@/lib/api";

export default function PerformancePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["performance", "1h"],
    queryFn: () => api.getPerformance({ symbol: "ALL", timeframe: "1h", snapshotId: "latest" }),
    staleTime: 60_000,
  });

  if (isLoading || !data) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-10 text-muted-foreground">
        Loading performance...
      </div>
    );
  }

  const bestSetup = data.setups.find((item) => item.setup_type === data.best_setup);
  const worstSetup = data.setups.find((item) => item.setup_type === data.worst_setup);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-2 text-4xl font-bold tracking-tight text-foreground">Performance</h1>
        <p className="text-lg text-muted-foreground">How FlowScope setups are performing over time</p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Total Trades</p>
          <p className="text-3xl font-bold text-foreground">{data.total_trades}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Winrate</p>
          <p className="text-3xl font-bold text-emerald-400">{Math.round(data.winrate * 100)}%</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Expectancy</p>
          <p className={`text-3xl font-bold ${data.expectancy >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {data.expectancy.toFixed(2)}%
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Best Setup</p>
          <p className="text-3xl font-bold text-foreground">{data.best_setup ?? "--"}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <div className="mb-4 flex items-center gap-2">
            <ArrowUpRight className="h-5 w-5 text-emerald-400" />
            <h3 className="font-semibold text-foreground">Best Setup</h3>
          </div>
          {bestSetup ? (
            <div className="space-y-2 text-sm text-muted-foreground">
              <p className="text-lg font-semibold text-foreground">{bestSetup.setup_type}</p>
              <p>Trades: {bestSetup.trades}</p>
              <p>Winrate: {Math.round(bestSetup.winrate * 100)}%</p>
              <p>Expectancy: {bestSetup.expectancy.toFixed(2)}%</p>
            </div>
          ) : (
            <p className="text-muted-foreground">No data yet.</p>
          )}
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <div className="mb-4 flex items-center gap-2">
            <ShieldX className="h-5 w-5 text-red-400" />
            <h3 className="font-semibold text-foreground">Worst Setup</h3>
          </div>
          {worstSetup ? (
            <div className="space-y-2 text-sm text-muted-foreground">
              <p className="text-lg font-semibold text-foreground">{worstSetup.setup_type}</p>
              <p>Trades: {worstSetup.trades}</p>
              <p>Winrate: {Math.round(worstSetup.winrate * 100)}%</p>
              <p>Expectancy: {worstSetup.expectancy.toFixed(2)}%</p>
            </div>
          ) : (
            <p className="text-muted-foreground">No data yet.</p>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
        <div className="mb-4 flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <h3 className="font-semibold text-foreground">Setup Breakdown</h3>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.setups.map((setup) => (
            <div key={setup.setup_type} className="rounded-xl border border-white/10 bg-white/5 p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">{setup.setup_type}</p>
                {setup.validated ? (
                  <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                    <ShieldCheck className="h-3 w-3" /> Validated
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
                    Experimental
                  </span>
                )}
              </div>
              <div className="space-y-1 text-xs text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>Trades</span>
                  <span className="text-foreground">{setup.trades}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Winrate</span>
                  <span className="text-foreground">{Math.round(setup.winrate * 100)}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Expectancy</span>
                  <span className={setup.expectancy >= 0 ? "text-emerald-300" : "text-red-300"}>
                    {setup.expectancy.toFixed(2)}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>RR</span>
                  <span className="text-foreground">{setup.rr_ratio.toFixed(2)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {data.regimes && data.regimes.length > 0 ? (
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <div className="mb-4 flex items-center gap-2">
            <Activity className="h-5 w-5 text-amber-400" />
            <h3 className="font-semibold text-foreground">Regime Split</h3>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data.regimes.map((regime) => (
              <div key={regime.regime} className="rounded-xl border border-white/10 bg-white/5 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold text-foreground">{regime.regime}</p>
                  {regime.validated ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                      <ShieldCheck className="h-3 w-3" /> Validated
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
                      Experimental
                    </span>
                  )}
                </div>
                <div className="space-y-1 text-xs text-muted-foreground">
                  <div className="flex items-center justify-between">
                    <span>Trades</span>
                    <span className="text-foreground">{regime.trades}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Winrate</span>
                    <span className="text-foreground">{Math.round(regime.winrate * 100)}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Expectancy</span>
                    <span className={regime.expectancy >= 0 ? "text-emerald-300" : "text-red-300"}>
                      {regime.expectancy.toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>RR</span>
                    <span className="text-foreground">{regime.rr_ratio.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
