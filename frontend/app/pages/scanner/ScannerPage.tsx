"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Clock3, RefreshCw, Search as SearchIcon, SlidersHorizontal } from "lucide-react";

import MarketStateCard from "@/app/components/MarketStateCard";
import { api } from "@/lib/api";
import { setupTypeFromDecision } from "@/lib/interpretation";
import type { SetupPerformance, Timeframe } from "@/lib/types";

const SIGNAL_OPTIONS = [
  "All",
  "Accumulation",
  "Breakout Watch",
  "Short Squeeze",
  "Long Squeeze",
  "Neutral",
] as const;

function getScannerStaleTime(timeframe: Timeframe): number {
  if (timeframe === "15m") {
    return 15_000;
  }
  if (timeframe === "1h") {
    return 30_000;
  }
  return 60_000;
}

function getScannerRefetchInterval(timeframe: Timeframe): number {
  if (timeframe === "15m") {
    return 20_000;
  }
  if (timeframe === "1h") {
    return 45_000;
  }
  if (timeframe === "4h") {
    return 90_000;
  }
  return 120_000;
}

export default function ScannerPage() {
  const searchParams = useSearchParams();
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [signalFilter, setSignalFilter] = useState<(typeof SIGNAL_OPTIONS)[number]>("All");
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    const search = searchParams.get("search");
    setSearchTerm(search ?? "");
  }, [searchParams]);

  const { data, isLoading, isFetching, dataUpdatedAt, refetch } = useQuery({
    queryKey: ["scanner", timeframe, signalFilter, scoreRange, searchTerm],
    staleTime: getScannerStaleTime(timeframe),
    refetchInterval: getScannerRefetchInterval(timeframe),
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    queryFn: () =>
      api.getScanner({
        symbol: "ALL",
        timeframe,
        snapshotId: "latest",
        signalType: signalFilter === "All" ? undefined : signalFilter,
        minScore: scoreRange[0] / 100,
        maxScore: scoreRange[1] / 100,
        search: searchTerm,
      }),
  });

  const { data: performanceData } = useQuery({
    queryKey: ["performance", timeframe],
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    queryFn: () => api.getPerformance({ symbol: "ALL", timeframe, snapshotId: "latest" }),
  });

  const setupMap = useMemo(() => {
    const map = new Map<string, SetupPerformance>();
    if (performanceData?.setups) {
      performanceData.setups.forEach((item) => {
        map.set(item.setup_type, item);
      });
    }
    return map;
  }, [performanceData]);

  const sortedAssets = useMemo(() => data?.items ?? [], [data]);
  const latestAssetTimestamp = useMemo(() => {
    if (!data?.items.length) {
      return null;
    }
    const latest = data.items.reduce<number | null>((max, asset) => {
      const current = new Date(asset.timestamp).getTime();
      if (!Number.isFinite(current)) {
        return max;
      }
      return max === null ? current : Math.max(max, current);
    }, null);
    return latest === null ? null : new Date(latest);
  }, [data]);

  const formattedFetchTime = useMemo(() => {
    if (!dataUpdatedAt) {
      return "--";
    }
    return new Intl.DateTimeFormat("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(dataUpdatedAt));
  }, [dataUpdatedAt]);

  const formattedLatestAssetTime = useMemo(() => {
    if (!latestAssetTimestamp) {
      return "--";
    }
    return new Intl.DateTimeFormat("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(latestAssetTimestamp);
  }, [latestAssetTimestamp]);

  const isFifteenMinuteStale = useMemo(() => {
    if (timeframe !== "15m" || !latestAssetTimestamp) {
      return false;
    }
    return Date.now() - latestAssetTimestamp.getTime() > 10 * 60 * 1000;
  }, [latestAssetTimestamp, timeframe]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-2 text-4xl font-bold tracking-tight text-foreground">Flow Scanner</h1>
        <p className="text-lg text-muted-foreground">Advanced signal detection with real-time filtering</p>
      </div>

      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all hover:border-white/20">
        <div className="mb-6 flex items-center gap-2">
          <SlidersHorizontal className="h-5 w-5 text-primary" />
          <h3 className="font-semibold text-foreground">Filters &amp; Controls</h3>
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-3 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">Timeframe</label>
            <div className="flex gap-2">
              {(["15m", "1h", "4h", "24h"] as const).map((value) => (
                <button
                  key={value}
                  onClick={() => setTimeframe(value)}
                  className={`flex-1 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all duration-200 ${
                    timeframe === value
                      ? "bg-primary text-white shadow-lg shadow-primary/30"
                      : "border border-white/10 bg-white/5 text-muted-foreground hover:border-white/20 hover:bg-white/10"
                  }`}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-3 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">Signal Type</label>
            <select
              value={signalFilter}
              onChange={(event) => setSignalFilter(event.target.value as (typeof SIGNAL_OPTIONS)[number])}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 font-medium text-foreground transition-all focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              {SIGNAL_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-3 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Clarity Range: {scoreRange[0]} - {scoreRange[1]}
            </label>
            <div className="space-y-3">
              <input
                type="range"
                min="0"
                max="100"
                value={scoreRange[0]}
                onChange={(event) =>
                  setScoreRange([
                    Math.min(Number(event.target.value), scoreRange[1]),
                    scoreRange[1],
                  ])
                }
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-white/5 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
              />
              <input
                type="range"
                min="0"
                max="100"
                value={scoreRange[1]}
                onChange={(event) =>
                  setScoreRange([
                    scoreRange[0],
                    Math.max(Number(event.target.value), scoreRange[0]),
                  ])
                }
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-white/5 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
              />
            </div>
          </div>

          <div>
            <label className="mb-3 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">Search Asset</label>
            <div className="relative">
              <SearchIcon className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="BTC, ETH..."
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                className="w-full rounded-xl border border-white/10 bg-white/5 py-2.5 pl-11 pr-4 font-medium text-foreground placeholder:text-muted-foreground transition-all focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">
            Showing <span className="font-semibold text-foreground">{data?.items.length ?? 0}</span> assets
          </p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1">
              <Clock3 className="h-3.5 w-3.5" />
              API refresh {formattedFetchTime}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1">
              Latest asset ts {formattedLatestAssetTime}
            </span>
            {isFifteenMinuteStale ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-red-300">
                15m stale suspected
              </span>
            ) : null}
          </div>
        </div>
        <button
          onClick={() => void refetch()}
          className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-foreground transition-all hover:border-white/20 hover:bg-white/10"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          Refresh Now
        </button>
      </div>

      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all hover:border-white/20">
        {isLoading || !data ? (
          <div className="text-muted-foreground">Loading scanner...</div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {sortedAssets.map((asset) => (
              <MarketStateCard
                key={`${asset.symbol}-${timeframe}`}
                asset={asset}
                timeframe={timeframe}
                setupStats={
                  setupMap.get(
                    setupTypeFromDecision(asset.decision_type, asset.position_quality) ?? "",
                  )
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
