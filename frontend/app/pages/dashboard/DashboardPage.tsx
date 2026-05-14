"use client";

import Link from "next/link";
import { useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowUpRight, HelpCircle, Sparkles, TrendingUp, Volume2, Zap } from "lucide-react";

import { api } from "@/lib/api";
import {
  formatAge,
  getDecisionTone,
  getDisplayDecision,
  getDqLabel,
  getDqStatus,
  getFallbackFields,
  getHumanLabel,
  getHumanReason,
  getProvenanceValue,
  getReadinessTone,
  getScenarioDisplay,
  getStructureDisplay,
  getSystemReadiness,
  isReliable,
  scoreToPercent,
  shortSymbol,
  toNumberOrNull,
} from "@/lib/formatters";
import type { AssetSnapshot, Timeframe } from "@/lib/types";

const DASHBOARD_TIMEFRAME: Timeframe = "15m";

function getDashboardRefreshMs(): number {
  return 30_000;
}

function tone(status: string): string {
  const normalized = status.toUpperCase();
  if (["ALLOW", "FRESH", "ALIGNED", "OK", "RELIABLE"].includes(normalized)) {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }
  if (["WATCHLIST", "PARTIAL", "STALE", "FALLBACK_ONLY", "UNRELIABLE", "PENALTY"].includes(normalized)) {
    return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  }
  if (["BLOCK", "MISSING", "NO_DATA", "INVALID"].includes(normalized)) {
    return "border-red-500/30 bg-red-500/10 text-red-300";
  }
  return "border-white/10 bg-white/5 text-slate-300";
}

function countBy(items: string[]): Array<[string, number]> {
  const counts = new Map<string, number>();
  items.forEach((item) => counts.set(item, (counts.get(item) ?? 0) + 1));
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
}

function pipelineConfidence(asset: AssetSnapshot): number {
  return scoreToPercent(asset.action_opportunity_score ?? asset.reliability_score ?? asset.score);
}

