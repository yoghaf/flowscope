"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Clock3, HelpCircle, RefreshCw, Search as SearchIcon, SlidersHorizontal } from "lucide-react";

import { api } from "@/lib/api";
import {
  formatAge,
  formatFundingRate,
  formatPipelineLabel,
  formatPrice,
  formatRatio,
  getBlockReasons,
  getDecisionTone,
  getDisplayDecision,
  getDqLabel,
  getDqStatus,
  getFallbackFields,
  getHardFilterReasons,
  getHumanDecisionSubtitle,
  getHumanLabel,
  getHumanReason,
  getProvenanceValue,
  getReadinessTone,
  getReasonLabel,
  getScenarioDisposition,
  getScenarioDisplay,
  getStructureDisplay,
  getStructuralPermission,
  getSystemReadiness,
  isReliable,
  shortSymbol,
  toNumberOrNull,
  type DisplayDecision,
} from "@/lib/formatters";
import {
  buildActionLayer,
  buildExecutionLayer,
  describeExecutionPlan,
  getMarketInterpretation,
  getOpportunityScore,
  setupTypeFromDecision,
} from "@/lib/interpretation";
import type { AssetSnapshot, SetupPerformance, Timeframe } from "@/lib/types";

const SIGNAL_OPTIONS = [
  "All",
  "Accumulation",
  "Breakout Watch",
  "Short Squeeze",
  "Long Squeeze",
  "Neutral",
] as const;

const PIPELINE_FILTERS = ["Trade Ready", "Watchlist", "Waiting", "Blocked", "Data Issues", "No Setup", "All"] as const;
type PipelineFilter = (typeof PIPELINE_FILTERS)[number];

const FILTER_TO_DECISION: Partial<Record<PipelineFilter, DisplayDecision>> = {
  "Trade Ready": "TRADE READY",
  "Data Issues": "DATA ISSUE",
  "No Setup": "NO SETUP",
};

const DECISION_ORDER: Record<DisplayDecision, number> = {
  "TRADE READY": 0,
  "LONG WATCH": 1,
  "SHORT WATCH": 1,
  "LONG TRAP WATCH": 1,
  "SHORT SQUEEZE WATCH": 1,
  WATCHLIST: 1,
  "WAITING CONFIRMATION": 2,
  "WAITING DIRECTION": 2,
  "LEGACY READY / WAIT": 2,
  WAIT: 2,
  AVOID: 3,
  BLOCKED: 3,
  "DATA ISSUE": 4,
  "NO SETUP": 5,
};

function isWatchlistDecision(decision: DisplayDecision): boolean {
  return (
    decision === "WATCHLIST" ||
    decision === "LONG WATCH" ||
    decision === "SHORT WATCH" ||
    decision === "LONG TRAP WATCH" ||
    decision === "SHORT SQUEEZE WATCH"
  );
}

function isWaitingDecision(decision: DisplayDecision): boolean {
  return decision === "WAIT" || decision === "WAITING CONFIRMATION" || decision === "WAITING DIRECTION" || decision === "LEGACY READY / WAIT";
}

