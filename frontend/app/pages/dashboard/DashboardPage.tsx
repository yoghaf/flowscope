"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  Sparkles,
  TrendingUp,
  Volume2,
  Zap,
} from "lucide-react";

import CoinTable from "@/app/components/CoinTable";
import MetricCard from "@/app/components/MetricCard";
import { api } from "@/lib/api";
import { formatFundingRate, formatPercent, getDqStatus, shortSymbol, toNumberOrNull } from "@/lib/formatters";

function dqTone(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized === "FRESH") {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";
  }
  if (["PARTIAL", "STALE", "FALLBACK_ONLY"].includes(normalized)) {
    return "border-amber-500/20 bg-amber-500/10 text-amber-300";
  }
  return "border-red-500/20 bg-red-500/10 text-red-300";
}

function getDashboardRefreshMs(): number {
  return 30_000;
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "1h"],
    staleTime: 10_000,
    refetchInterval: getDashboardRefreshMs(),
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    queryFn: () => api.getDashboard({ symbol: "ALL", timeframe: "1h", snapshotId: "latest" }),
  });

  if (isLoading || !data) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-10 text-muted-foreground">
        Loading dashboard...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="relative">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 via-blue-500/10 to-emerald-500/10 blur-3xl opacity-30" />
        <div className="relative">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">Live Market Data</span>
          </div>
          <h1 className="mb-2 text-4xl font-bold tracking-tight text-foreground">Market Overview</h1>
          <p className="text-lg text-muted-foreground">Real-time crypto flow analytics and accumulation signals</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Accumulation Signals"
          value={data.market_overview.accumulation_signals}
          change={`${data.market_overview.accumulation_signals > 0 ? "+" : ""}${data.market_overview.accumulation_signals}`}
          icon={TrendingUp}
          trend="up"
        />
        <MetricCard
          title="Breakout Watch"
          value={data.market_overview.breakout_watch_signals}
          change={`${data.market_overview.breakout_watch_signals > 0 ? "+" : ""}${data.market_overview.breakout_watch_signals}`}
          icon={Zap}
          trend="up"
        />
        <MetricCard
          title="OI Market Trend"
          value={data.market_overview.oi_market_trend}
          change={data.market_overview.oi_market_trend}
          icon={Activity}
          trend={
            data.market_overview.oi_market_trend === "Bullish"
              ? "up"
              : data.market_overview.oi_market_trend === "Bearish"
                ? "down"
                : "neutral"
          }
        />
        <MetricCard
          title="Volume Spikes"
          value={data.market_overview.volume_spikes}
          change={`${data.market_overview.volume_spikes > 0 ? "+" : ""}${data.market_overview.volume_spikes}`}
          icon={Volume2}
          trend="neutral"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-card/50 backdrop-blur-xl transition-all duration-300 hover:border-white/20">
            <div className="border-b border-white/10 px-6 py-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Top Signals</h2>
                  <p className="mt-0.5 text-sm text-muted-foreground">Strongest accumulation patterns detected</p>
                </div>
                <div className="rounded-lg border border-primary/20 bg-primary/10 px-3 py-1.5">
                  <span className="text-xs font-semibold text-primary">{data.top_signals.length} Active</span>
                </div>
              </div>
            </div>
            <CoinTable rows={data.top_signals} timeframe="1h" variant="dashboard" />
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all duration-300 hover:border-white/20">
            <div className="mb-5 flex items-center gap-2">
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-2">
                <ArrowUpRight className="h-4 w-4 text-emerald-400" />
              </div>
              <h3 className="font-semibold text-foreground">OI Leaders</h3>
            </div>
            <div className="space-y-2">
              {data.oi_leaders.map((coin, index) => (
                <Link
                  key={coin.symbol}
                  href={`/coin/${coin.symbol}?timeframe=${coin.timeframe}&snapshot_id=latest`}
                  className="group flex items-center justify-between rounded-xl p-3 transition-all hover:bg-white/5"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-5 w-5 items-center justify-center rounded-md bg-white/5 text-xs font-semibold text-muted-foreground">
                      {index + 1}
                    </span>
                    <span className="font-semibold text-foreground transition-colors group-hover:text-primary">
                      {shortSymbol(coin.symbol)}
                    </span>
                  </div>
                  <span className="font-semibold text-emerald-400">
                    {formatPercent(coin.flow_metrics.oi_change_1h)}
                  </span>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${dqTone(getDqStatus(coin, coin.timeframe))}`}>
                    {getDqStatus(coin, coin.timeframe)}
                  </span>
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all duration-300 hover:border-white/20">
            <div className="mb-5 flex items-center gap-2">
              <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-2">
                <Volume2 className="h-4 w-4 text-blue-400" />
              </div>
              <h3 className="font-semibold text-foreground">Volume Spikes</h3>
            </div>
            <div className="space-y-2">
              {data.volume_leaders.map((coin, index) => (
                <Link
                  key={coin.symbol}
                  href={`/coin/${coin.symbol}?timeframe=${coin.timeframe}&snapshot_id=latest`}
                  className="group flex items-center justify-between rounded-xl p-3 transition-all hover:bg-white/5"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-5 w-5 items-center justify-center rounded-md bg-white/5 text-xs font-semibold text-muted-foreground">
                      {index + 1}
                    </span>
                    <span className="font-semibold text-foreground transition-colors group-hover:text-primary">
                      {shortSymbol(coin.symbol)}
                    </span>
                  </div>
                  <span className="font-semibold text-blue-400">
                    {formatPercent(coin.flow_metrics.volume_change_1h)}
                  </span>
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all duration-300 hover:border-white/20">
            <div className="mb-5 flex items-center gap-2">
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-2">
                <Activity className="h-4 w-4 text-amber-400" />
              </div>
              <h3 className="font-semibold text-foreground">Funding Extremes</h3>
            </div>
            <div className="space-y-2">
              {data.funding_extremes.map((coin, index) => (
                (() => {
                  const fundingRate = toNumberOrNull(coin.funding_rate);

                  return (
                    <Link
                      key={coin.symbol}
                      href={`/coin/${coin.symbol}?timeframe=${coin.timeframe}&snapshot_id=latest`}
                      className="group flex items-center justify-between rounded-xl p-3 transition-all hover:bg-white/5"
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex h-5 w-5 items-center justify-center rounded-md bg-white/5 text-xs font-semibold text-muted-foreground">
                          {index + 1}
                        </span>
                        <span className="font-semibold text-foreground transition-colors group-hover:text-primary">
                          {shortSymbol(coin.symbol)}
                        </span>
                      </div>
                      <span
                        className={
                          fundingRate === null
                            ? "font-semibold text-muted-foreground"
                            : fundingRate >= 0
                              ? "font-semibold text-emerald-400"
                              : "font-semibold text-red-400"
                        }
                      >
                        {formatFundingRate(fundingRate)}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${dqTone(getDqStatus(coin, coin.timeframe))}`}>
                        {getDqStatus(coin, coin.timeframe)}
                      </span>
                    </Link>
                  );
                })()
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-card/50 backdrop-blur-xl transition-all duration-300 hover:border-white/20">
        <div className="border-b border-white/10 px-6 py-5">
          <h2 className="text-xl font-semibold text-foreground">Flow Activity Heatmap</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">Real-time signal strength visualization</p>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-5">
            {data.heatmap.map((item) => {
              const intensity = item.value / 100;
              const colorScheme =
                item.signal === "Breakout Watch"
                  ? { bg: `rgba(16, 185, 129, ${intensity * 0.3})`, border: "border-emerald-500/20", text: "text-emerald-400" }
                  : item.signal === "Accumulation"
                    ? { bg: `rgba(59, 130, 246, ${intensity * 0.3})`, border: "border-blue-500/20", text: "text-blue-400" }
                    : item.signal === "Short Squeeze"
                      ? { bg: `rgba(245, 158, 11, ${intensity * 0.3})`, border: "border-amber-500/20", text: "text-amber-400" }
                      : item.signal === "Long Squeeze"
                        ? { bg: `rgba(239, 68, 68, ${intensity * 0.3})`, border: "border-red-500/20", text: "text-red-400" }
                        : { bg: `rgba(148, 163, 184, ${intensity * 0.2})`, border: "border-slate-500/20", text: "text-slate-400" };

              return (
                <Link
                  key={item.symbol}
                  href={`/coin/${item.symbol}USDT?timeframe=${item.timeframe}&snapshot_id=latest`}
                  className={`group relative flex aspect-square flex-col items-center justify-center overflow-hidden rounded-xl border p-4 transition-all duration-300 hover:scale-105 ${colorScheme.border}`}
                  style={{ backgroundColor: colorScheme.bg }}
                >
                  <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
                  <span className={`relative mb-1 text-base font-bold ${colorScheme.text}`}>{item.symbol}</span>
                  <span className="relative text-xs font-semibold text-muted-foreground">{item.value}</span>
                  <div className="absolute bottom-2 left-2 right-2 h-1 overflow-hidden rounded-full bg-white/10">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${item.value}%` }} />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