function FoundationRow({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="font-semibold text-foreground">{value}/{total}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: dashboardData, isLoading: dashboardLoading } = useQuery({
    queryKey: ["dashboard", "1h"],
    staleTime: 10_000,
    refetchInterval: getDashboardRefreshMs(),
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    queryFn: () => api.getDashboard({ symbol: "ALL", timeframe: "1h", snapshotId: "latest" }),
  });

  const { data: scannerData, isLoading: scannerLoading } = useQuery({
    queryKey: ["dashboard-scanner", DASHBOARD_TIMEFRAME],
    staleTime: 15_000,
    refetchInterval: 20_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    queryFn: () =>
      api.getScanner({
        symbol: "ALL",
        timeframe: DASHBOARD_TIMEFRAME,
        snapshotId: "latest",
      }),
  });

  const assets = scannerData?.items ?? [];

  const command = useMemo(() => {
    const total = assets.length;
    const tradeReady = assets.filter((asset) => getDisplayDecision(asset, DASHBOARD_TIMEFRAME) === "TRADE READY");
    const watchlist = assets.filter((asset) => getDisplayDecision(asset, DASHBOARD_TIMEFRAME) === "WATCHLIST");
    const waiting = assets.filter((asset) => getDisplayDecision(asset, DASHBOARD_TIMEFRAME) === "WAIT");
    const blocked = assets.filter((asset) => getDisplayDecision(asset, DASHBOARD_TIMEFRAME) === "BLOCKED");
    const dataIssues = assets.filter((asset) => getDisplayDecision(asset, DASHBOARD_TIMEFRAME) === "DATA ISSUE");
    const noSetup = assets.filter((asset) => getDisplayDecision(asset, DASHBOARD_TIMEFRAME) === "NO SETUP");

    const oiReliable = assets.filter((asset) => isReliable(getProvenanceValue(asset, "oi_delta_reliable", DASHBOARD_TIMEFRAME))).length;
    const fundingReliable = assets.filter((asset) => isReliable(getProvenanceValue(asset, "funding_reliable", DASHBOARD_TIMEFRAME))).length;
    const liquidationFresh = assets.filter((asset) => {
      const source = String(getProvenanceValue(asset, "liquidation_source", DASHBOARD_TIMEFRAME) ?? "missing");
      return source !== "missing";
    }).length;
    const ratioValid = assets.filter((asset) => {
      const fallback = getFallbackFields(asset, DASHBOARD_TIMEFRAME);
      const takerSource = String(getProvenanceValue(asset, "taker_ratio_source", DASHBOARD_TIMEFRAME) ?? "missing");
      const lsSource = String(getProvenanceValue(asset, "long_short_ratio_source", DASHBOARD_TIMEFRAME) ?? "missing");
      return !fallback.some((field) => ["taker_ratio", "ls_ratio", "long_short_ratio"].includes(field)) && takerSource !== "missing" && lsSource !== "missing";
    }).length;

    const dqDistribution = countBy(assets.map((asset) => getDqStatus(asset, DASHBOARD_TIMEFRAME)));
    const blockDistribution = countBy(
      assets
        .filter((asset) => getDisplayDecision(asset, DASHBOARD_TIMEFRAME) !== "TRADE READY")
        .map((asset) => getHumanReason(asset, DASHBOARD_TIMEFRAME)),
    ).slice(0, 8);
    const stateDistribution = countBy(assets.map((asset) => asset.market_interpretation?.state ?? asset.market_state ?? "unknown")).slice(0, 4);

    const closest = assets
      .filter((asset) => {
        const decision = getDisplayDecision(asset, DASHBOARD_TIMEFRAME);
        return decision !== "TRADE READY" && decision !== "DATA ISSUE" && decision !== "NO SETUP";
      })
      .sort((a, b) => pipelineConfidence(b) - pipelineConfidence(a))
      .slice(0, 8);
    const dataBlocked = assets
      .filter((asset) => getDisplayDecision(asset, DASHBOARD_TIMEFRAME) === "DATA ISSUE")
      .sort((a, b) => pipelineConfidence(b) - pipelineConfidence(a))
      .slice(0, 8);
    const noSetupRows = assets
      .filter((asset) => getDisplayDecision(asset, DASHBOARD_TIMEFRAME) === "NO SETUP")
      .sort((a, b) => pipelineConfidence(b) - pipelineConfidence(a))
      .slice(0, 8);
    const readiness = getSystemReadiness(assets, DASHBOARD_TIMEFRAME);

    return {
      total,
      tradeReady,
      watchlist,
      waiting,
      blocked,
      dataIssues,
      noSetup,
      oiReliable,
      fundingReliable,
      liquidationFresh,
      ratioValid,
      dqDistribution,
      blockDistribution,
      stateDistribution,
      closest,
      dataBlocked,
      noSetupRows,
      readiness,
    };
  }, [assets]);

  if (dashboardLoading || scannerLoading) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-10 text-muted-foreground">
        Loading command center...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="relative">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 via-blue-500/10 to-emerald-500/10 blur-3xl opacity-30" />
        <div className="relative">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">Decision Pipeline</span>
          </div>
          <h1 className="mb-2 text-4xl font-bold tracking-tight text-foreground">FlowScope Command Center</h1>
          <p className="text-lg text-muted-foreground">Tradability, blockers, and data foundation health from the live {DASHBOARD_TIMEFRAME} scanner.</p>
        </div>
      </div>

      <SystemReadinessBanner readiness={command.readiness} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-300">Trade Ready</p>
          <p className="mt-2 text-3xl font-bold text-foreground">{command.tradeReady.length}</p>
        </div>
        <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-blue-300">Watchlist</p>
          <p className="mt-2 text-3xl font-bold text-foreground">{command.watchlist.length}</p>
        </div>
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-300">Waiting</p>
          <p className="mt-2 text-3xl font-bold text-foreground">{command.waiting.length}</p>
        </div>
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-red-300">Blocked</p>
          <p className="mt-2 text-3xl font-bold text-foreground">{command.blocked.length}</p>
        </div>
        <div className="rounded-xl border border-orange-500/20 bg-orange-500/10 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-orange-300">Data Issues</p>
          <p className="mt-2 text-3xl font-bold text-foreground">{command.dataIssues.length}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">No Setup</p>
          <p className="mt-2 text-3xl font-bold text-foreground">{command.noSetup.length}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <section className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
          <div className="mb-4 flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            <h2 className="font-semibold text-foreground">Data Foundation Health</h2>
          </div>
          <div className="space-y-4">
            <FoundationRow label="OI ready" value={command.oiReliable} total={command.total} />
            <FoundationRow label="Funding ready" value={command.fundingReliable} total={command.total} />
            <FoundationRow label="Liquidation fresh" value={command.liquidationFresh} total={command.total} />
            <FoundationRow label="Ratio fresh" value={command.ratioValid} total={command.total} />
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {command.dqDistribution.map(([status, count]) => (
              <span key={status} className={`rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${tone(status)}`}>
                {getHumanLabel(status)} {count}
              </span>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
          <div className="mb-4 flex items-center gap-2">
            <Zap className="h-4 w-4 text-amber-300" />
            <h2 className="font-semibold text-foreground">Top Blockers</h2>
          </div>
          <div className="space-y-2">
            {command.blockDistribution.length > 0 ? command.blockDistribution.map(([reason, count]) => (
              <div key={reason} className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm">
                <span className="truncate text-muted-foreground" title={reason}>{reason}</span>
                <span className="font-semibold text-foreground">{count}</span>
              </div>
            )) : (
              <p className="text-sm text-muted-foreground">No block reasons in the current scanner feed.</p>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
          <div className="mb-4 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-blue-300" />
            <h2 className="font-semibold text-foreground">Regime Summary</h2>
          </div>
          <div className="space-y-2">
            {command.stateDistribution.map(([state, count]) => (
              <div key={state} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm">
                <span className="text-muted-foreground">{getHumanLabel(state)}</span>
                <span className="font-semibold text-foreground">{count}</span>
              </div>
            ))}
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <p className="text-muted-foreground">Legacy accumulation</p>
                <p className="mt-1 font-semibold text-foreground">{dashboardData?.market_overview.accumulation_signals ?? 0}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <p className="text-muted-foreground">Volume spikes</p>
                <p className="mt-1 font-semibold text-foreground">{dashboardData?.market_overview.volume_spikes ?? 0}</p>
              </div>
            </div>
          </div>
        </section>
      </div>

      <DecisionTable
        title="Closest To Allow"
        description="High-confidence candidates that are not data-blocked and still need a final condition."
        assets={command.closest}
        action={<Link href="/scanner" className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm font-semibold text-foreground hover:bg-white/10">Open Scanner <ArrowUpRight className="h-4 w-4" /></Link>}
      />

      <DecisionTable
        title="Data-Blocked Watchlist"
        description="Interesting rows where the main problem is stale, missing, or fallback data."
        assets={command.dataBlocked}
      />

      <DecisionTable
        title="No Setup"
        description="Rows where the scanner sees no clear tradable edge right now."
        assets={command.noSetupRows}
      />

      <section className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
        <div className="mb-4 flex items-center gap-2">
          <Volume2 className="h-4 w-4 text-primary" />
          <h2 className="font-semibold text-foreground">Live Heatmap Context</h2>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          {(dashboardData?.heatmap ?? []).slice(0, 16).map((item) => (
            <Link
              key={`${item.symbol}-${item.timeframe}`}
              href={`/coin/${item.symbol}USDT?timeframe=${item.timeframe}&snapshot_id=latest`}
              className="rounded-lg border border-white/10 bg-white/5 p-3 transition-colors hover:bg-white/10"
            >
              <p className="font-semibold text-foreground">{item.symbol}</p>
              <p className="text-xs text-muted-foreground">{item.signal}</p>
              <p className="mt-1 text-sm font-semibold text-primary">{item.value}</p>
            </Link>
          ))}
        </div>
      </section>
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
  const readinessTone = getReadinessTone(readiness.state);
  return (
    <section className={`rounded-2xl border p-4 ${readinessTone}`}>
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

function DecisionTable({
  title,
  description,
  assets,
  action,
}: {
  title: string;
  description: string;
  assets: AssetSnapshot[];
  action?: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-white/10 bg-card/50 backdrop-blur-xl">
      <div className="border-b border-white/10 px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-foreground">{title}</h2>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          {action}
        </div>
      </div>
      {assets.length === 0 ? (
        <p className="p-5 text-sm text-muted-foreground">No rows in this bucket right now.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-5 py-3 text-left">Symbol</th>
                <th className="px-5 py-3 text-left">Decision State</th>
                <th className="px-5 py-3 text-left">DQ</th>
                <th className="px-5 py-3 text-left">Scenario</th>
                <th className="px-5 py-3 text-left">Structure</th>
                <th className="px-5 py-3 text-left">Main Reason</th>
                <th className="px-5 py-3 text-right">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => {
                const dq = getDqStatus(asset, DASHBOARD_TIMEFRAME);
                const decision = getDisplayDecision(asset, DASHBOARD_TIMEFRAME);
                const reason = getHumanReason(asset, DASHBOARD_TIMEFRAME);
                const structure = getStructureDisplay(asset, DASHBOARD_TIMEFRAME);
                const scenario = getScenarioDisplay(asset);
                const oiReliable = isReliable(getProvenanceValue(asset, "oi_delta_reliable", DASHBOARD_TIMEFRAME));
                const fundingAge = toNumberOrNull(getProvenanceValue(asset, "funding_age_seconds", DASHBOARD_TIMEFRAME));
                return (
                  <tr key={`${title}-${asset.symbol}`} className="border-b border-white/5 text-sm hover:bg-white/5">
                    <td className="px-5 py-3 font-semibold text-foreground">
                      <Link href={`/coin/${asset.symbol}?timeframe=${asset.timeframe}&snapshot_id=latest`} className="hover:text-primary">
                        {shortSymbol(asset.symbol)}
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <span title={getHelpText(decision)} className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${getDecisionTone(decision)}`}>
                        {decision}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${tone(dq)}`}>
                        {getDqLabel(asset, DASHBOARD_TIMEFRAME)}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-muted-foreground" title={scenario.includes("Mixed market") ? getHelpText("Mixed market") : undefined}>{scenario}</td>
                    <td className="px-5 py-3 text-muted-foreground" title={structure === "Structural block" ? getHelpText("Structural block") : undefined}>{structure}</td>
                    <td className="px-5 py-3 text-amber-300">
                      <span title={`${reason} - OI ${oiReliable ? "OK" : "not ready"} - funding age ${formatAge(fundingAge)}`}>
                        {reason}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right font-semibold text-foreground">{pipelineConfidence(asset)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