function isBlockedDecision(decision: DisplayDecision): boolean {
  return decision === "BLOCKED" || decision === "AVOID";
}

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
  const [timeframe, setTimeframe] = useState<Timeframe>("15m");
  const [signalFilter, setSignalFilter] = useState<(typeof SIGNAL_OPTIONS)[number]>("All");
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);
  const [searchTerm, setSearchTerm] = useState("");
  const [pipelineFilter, setPipelineFilter] = useState<PipelineFilter>("All");
  const [expandedAsset, setExpandedAsset] = useState<string | null>(null);
  const [clockTick, setClockTick] = useState(() => Date.now());

  useEffect(() => {
    const search = searchParams.get("search");
    setSearchTerm(search ?? "");
  }, [searchParams]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setClockTick(Date.now());
    }, 1_000);
    return () => window.clearInterval(interval);
  }, []);

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

  const { data: readinessData } = useQuery({
    queryKey: ["scanner-readiness", "15m"],
    staleTime: 15_000,
    refetchInterval: 20_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    queryFn: () =>
      api.getScanner({
        symbol: "ALL",
        timeframe: "15m",
        snapshotId: "latest",
      }),
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

  const sortedAssets = useMemo(() => {
    return [...(data?.items ?? [])].sort((a, b) => {
      const decisionDelta = DECISION_ORDER[getDisplayDecision(a, timeframe)] - DECISION_ORDER[getDisplayDecision(b, timeframe)];
      if (decisionDelta !== 0) {
        return decisionDelta;
      }
      return getOpportunityScore(b, timeframe) - getOpportunityScore(a, timeframe);
    });
  }, [data, timeframe]);

  const readinessAssets = timeframe === "15m" ? sortedAssets : readinessData?.items ?? [];
  const readiness = useMemo(() => getSystemReadiness(readinessAssets, "15m"), [readinessAssets]);
  const pipelineCounts = useMemo(() => {
    const base = {
      All: sortedAssets.length,
      "Trade Ready": 0,
      Watchlist: 0,
      Waiting: 0,
      Blocked: 0,
      "Data Issues": 0,
      "No Setup": 0,
    } satisfies Record<PipelineFilter, number>;

    sortedAssets.forEach((asset) => {
      const decision = getDisplayDecision(asset, timeframe);
      if (decision === "TRADE READY") {
        base["Trade Ready"] += 1;
      } else if (isWatchlistDecision(decision)) {
        base.Watchlist += 1;
      } else if (isWaitingDecision(decision)) {
        base.Waiting += 1;
      } else if (isBlockedDecision(decision)) {
        base.Blocked += 1;
      } else if (decision === "DATA ISSUE") {
        base["Data Issues"] += 1;
      } else if (decision === "NO SETUP") {
        base["No Setup"] += 1;
      }
    });

    return base;
  }, [sortedAssets, timeframe]);

  const filteredAssets = useMemo(() => {
    return sortedAssets.filter((asset) => {
      const decision = FILTER_TO_DECISION[pipelineFilter];
      const displayDecision = getDisplayDecision(asset, timeframe);
      if (pipelineFilter === "Watchlist") {
        return isWatchlistDecision(displayDecision);
      }
      if (pipelineFilter === "Waiting") {
        return isWaitingDecision(displayDecision);
      }
      if (pipelineFilter === "Blocked") {
        return isBlockedDecision(displayDecision);
      }
      return decision ? displayDecision === decision : true;
    });
  }, [pipelineFilter, sortedAssets, timeframe]);
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
    return clockTick - latestAssetTimestamp.getTime() > 10 * 60 * 1000;
  }, [clockTick, latestAssetTimestamp, timeframe]);

  useEffect(() => {
    if (timeframe !== "15m" || !isFifteenMinuteStale) {
      return;
    }
    const recoveryInterval = window.setInterval(() => {
      void refetch();
    }, 5_000);
    return () => window.clearInterval(recoveryInterval);
  }, [isFifteenMinuteStale, refetch, timeframe]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-2 text-4xl font-bold tracking-tight text-foreground">Decision Scanner</h1>
        <p className="text-lg text-muted-foreground">Entry permission, data reliability, structure, and block reasons in one pass</p>
      </div>

      <SystemReadinessBanner readiness={readiness} />

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

      <div className="rounded-2xl border border-white/10 bg-card/50 p-4 backdrop-blur-xl">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-foreground">Pipeline View</h3>
            <p className="text-sm text-muted-foreground">Filter by decision state before reading individual candidates.</p>
          </div>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-muted-foreground">
            {filteredAssets.length} / {sortedAssets.length} shown
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {PIPELINE_FILTERS.map((filter) => (
            <button
              key={filter}
              onClick={() => setPipelineFilter(filter)}
              className={`rounded-lg border px-3 py-2 text-sm font-semibold transition-colors ${
                pipelineFilter === filter
                  ? "border-primary/40 bg-primary/15 text-primary"
                  : "border-white/10 bg-white/5 text-muted-foreground hover:border-white/20 hover:text-foreground"
              }`}
            >
              {filter} <span className="ml-1 text-xs opacity-75">{pipelineCounts[filter]}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">
            Showing <span className="font-semibold text-foreground">{filteredAssets.length}</span> assets
          </p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1">
              <Clock3 className="h-3.5 w-3.5" />
              API refresh {formattedFetchTime}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1">
              Latest asset ts {formattedLatestAssetTime}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1">
              Auto refresh {timeframe === "15m" ? "20s" : timeframe === "1h" ? "45s" : timeframe === "4h" ? "90s" : "120s"}
            </span>
            {isFifteenMinuteStale ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-red-300">
                15m stale suspected · recovery 5s
              </span>
            ) : null}
          </div>
        </div>
        <div className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-foreground">
          <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          {isFetching ? "Refreshing…" : "Auto refresh active"}
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-card/50 backdrop-blur-xl">
        {isLoading || !data ? (
          <div className="p-6 text-muted-foreground">Loading scanner...</div>
        ) : filteredAssets.length === 0 ? (
          <div className="m-5 rounded-xl border border-white/10 bg-white/5 p-8 text-center text-muted-foreground">
            No assets match this pipeline filter right now.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3 text-left">Symbol</th>
                  <th className="px-4 py-3 text-left">Bias</th>
                  <th className="px-4 py-3 text-left">Setup</th>
                  <th className="px-4 py-3 text-left">Decision State</th>
                  <th className="px-4 py-3 text-left">DQ</th>
                  <th className="px-4 py-3 text-left">Scenario</th>
                  <th className="px-4 py-3 text-left">Structure</th>
                  <th className="px-4 py-3 text-left">Main Reason</th>
                  <th className="px-4 py-3 text-right">Confidence</th>
                  <th className="px-3 py-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredAssets.map((asset) => {
                  const action = buildActionLayer(asset, timeframe);
                  const decision = getDisplayDecision(asset, timeframe);
                  const dqStatus = getDqStatus(asset, timeframe);
                  const dqLabel = getDqLabel(asset, timeframe);
                  const scenario = getScenarioDisplay(asset);
                  const structure = getStructureDisplay(asset, timeframe);
                  const reason = getHumanReason(asset, timeframe);
                  const subtitle = getHumanDecisionSubtitle(asset);
                  const confidence = Math.round(getOpportunityScore(asset, timeframe) * 100);
                  const setupStats = setupMap.get(setupTypeFromDecision(asset.decision_type, asset.position_quality) ?? "");
                  const degradedBadges = getDegradedBadges(asset, timeframe);
                  const rowKey = `${asset.symbol}-${timeframe}`;
                  const isExpanded = expandedAsset === rowKey;

                  return (
                    <Fragment key={rowKey}>
                      <tr className="border-b border-white/5 hover:bg-white/[0.04]">
                        <td className="whitespace-nowrap px-4 py-3">
                          <Link href={`/coin/${asset.symbol}?timeframe=${asset.timeframe}&snapshot_id=latest`} className="font-semibold text-foreground hover:text-primary">
                            {shortSymbol(asset.symbol)}
                          </Link>
                          <p className="text-xs text-muted-foreground">{asset.name}</p>
                        </td>
                        <td className="px-4 py-3 text-foreground">{action.tradeBias}</td>
                        <td className="min-w-[160px] px-4 py-3 text-foreground">
                          <span>{action.setupType}</span>
                          <p className="text-xs text-muted-foreground">{getHumanLabel(asset.decision_type ?? "No-Trade")}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span title={getHelpText(decision)} className={`inline-flex rounded-lg border px-3 py-1.5 text-[11px] font-bold uppercase tracking-wide ${getDecisionTone(decision)}`}>
                            {decision}
                          </span>
                          <p className="mt-1 max-w-[180px] text-xs text-muted-foreground">{subtitle}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span title={dqStatus.toUpperCase() === "STALE" ? "Data stale: wait for a fresh snapshot before trusting the setup." : undefined} className={`inline-flex rounded-lg border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${dqStatus.toUpperCase() === "FRESH" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-orange-500/25 bg-orange-500/10 text-orange-300"}`}>
                            {dqLabel}
                          </span>
                        </td>
                        <td className="min-w-[150px] px-4 py-3 text-muted-foreground" title={scenario.includes("Mixed market") ? getHelpText("Mixed market") : undefined}>{scenario}</td>
                        <td className="min-w-[140px] px-4 py-3 text-muted-foreground" title={structure === "Structural block" ? getHelpText("Structural block") : undefined}>{structure}</td>
                        <td className="min-w-[220px] px-4 py-3">
                          <p className="font-medium text-foreground">{reason}</p>
                          {degradedBadges.length > 0 ? (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {degradedBadges.map((badge) => (
                                <span key={badge.label} title={badge.help} className="rounded-full border border-orange-500/20 bg-orange-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-orange-300">
                                  {badge.label}
                                </span>
                              ))}
                            </div>
                          ) : null}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="inline-flex items-center gap-2">
                            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/10">
                              <div className="h-full rounded-full bg-primary" style={{ width: `${confidence}%` }} />
                            </div>
                            <span className="w-9 font-semibold text-foreground">{confidence}%</span>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-right">
                          <button
                            type="button"
                            onClick={() => setExpandedAsset(isExpanded ? null : rowKey)}
                            className="rounded-lg border border-white/10 bg-white/5 p-2 text-muted-foreground hover:text-foreground"
                            aria-label={`Toggle ${shortSymbol(asset.symbol)} details`}
                          >
                            <ChevronDown className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                          </button>
                        </td>
                      </tr>
                      {isExpanded ? (
                        <tr className="border-b border-white/10 bg-white/[0.025]">
                          <td colSpan={10} className="px-5 py-5">
                            <ScannerDetails asset={asset} timeframe={timeframe} setupStats={setupStats} />
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function getHelpText(item: string): string | undefined {
  if (item === "DATA ISSUE") {
    return "This asset is not tradable because a required data source is stale, missing, or unreliable.";
  }
  if (item === "OI not ready") {
    return "Open interest data is not clean enough yet for this decision.";
  }
  if (item === "Ratio not fresh") {
    return "Taker or long/short ratio data is missing, stale, or using fallback values.";
  }
  if (item === "Structural block") {
    return "Market structure blocks execution even if other flow signals look interesting.";
  }
  if (item === "Mixed market") {
    return "Signals are conflicting, so the scanner is asking you to observe instead of trade.";
  }
  return undefined;
}

function SystemReadinessBanner({ readiness }: { readiness: ReturnType<typeof getSystemReadiness> }) {
  const tone = getReadinessTone(readiness.state);
  return (
    <section className={`rounded-2xl border p-4 ${tone}`}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-xs font-bold uppercase tracking-wider">System Readiness: {readiness.state}</p>
            <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
          </div>
          <p className="mt-1 text-sm text-foreground">{readiness.explanation}</p>
        </div>
        <div className="flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-wide">
          <span className="rounded-full border border-white/10 bg-black/10 px-2.5 py-1">DQ fresh {readiness.dqFresh}/{readiness.total}</span>
          <span title={getHelpText("OI not ready")} className="rounded-full border border-white/10 bg-black/10 px-2.5 py-1">OI ready {readiness.oiReliable}/{readiness.total}</span>
          <span className="rounded-full border border-white/10 bg-black/10 px-2.5 py-1">Funding ready {readiness.fundingReliable}/{readiness.total}</span>
          <span className="rounded-full border border-white/10 bg-black/10 px-2.5 py-1">Liq fresh {readiness.liquidationFresh}/{readiness.total}</span>
          <span title={getHelpText("Ratio not fresh")} className="rounded-full border border-white/10 bg-black/10 px-2.5 py-1">Ratio fresh {readiness.ratioValid}/{readiness.total}</span>
        </div>
      </div>
    </section>
  );
}

function getDegradedBadges(asset: AssetSnapshot, timeframe: Timeframe): Array<{ label: string; help?: string }> {
  const badges: Array<{ label: string; help?: string }> = [];
  const fallbackFields = getFallbackFields(asset, timeframe);
  const oiReliable = isReliable(getProvenanceValue(asset, "oi_delta_reliable", timeframe));
  const fundingReliable = isReliable(getProvenanceValue(asset, "funding_reliable", timeframe));
  const liquidationSource = String(getProvenanceValue(asset, "liquidation_source", timeframe) ?? "missing");
  const takerSource = String(getProvenanceValue(asset, "taker_ratio_source", timeframe) ?? "missing");
  const longShortSource = String(getProvenanceValue(asset, "long_short_ratio_source", timeframe) ?? "missing");

  if (!oiReliable) {
    badges.push({ label: "OI not ready", help: getHelpText("OI not ready") });
  }
  if (!fundingReliable) {
    badges.push({ label: "Funding not ready" });
  }
  if (liquidationSource === "missing" || fallbackFields.includes("liquidation")) {
    badges.push({ label: "Liq not fresh" });
  }
  if (takerSource === "missing" || longShortSource === "missing" || fallbackFields.some((field) => ["taker_ratio", "ls_ratio", "long_short_ratio"].includes(field))) {
    badges.push({ label: "Ratio not fresh", help: getHelpText("Ratio not fresh") });
  }

  return badges;
}

function detailItems(items: Array<string | null | undefined>): string[] {
  return items.filter((item): item is string => Boolean(item));
}

function DetailBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h4>
      <div className="space-y-1.5">
        {items.length > 0 ? (
          items.map((item, index) => (
            <p key={`${title}-${index}-${item}`} className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-foreground">
              {item}
            </p>
          ))
        ) : (
          <p className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-muted-foreground">None</p>
        )}
      </div>
    </div>
  );
}

function ScannerDetails({
  asset,
  timeframe,
  setupStats,
}: {
  asset: AssetSnapshot;
  timeframe: Timeframe;
  setupStats?: SetupPerformance;
}) {
  const marketInterpretation = getMarketInterpretation(asset, timeframe);
  const action = buildActionLayer(asset, timeframe);
  const execution = buildExecutionLayer(asset, timeframe);
  const executionPlanTitle = describeExecutionPlan(action, execution, asset.decision_type);
  const hardReasons = getHardFilterReasons(asset);
  const blockReasons = getBlockReasons(asset);
  const fallbackFields = getFallbackFields(asset, timeframe);
  const fundingAge = toNumberOrNull(getProvenanceValue(asset, "funding_age_seconds", timeframe));
  const liquidationAge = toNumberOrNull(getProvenanceValue(asset, "liquidation_age_seconds", timeframe));
  const takerAge = toNumberOrNull(getProvenanceValue(asset, "taker_ratio_age_seconds", timeframe));
  const longShortAge = toNumberOrNull(getProvenanceValue(asset, "long_short_ratio_age_seconds", timeframe));

  const entryRange =
    execution.entryMin === null || execution.entryMax === null
      ? "No armed entry"
      : execution.entryMin === execution.entryMax
        ? formatPrice(execution.entryMin)
        : `${formatPrice(Math.min(execution.entryMin, execution.entryMax))} - ${formatPrice(Math.max(execution.entryMin, execution.entryMax))}`;

  return (
    <div className="grid gap-5 lg:grid-cols-4">
      <DetailBlock
        title="Interpretation / risk / execution"
        items={detailItems([
          marketInterpretation.interpretation,
          marketInterpretation.action_rationale,
          `Execution: ${executionPlanTitle}`,
          `Entry: ${entryRange}`,
          `Risk: trap ${Math.round(marketInterpretation.trap_risk * 100)}%, conflict ${Math.round(marketInterpretation.conflict_score * 100)}%`,
        ])}
      />
      <DetailBlock
        title="Classifier trace"
        items={detailItems([
          `State: ${marketInterpretation.state}`,
          `Intent: ${asset.position_intent ?? "None"}`,
          `Quality: ${asset.position_quality ?? "Neutral"}`,
          `Decision: ${asset.decision_type ?? "No-Trade"}`,
          `Setup stats: ${setupStats?.validated ? "validated" : "experimental"}`,
        ])}
      />
      <DetailBlock
        title="Data provenance"
        items={detailItems([
          `DQ: ${formatPipelineLabel(getDqStatus(asset, timeframe))}`,
          `Funding: ${formatFundingRate(asset.funding_rate)} - age ${formatAge(fundingAge)}`,
          `Liquidation: ${String(getProvenanceValue(asset, "liquidation_source", timeframe) ?? "missing")} - age ${formatAge(liquidationAge)}`,
          `Taker ratio: ${formatRatio(asset.taker_buy_sell_ratio)} - age ${formatAge(takerAge)}`,
          `Long/short ratio: ${formatRatio(asset.long_short_ratio)} - age ${formatAge(longShortAge)}`,
          fallbackFields.length > 0 ? `Fallbacks: ${fallbackFields.join(", ")}` : "Fallbacks: none",
        ])}
      />
      <DetailBlock
        title="Raw backend reasons"
        items={detailItems([
          ...hardReasons.map((reason) => `${reason} - ${getReasonLabel(reason)}`),
          ...blockReasons.map((reason) => `${reason} - ${getReasonLabel(reason)}`),
          `scenario_disposition=${getScenarioDisposition(asset)}`,
          `final_structural_permission=${getStructuralPermission(asset, timeframe)}`,
          `final_entry_permission=${asset.final_entry_permission ?? "UNKNOWN"}`,
        ])}
      />
    </div>
  );
}
