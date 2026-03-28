"use client";

import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowDownToLine, ArrowUpRight, ShieldCheck, ShieldX } from "lucide-react";

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
  const [capitalPerTrade, setCapitalPerTrade] = useState("100");
  const [isDownloading, setIsDownloading] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["performance", "1h"],
    queryFn: () => api.getPerformance({ symbol: "ALL", timeframe: "1h", snapshotId: "latest" }),
    staleTime: 60_000,
  });

  const parsedCapital = useMemo(() => {
    const value = Number(capitalPerTrade);
    return Number.isFinite(value) && value > 0 ? value : 100;
  }, [capitalPerTrade]);

  async function handleDownloadReport() {
    try {
      setIsDownloading(true);
      const blob = await api.downloadPerformanceReport({
        symbol: "ALL",
        timeframe: "ALL",
        capitalPerTrade: parsedCapital,
      });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `flowscope-performance-report-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setIsDownloading(false);
    }
  }

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

      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-foreground">Download Performance Report</h2>
            <p className="text-sm text-muted-foreground">
              Export every token position with RR, planned target profile, assumed modal per trade, quantity, and realized USD PnL.
            </p>
            <p className="text-xs text-muted-foreground">
              Modal di report dihitung sebagai simulasi fixed capital per trade dari harga entry, jadi ini cocok untuk audit performa riil versi sistem.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex flex-col gap-2 text-sm text-muted-foreground">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Modal / Trade (USDT)</span>
              <input
                type="number"
                min="1"
                step="1"
                value={capitalPerTrade}
                onChange={(event) => setCapitalPerTrade(event.target.value)}
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary/40 focus:bg-white/10 sm:w-48"
              />
            </label>
            <button
              type="button"
              onClick={handleDownloadReport}
              disabled={isDownloading}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm font-semibold text-primary transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <ArrowDownToLine className="h-4 w-4" />
              {isDownloading ? "Preparing CSV..." : "Download CSV Report"}
            </button>
          </div>
        </div>
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
