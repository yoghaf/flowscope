"use client";

import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowUpRight, ShieldCheck, ShieldX } from "lucide-react";

import { api } from "@/lib/api";
import type { SetupPerformance } from "@/lib/types";

function formatTradeSample(item: { closed_trades?: number; open_trades?: number; trades: number }) {
  const closedTrades = item.closed_trades ?? item.trades;
  const openTrades = item.open_trades ?? 0;
  return {
    closedTrades,
    openTrades,
    totalTrades: item.trades,
  };
}

function formatRrValue(item: { rr_ratio: number; winrate: number; closed_trades?: number; trades: number }) {
  const closedTrades = item.closed_trades ?? item.trades;
  if (closedTrades === 0) {
    return "--";
  }
  if (item.winrate >= 1 && item.rr_ratio === 0) {
    return "--";
  }
  return item.rr_ratio.toFixed(2);
}

function formatWinrateValue(item: { winrate: number; closed_trades?: number; trades: number }) {
  const closedTrades = item.closed_trades ?? item.trades;
  if (closedTrades === 0) {
    return "--";
  }
  return `${Math.round(item.winrate * 100)}%`;
}

function formatExpectancyValue(item: { expectancy: number; closed_trades?: number; trades: number }) {
  const closedTrades = item.closed_trades ?? item.trades;
  if (closedTrades === 0) {
    return "--";
  }
  return `${item.expectancy.toFixed(2)}%`;
}

function SetupSummaryCard({
  title,
  icon,
  setup,
  emptyText,
}: {
  title: string;
  icon: ReactNode;
  setup?: SetupPerformance;
  emptyText: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
      <div className="mb-4 flex items-center gap-2">
        {icon}
        <h3 className="font-semibold text-foreground">{title}</h3>
      </div>
      {setup ? (
        <div className="space-y-2 text-sm text-muted-foreground">
          <p className="text-lg font-semibold text-foreground">{setup.setup_type}</p>
          <p>Closed trades: {formatTradeSample(setup).closedTrades}</p>
          <p>Open trades: {formatTradeSample(setup).openTrades}</p>
          <p>Wins / Losses: {setup.wins ?? 0} / {setup.losses ?? 0}</p>
          <p>Breakevens: {setup.breakevens ?? 0}</p>
          <p>Winrate: {formatWinrateValue(setup)}</p>
          <p>Expectancy: {formatExpectancyValue(setup)}</p>
        </div>
      ) : (
        <p className="text-muted-foreground">{emptyText}</p>
      )}
    </div>
  );
}

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
        <p className="mt-2 text-sm text-muted-foreground">Winrate and expectancy only use closed `win/loss` trades. Open trades and breakevens are shown separately.</p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Closed Trades</p>
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
        <SetupSummaryCard
          title="Best Setup"
          icon={<ArrowUpRight className="h-5 w-5 text-emerald-400" />}
          setup={bestSetup}
          emptyText="No closed setup data yet."
        />
        <SetupSummaryCard
          title="Worst Setup"
          icon={<ShieldX className="h-5 w-5 text-red-400" />}
          setup={worstSetup}
          emptyText="Need at least two distinct setups with closed trades."
        />
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
                  <span>Closed</span>
                  <span className="text-foreground">{formatTradeSample(setup).closedTrades}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Open</span>
                  <span className="text-foreground">{formatTradeSample(setup).openTrades}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Winrate</span>
                  <span className="text-foreground">{formatWinrateValue(setup)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Expectancy</span>
                  <span className={setup.expectancy >= 0 ? "text-emerald-300" : "text-red-300"}>
                    {formatExpectancyValue(setup)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Wins / Losses</span>
                  <span className="text-foreground">{setup.wins ?? 0} / {setup.losses ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Breakevens</span>
                  <span className="text-foreground">{setup.breakevens ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>RR</span>
                  <span className="text-foreground">{formatRrValue(setup)}</span>
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
                    <span className="text-foreground">{formatWinrateValue(regime)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Expectancy</span>
                    <span className={regime.expectancy >= 0 ? "text-emerald-300" : "text-red-300"}>
                      {formatExpectancyValue(regime)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Wins / Losses</span>
                    <span className="text-foreground">{regime.wins ?? 0} / {regime.losses ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Breakevens</span>
                    <span className="text-foreground">{regime.breakevens ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>RR</span>
                    <span className="text-foreground">{formatRrValue(regime)}</span>
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
