"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  Eye,
  Gauge,
  ListChecks,
  Search,
  ShieldAlert,
  Signal,
  Sparkles,
  XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import {
  type SystemReadiness,
  formatAge,
  formatEntryLocationPhase,
  formatEntryLocationQuality,
  formatMarketRelativeStatus,
  formatRelativeScore,
  formatSemanticGateDecision,
  getDirectionAlignmentStatus,
  getDisplayDecision,
  getDqLabel,
  getDqStatus,
  getEntryLocationGuidance,
  getEntryLocationPhase,
  getEntryLocationQuality,
  getEntryLocationReason,
  getFallbackFields,
  getHardFilterReasons,
  getHumanDecisionSubtitle,
  getHumanLabel,
  getHumanReason,
  getLayer5DirectionBias,
  getLayer5WatchStatus,
  getMainBlockReason,
  getMarketIndependenceScore,
  getMarketRelativeStatus,
  getObservabilityDecisionLabel,
  getObservabilityDecisionTone,
  getOriginalWatchLabel,
  getProvenanceValue,
  getReadinessTone,
  getReasonLabel,
  getRelativeStrengthScore,
  getRelativeWeaknessScore,
  getScenarioDisplay,
  getScenarioDisposition,
  getScenarioLabel,
  getSystemReadiness,
  isReliable,
  isRiskEntryLocationPhase,
  isUnknownMarketRelativeStatus,
  scoreToPercent,
  shouldShowRelativeScore,
  shortSymbol,
  toNumberOrNull,
} from "@/lib/formatters";
import type { AssetSnapshot, Timeframe } from "@/lib/types";

const DASHBOARD_TIMEFRAME: Timeframe = "15m";
const SECTION_LIMIT = 10;

type CandidateBucket =
  | "tradeReady"
  | "watchlist"
  | "neutralWatch"
  | "waiting"
  | "strategyBlocked"
  | "dataBlocked"
  | "noSetup";

type DashboardAction = "WAIT" | "OBSERVE" | "REVIEW WATCHLIST" | "REVIEW TRADE READY" | "CHECK BACKEND";

const BLOCKER_MEANINGS: Record<string, string> = {
  "No clear edge": "Most assets have no dominant setup.",
  "Scenario not allowed yet": "Setups are forming but not confirmed.",
  "OI data not reliable": "OI data is not ready.",
  "Data quality degraded": "Some required data is stale, missing, or fallback.",
  "Ratio not fresh": "Ratio data is not fresh.",
  "Structural block": "Price structure is noisy or unsafe.",
  "Volatile noise, no structure": "Price structure is noisy or unsafe.",
  "OI climax / exhaustion risk": "Flow may be late; avoid chasing.",
  "Taker/price divergence": "Aggression and price are not confirming each other.",
  "Taker price divergence": "Aggression and price are not confirming each other.",
  "Mixed market context": "The market is conflicted and needs confirmation.",
  "Clarity below threshold": "The setup is too unclear to act on.",
  "Higher timeframe not aligned": "The larger trend does not support this setup.",
  "Flow alignment too weak": "Flow is not strong enough yet.",
};

function getDashboardRefreshMs(): number {
  return 30_000;
}

function humanStatus(value: string | null | undefined): string {
  return getHumanLabel(value).replace(/^Dq /i, "Data ");
}

function statusTone(status: string): string {
  const normalized = status.toUpperCase();
  if (["READY", "FRESH", "ALIGNED", "OK", "RELIABLE", "TRADE READY"].includes(normalized)) {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }
  if (["WATCHLIST", "WAIT", "WARMING_UP", "PARTIAL", "PENALTY"].includes(normalized)) {
    return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  }
  if (["DATA ISSUE", "DATA_BLOCKED", "DEGRADED", "STALE", "FALLBACK_ONLY"].includes(normalized)) {
    return "border-orange-500/30 bg-orange-500/10 text-orange-300";
  }
  if (["BLOCKED", "AVOID / RISK", "AVOID_RISK", "AVOID_LAYER5_RISK", "BLOCK", "MISSING", "NO_DATA", "INVALID"].includes(normalized)) {
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

function observabilityPriority(asset: AssetSnapshot): number {
  const direction = getLayer5DirectionBias(asset);
  const semantic = getSemanticReadiness(asset);
  const market = getMarketRelativeStatus(asset, DASHBOARD_TIMEFRAME);
  const entryPhase = getEntryLocationPhase(asset, DASHBOARD_TIMEFRAME);
  let priority = pipelineConfidence(asset);
  if (direction === "LONG_WATCH" || direction === "SHORT_WATCH") priority += 120;
  if (semantic === "WAIT_SCENARIO" && getHumanReason(asset, DASHBOARD_TIMEFRAME) !== "No trade reason available") priority += 80;
  if (market === "RELATIVE_STRENGTH" || market === "RELATIVE_WEAKNESS") priority += 60;
  if (entryPhase === "HEALTHY_CONTINUATION" || entryPhase === "EARLY_BUILD" || entryPhase === "WAIT_PULLBACK") priority += 35;
  return priority;
}

function assetRecord(asset: AssetSnapshot): Record<string, unknown> {
  return asset as unknown as Record<string, unknown>;
}

function optionalText(asset: AssetSnapshot, key: string): string | null {
  const direct = assetRecord(asset)[key];
  if (typeof direct === "string" && direct.trim()) {
    return direct;
  }
  const flow = asset.flow_metrics as unknown as Record<string, unknown> | undefined;
  const value = flow?.[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function getSemanticReadiness(asset: AssetSnapshot): string {
  return optionalText(asset, "v2balanced_semantic_readiness") ?? "NO_SETUP";
}

function getCandidateStage(asset: AssetSnapshot): string {
  return optionalText(asset, "v2balanced_candidate_stage") ?? "NO_SETUP";
}

function isWatchDecision(decision: string): boolean {
  return ["LONG WATCH", "SHORT WATCH", "LONG TRAP WATCH", "SHORT SQUEEZE WATCH", "WATCHLIST"].includes(decision);
}

function isWaitingDecision(decision: string): boolean {
  return ["WAIT", "WAITING CONFIRMATION", "WAITING DIRECTION", "LEGACY READY / WAIT"].includes(decision);
}

function getDirectionLabel(asset: AssetSnapshot): string {
  const layer5Direction = getLayer5DirectionBias(asset);
  if (layer5Direction && layer5Direction !== "NO_DIRECTION") {
    return humanStatus(layer5Direction);
  }
  if (asset.action_bias === "Bullish") {
    return "Long bias";
  }
  if (asset.action_bias === "Bearish") {
    return "Short bias";
  }
  return "No direction";
}

function getRiskLabel(asset: AssetSnapshot): string {
  return asset.execution?.risk_level ?? asset.action_confidence_label ?? "Not scored";
}

function getNeededConfirmation(asset: AssetSnapshot): string {
  const scenario = getScenarioDisposition(asset);
  const direction = getLayer5DirectionBias(asset);
  if (direction === "NEUTRAL_WATCH" || direction === "NO_DIRECTION") {
    return "Clear direction";
  }
  if (scenario === "wait" || scenario === "observe") {
    return "Scenario confirmation";
  }
  return "Clean trigger";
}

function getMissingConfirmation(asset: AssetSnapshot): string {
  const mainReason = getHumanReason(asset, DASHBOARD_TIMEFRAME);
  if (mainReason !== "No trade reason available") {
    return mainReason;
  }
  const scenario = getScenarioDisposition(asset);
  if (scenario === "wait") {
    return "Scenario still waiting";
  }
  if (scenario === "observe") {
    return "Observation only";
  }
  return "Confirmation not present";
}

function getDataIssue(asset: AssetSnapshot): string {
  const dq = getDqStatus(asset, DASHBOARD_TIMEFRAME);
  if (dq !== "FRESH") {
    return getDqLabel(asset, DASHBOARD_TIMEFRAME);
  }
  if (!isReliable(getProvenanceValue(asset, "oi_delta_reliable", DASHBOARD_TIMEFRAME))) {
    return "OI not ready";
  }
  if (getFallbackFields(asset, DASHBOARD_TIMEFRAME).length > 0) {
    return "Fallback data present";
  }
  const takerSource = String(getProvenanceValue(asset, "taker_ratio_source", DASHBOARD_TIMEFRAME) ?? "missing");
  const lsSource = String(getProvenanceValue(asset, "long_short_ratio_source", DASHBOARD_TIMEFRAME) ?? "missing");
  if (takerSource === "missing" || lsSource === "missing") {
    return "Ratio not fresh";
  }
  return "Data not ready";
}

function getAvoidLabel(asset: AssetSnapshot): string {
  const semantic = getSemanticReadiness(asset);
  const entryPhase = getEntryLocationPhase(asset, DASHBOARD_TIMEFRAME);
  const dataIssue = getCandidateStage(asset) === "DATA_BLOCKED" || semantic === "DATA_BLOCKED";
  if (semantic === "AVOID_LAYER5_RISK") {
    return "AVOID_LAYER5_RISK";
  }
  if (["EXHAUSTION_RISK", "DISTRIBUTION_RISK", "ACCUMULATION_RISK", "LATE_CHASE"].includes(entryPhase ?? "")) {
    return entryPhase ?? "AVOID_LAYER5_RISK";
  }
  if (dataIssue) {
    return "DATA_BLOCKED";
  }
  return getMainBlockReason(asset);
}

function hasHardRisk(asset: AssetSnapshot): boolean {
  const semantic = getSemanticReadiness(asset);
  return (
    semantic === "AVOID_LAYER5_RISK" ||
    semantic === "DATA_BLOCKED" ||
    getCandidateStage(asset) === "DATA_BLOCKED" ||
    getLayer5WatchStatus(asset) === "AVOID_HARD_RISK" ||
    isRiskEntryLocationPhase(getEntryLocationPhase(asset, DASHBOARD_TIMEFRAME))
  );
}

function isMainWatchlistCandidate(asset: AssetSnapshot): boolean {
  const direction = getLayer5DirectionBias(asset);
  const semantic = getSemanticReadiness(asset);
  return (
    (direction === "LONG_WATCH" || direction === "SHORT_WATCH") &&
    (semantic === "WAIT_SCENARIO" || semantic === "READY_CANDIDATE") &&
    !hasHardRisk(asset)
  );
}

function isNeutralWatchCandidate(asset: AssetSnapshot): boolean {
  if (hasHardRisk(asset)) {
    return false;
  }
  const decision = getDisplayDecision(asset, DASHBOARD_TIMEFRAME);
  const direction = getLayer5DirectionBias(asset);
  const semantic = getSemanticReadiness(asset);
  return (
    direction === "NO_DIRECTION" ||
    direction === "NEUTRAL_WATCH" ||
    semantic === "WAIT_DIRECTION" ||
    getLayer5WatchStatus(asset).startsWith("WATCHLIST") ||
    (isWatchDecision(decision) && direction !== "LONG_WATCH" && direction !== "SHORT_WATCH")
  );
}

function getLastUpdate(asset: AssetSnapshot): string {
  const oiAge = toNumberOrNull(getProvenanceValue(asset, "oi_close_age_seconds", DASHBOARD_TIMEFRAME));
  const ratioAge = toNumberOrNull(getProvenanceValue(asset, "taker_ratio_age_seconds", DASHBOARD_TIMEFRAME));
  const liqAge = toNumberOrNull(getProvenanceValue(asset, "liquidation_age_seconds", DASHBOARD_TIMEFRAME));
  const ages = [oiAge, ratioAge, liqAge].filter((value): value is number => value !== null);
  return ages.length > 0 ? formatAge(Math.max(...ages)) : formatAge(null);
}

function bucketFor(asset: AssetSnapshot): CandidateBucket {
  const decision = getDisplayDecision(asset, DASHBOARD_TIMEFRAME);
  const stage = getCandidateStage(asset);
  const semantic = getSemanticReadiness(asset);
  if (decision === "DATA ISSUE" || stage === "DATA_BLOCKED" || semantic === "DATA_BLOCKED") {
    return "dataBlocked";
  }
  if (decision === "AVOID" || hasHardRisk(asset)) {
    return "strategyBlocked";
  }
  if (decision === "TRADE READY" || semantic === "READY_CANDIDATE") {
    return "tradeReady";
  }
  if (isMainWatchlistCandidate(asset)) {
    return "watchlist";
  }
  if (isNeutralWatchCandidate(asset)) {
    return "neutralWatch";
  }
  if (isWaitingDecision(decision) || semantic === "WAIT_SCENARIO" || semantic === "WAIT_DIRECTION") {
    return "waiting";
  }
  if (decision === "NO SETUP") {
    return "noSetup";
  }
  return "strategyBlocked";
}

function getReadinessCopy(readiness: SystemReadiness): { title: string; meaning: string; action: string } {
  switch (readiness.state) {
    case "READY":
      return {
        title: "System Ready",
        meaning: "The 15m data foundation is healthy enough to review live decisions.",
        action: "Review trade-ready candidates first, then watchlist names.",
      };
    case "WARMING_UP":
      return {
        title: "System Warming Up",
        meaning: "Live signals are paused until the 15m data foundation is clean.",
        action: "Wait for the next clean 15m rollover. Do not treat current rows as trade signals.",
      };
    case "DEGRADED":
      return {
        title: "System Degraded",
        meaning: "Some required data sources are stale or missing.",
        action: "Use the dashboard for context only. Avoid acting on data-blocked rows.",
      };
    case "NO_DATA":
      return {
        title: "No Live Data",
        meaning: "FlowScope does not have active 15m scanner data right now.",
        action: "Check the backend collector and database connection before reviewing signals.",
      };
  }
}

function getFoundationSummary(readiness: SystemReadiness): { label: string; explanation: string } {
  if (readiness.total === 0) {
    return { label: "No data", explanation: "No active 15m scanner feed is available." };
  }
  const weak: string[] = [];
  if (readiness.dqFresh < readiness.total) weak.push("data quality");
  if (readiness.oiReliable < readiness.total) weak.push("OI");
  if (readiness.ratioValid < readiness.total) weak.push("ratio");
  if (readiness.fundingReliable < readiness.total) weak.push("funding");
  if (readiness.liquidationFresh < readiness.total) weak.push("liquidation");

  if (weak.length === 0) {
    return { label: "Healthy", explanation: "Data foundation is healthy across required 15m sources." };
  }

  const healthy: string[] = [];
  if (readiness.fundingReliable === readiness.total) healthy.push("funding");
  if (readiness.liquidationFresh === readiness.total) healthy.push("liquidation");
  const label = readiness.state === "WARMING_UP" ? "Warming up" : "Degraded";
  const healthyText = healthy.length > 0 ? `${healthy.join(" and ")} are healthy, but ` : "";
  return {
    label,
    explanation: `${healthyText}${weak.join(" and ")} ${weak.length === 1 ? "is" : "are"} not ready.`,
  };
}

function getCurrentAction(readiness: SystemReadiness, buckets: Record<CandidateBucket, AssetSnapshot[]>): {
  action: DashboardAction;
  title: string;
  description: string;
} {
  if (readiness.state === "NO_DATA") {
    return {
      action: "CHECK BACKEND",
      title: "Check backend",
      description: "No active scanner data is available. Confirm collectors and API health before using the dashboard.",
    };
  }
  if (readiness.state === "WARMING_UP") {
    return {
      action: "WAIT",
      title: "Wait for clean data",
      description: "The system is warming up. No actionable trade signals yet. Wait for clean 15m data.",
    };
  }
  if (buckets.tradeReady.length > 0) {
    return {
      action: "REVIEW TRADE READY",
      title: "Review trade-ready candidates",
      description: "At least one row has passed the human decision checks. Review risk before acting.",
    };
  }
  if (buckets.watchlist.length > 0) {
    return {
      action: "REVIEW WATCHLIST",
      title: "Review watchlist",
      description: "No trade-ready rows, but some clean candidates are worth watching for confirmation.",
    };
  }
  if (buckets.waiting.length > 0) {
    return {
      action: "OBSERVE",
      title: "Observe only",
      description: "Setups are forming, but confirmation is missing. Wait for clearer structure or direction.",
    };
  }
  return {
    action: "WAIT",
    title: "No actionable edge",
    description: "The current market does not show a clean trade-ready or watchlist setup.",
  };
}

function getRegimeInterpretation(assets: AssetSnapshot[]): string {
  if (assets.length === 0) {
    return "No active market context is available yet.";
  }
  const mixedOrWait = assets.filter((asset) => {
    const scenario = getScenarioLabel(asset);
    const disposition = getScenarioDisposition(asset);
    return scenario === "mixed_context" || disposition === "wait" || disposition === "observe";
  }).length;
  const noSetup = assets.filter((asset) => bucketFor(asset) === "noSetup").length;
  if (mixedOrWait / assets.length >= 0.5) {
    return "Market is mostly unclear. Better to wait for cleaner structure.";
  }
  if (noSetup / assets.length >= 0.5) {
    return "Most assets have no clear edge. Patience is the correct action.";
  }
  return "There are pockets of activity, but only confirmed rows should be treated as actionable.";
}

function isClosestToAllow(asset: AssetSnapshot): boolean {
  const direction = getLayer5DirectionBias(asset);
  const quality = getEntryLocationQuality(asset, DASHBOARD_TIMEFRAME);
  return (
    getDirectionAlignmentStatus(asset) === "ALIGNED" &&
    (direction === "LONG_WATCH" || direction === "SHORT_WATCH") &&
    !isUnknownMarketRelativeStatus(getMarketRelativeStatus(asset, DASHBOARD_TIMEFRAME)) &&
    (quality === "WAIT_CONFIRMATION" || quality === "GOOD_LOCATION") &&
    getHardFilterReasons(asset).length === 0 &&
    !hasHardRisk(asset)
  );
}

function FoundationRow({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="font-semibold text-foreground">
          {value}/{total}
        </span>
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
    const buckets: Record<CandidateBucket, AssetSnapshot[]> = {
      tradeReady: [],
      watchlist: [],
      neutralWatch: [],
      waiting: [],
      strategyBlocked: [],
      dataBlocked: [],
      noSetup: [],
    };

    assets.forEach((asset) => {
      buckets[bucketFor(asset)].push(asset);
    });

    Object.values(buckets).forEach((bucket) => {
      bucket.sort((a, b) => observabilityPriority(b) - observabilityPriority(a));
    });

    const readiness = getSystemReadiness(assets, DASHBOARD_TIMEFRAME);
    const currentAction = getCurrentAction(readiness, buckets);
    const foundation = getFoundationSummary(readiness);
    const closest = assets.filter(isClosestToAllow).sort((a, b) => observabilityPriority(b) - observabilityPriority(a));
    const topBlockers = countBy(
      assets
        .filter((asset) => bucketFor(asset) !== "tradeReady")
        .map((asset) => getHumanReason(asset, DASHBOARD_TIMEFRAME)),
    ).slice(0, 6);

    return {
      buckets,
      readiness,
      currentAction,
      foundation,
      closest,
      topBlockers,
      total: assets.length,
      regimeInterpretation: getRegimeInterpretation(assets),
    };
  }, [assets]);

  if (dashboardLoading || scannerLoading) {
    return (
      <div className="rounded-lg border border-white/10 bg-card/50 p-10 text-muted-foreground">
        Loading dashboard...
      </div>
    );
  }

  const funnel = [
    { label: "Assets Scanned", value: command.total, tone: "border-white/10 bg-white/5 text-slate-200" },
    { label: "Trade Ready", value: command.buckets.tradeReady.length, tone: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" },
    { label: "Watchlist", value: command.buckets.watchlist.length, tone: "border-blue-500/30 bg-blue-500/10 text-blue-300" },
    { label: "Neutral Watch", value: command.buckets.neutralWatch.length, tone: "border-white/10 bg-white/5 text-slate-300" },
    { label: "Waiting", value: command.buckets.waiting.length, tone: "border-amber-500/30 bg-amber-500/10 text-amber-300" },
    { label: "Avoid / Risk", value: command.buckets.strategyBlocked.length, tone: "border-red-500/30 bg-red-500/10 text-red-300" },
    { label: "Data Blocked", value: command.buckets.dataBlocked.length, tone: "border-orange-500/30 bg-orange-500/10 text-orange-300" },
    { label: "No Setup", value: command.buckets.noSetup.length, tone: "border-white/10 bg-white/5 text-slate-300" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <span className="text-xs font-semibold uppercase tracking-wider text-primary">Decision Pipeline</span>
        </div>
        <h1 className="mb-2 text-3xl font-bold tracking-tight text-foreground md:text-4xl">FlowScope Dashboard</h1>
        <p className="max-w-3xl text-base text-muted-foreground">
          A trader-readable view of readiness, action, candidates, and why the system is not tradable.
        </p>
      </div>

      <SystemReadinessHero readiness={command.readiness} />
      <CurrentActionPanel currentAction={command.currentAction} readiness={command.readiness} />
      <DecisionFunnel items={funnel} />

      <CandidateSection bucket="tradeReady" title="Trade Ready" rows={command.buckets.tradeReady} />
      <CandidateSection bucket="watchlist" title="Watchlist" rows={command.buckets.watchlist} />
      <CandidateSection bucket="neutralWatch" title="Neutral Watch / No Clear Edge" rows={command.buckets.neutralWatch} />
      <CandidateSection bucket="waiting" title="Waiting for Confirmation" rows={command.buckets.waiting} />
      <CandidateSection bucket="strategyBlocked" title="Avoid / Risk" rows={command.buckets.strategyBlocked} />
      <CandidateSection bucket="dataBlocked" title="Data Blocked" rows={command.buckets.dataBlocked} />
      <CandidateSection bucket="noSetup" title="No Setup" rows={command.buckets.noSetup} />

      <ClosestToAllow assets={command.closest} allDataBlocked={command.total > 0 && command.buckets.dataBlocked.length === command.total} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <DataFoundationHealth readiness={command.readiness} foundation={command.foundation} />
        <TopBlockers blockers={command.topBlockers} />
        <RegimeSummary interpretation={command.regimeInterpretation} assets={assets} />
      </div>

      <LiveHeatmapContext items={dashboardData?.heatmap ?? []} />
    </div>
  );
}

function SystemReadinessHero({ readiness }: { readiness: SystemReadiness }) {
  const copy = getReadinessCopy(readiness);
  const tone = getReadinessTone(readiness.state);
  const chips = [
    `DQ fresh: ${readiness.dqFresh}/${readiness.total}`,
    `OI ready: ${readiness.oiReliable}/${readiness.total}`,
    `Ratio fresh: ${readiness.ratioValid}/${readiness.total}`,
    `Funding ready: ${readiness.fundingReliable}/${readiness.total}`,
    `Liquidation fresh: ${readiness.liquidationFresh}/${readiness.total}`,
  ];

  return (
    <section className={`rounded-lg border p-5 ${tone}`}>
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-3xl">
          <p className="text-xs font-bold uppercase tracking-wider">System Readiness</p>
          <h2 className="mt-2 text-2xl font-bold text-foreground">{copy.title}</h2>
          <p className="mt-2 text-sm text-foreground/90">{copy.meaning}</p>
          <p className="mt-4 rounded-lg border border-white/10 bg-black/10 p-3 text-sm font-semibold text-foreground">
            {copy.action}
          </p>
        </div>
        <div className="flex max-w-xl flex-wrap gap-2">
          {chips.map((chip) => (
            <span key={chip} className="rounded-full border border-white/10 bg-black/10 px-3 py-1.5 text-xs font-semibold text-foreground">
              {chip}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function CurrentActionPanel({
  currentAction,
  readiness,
}: {
  currentAction: ReturnType<typeof getCurrentAction>;
  readiness: SystemReadiness;
}) {
  const icon = {
    WAIT: Clock3,
    OBSERVE: Eye,
    "REVIEW WATCHLIST": ListChecks,
    "REVIEW TRADE READY": CheckCircle2,
    "CHECK BACKEND": AlertTriangle,
  }[currentAction.action];
  const Icon = icon;

  return (
    <section className="rounded-lg border border-white/10 bg-card/60 p-5 backdrop-blur-xl">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-3">
          <div className={`rounded-lg border p-3 ${statusTone(readiness.state)}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-primary">Current Action</p>
            <h2 className="mt-1 text-2xl font-bold text-foreground">{currentAction.action}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{currentAction.description}</p>
          </div>
        </div>
        <Link href="/scanner" className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-foreground hover:bg-white/10">
          Open Scanner
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  );
}

function DecisionFunnel({ items }: { items: Array<{ label: string; value: number; tone: string }> }) {
  return (
    <section className="rounded-lg border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
      <div className="mb-4 flex items-center gap-2">
        <Gauge className="h-4 w-4 text-primary" />
        <h2 className="font-semibold text-foreground">Decision Funnel</h2>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        {items.map((item) => (
          <div key={item.label} className={`rounded-lg border p-3 ${item.tone}`}>
            <p className="text-xs font-semibold uppercase tracking-wide opacity-90">{item.label}</p>
            <p className="mt-2 text-2xl font-bold text-foreground">{item.value}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function CandidateSection({ bucket, title, rows }: { bucket: CandidateBucket; title: string; rows: AssetSnapshot[] }) {
  const limitedRows = rows.slice(0, SECTION_LIMIT);
  const empty = {
    tradeReady: "No trade-ready candidates. Do not force a trade.",
    watchlist: "No clean watchlist candidates. Wait for better structure.",
    neutralWatch: "No neutral watch rows. Directionless or no-edge rows are not being promoted here.",
    waiting: "No rows are waiting for confirmation right now.",
    strategyBlocked: "No strategy-blocked candidates in the current feed.",
    dataBlocked: "No data-blocked rows. Data foundation is not the main blocker here.",
    noSetup: "No no-setup rows in the current feed.",
  }[bucket];
  const sectionNote =
    bucket === "strategyBlocked"
      ? "Avoid/Risk rows are not entries. They are blocked setups or reversal-monitor candidates."
      : null;

  return (
    <section className="overflow-hidden rounded-lg border border-white/10 bg-card/50 backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
        <div>
          <h2 className="font-semibold text-foreground">{title}</h2>
          <p className="text-sm text-muted-foreground">
            Showing top {Math.min(rows.length, SECTION_LIMIT)} of {rows.length}.{" "}
            <Link href="/scanner" className="font-semibold text-primary hover:underline">
              Full list in Scanner
            </Link>
          </p>
          {sectionNote ? <p className="mt-1 text-xs font-medium text-red-200/80">{sectionNote}</p> : null}
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(title.toUpperCase())}`}>{rows.length}</span>
      </div>
      {limitedRows.length === 0 ? (
        <p className="px-5 py-6 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <CandidateHeader bucket={bucket} />
            <tbody>
              {limitedRows.map((asset) => (
                <CandidateRow key={`${bucket}-${asset.symbol}`} bucket={bucket} asset={asset} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function CandidateHeader({ bucket }: { bucket: CandidateBucket }) {
  const columns: Record<CandidateBucket, string[]> = {
    tradeReady: ["Symbol", "Direction", "Setup", "Reason", "Confidence", "Risk", "Action"],
    watchlist: ["Symbol", "Watch Type", "Market", "Entry Location", "Reason", "Needed Confirmation"],
    neutralWatch: ["Symbol", "State", "Market", "Entry Location", "Reason"],
    waiting: ["Symbol", "Bias", "Market", "Entry Location", "Missing Confirmation"],
    strategyBlocked: ["Symbol", "Avoid Reason", "Market", "Entry Location", "Scenario", "Confidence"],
    dataBlocked: ["Symbol", "Main Data Issue", "DQ", "OI", "Ratio", "Funding", "Last Update"],
    noSetup: ["Symbol", "Market State", "Reason", "Confidence"],
  };
  return (
    <thead>
      <tr className="border-b border-white/10 text-xs uppercase tracking-wider text-muted-foreground">
        {columns[bucket].map((column, index) => (
          <th key={column} className={`px-5 py-3 ${index === columns[bucket].length - 1 ? "text-right" : "text-left"}`}>
            {column}
          </th>
        ))}
      </tr>
    </thead>
  );
}

function MarketRelativeCell({ asset }: { asset: AssetSnapshot }) {
  const status = getMarketRelativeStatus(asset, DASHBOARD_TIMEFRAME);
  const score =
    getRelativeStrengthScore(asset, DASHBOARD_TIMEFRAME) ??
    getRelativeWeaknessScore(asset, DASHBOARD_TIMEFRAME) ??
    getMarketIndependenceScore(asset, DASHBOARD_TIMEFRAME);
  const showScore = shouldShowRelativeScore(status, score);
  return (
    <div>
      <p className="font-medium text-foreground">{formatMarketRelativeStatus(status)}</p>
      {showScore ? <p className="mt-1 text-xs text-muted-foreground">Score {formatRelativeScore(score)}</p> : null}
    </div>
  );
}

function EntryLocationCell({ asset }: { asset: AssetSnapshot }) {
  const phase = getEntryLocationPhase(asset, DASHBOARD_TIMEFRAME);
  const quality = getEntryLocationQuality(asset, DASHBOARD_TIMEFRAME);
  const reason = getEntryLocationReason(asset, DASHBOARD_TIMEFRAME);
  return (
    <div title={reason ?? undefined}>
      <p className="font-medium text-foreground">{formatEntryLocationPhase(phase)}</p>
      <p className="mt-1 text-xs text-muted-foreground">{formatEntryLocationQuality(quality)}</p>
    </div>
  );
}

function CandidateRow({ bucket, asset }: { bucket: CandidateBucket; asset: AssetSnapshot }) {
  const symbol = (
    <Link href={`/coin/${asset.symbol}?timeframe=${asset.timeframe}&snapshot_id=latest`} className="font-semibold text-foreground hover:text-primary">
      {shortSymbol(asset.symbol)}
    </Link>
  );
  const confidence = `${pipelineConfidence(asset)}%`;
  const reason = getHumanReason(asset, DASHBOARD_TIMEFRAME);
  const decision = getDisplayDecision(asset, DASHBOARD_TIMEFRAME);
  const subtitle = getHumanDecisionSubtitle(asset);
  const decisionLabel = getObservabilityDecisionLabel(asset, DASHBOARD_TIMEFRAME);
  const decisionTone = getObservabilityDecisionTone(asset, DASHBOARD_TIMEFRAME);
  const rowClass = "border-b border-white/5 text-sm hover:bg-white/5";
  const cellClass = "px-5 py-3 text-muted-foreground";
  const rightCell = "px-5 py-3 text-right font-semibold text-foreground";

  if (bucket === "tradeReady") {
    return (
      <tr className={rowClass}>
        <td className="px-5 py-3">{symbol}</td>
        <td className={cellClass}>{getDirectionLabel(asset)}</td>
        <td className={cellClass}>{humanStatus(asset.setup_type ?? asset.signal)}</td>
        <td className={cellClass}>{reason}</td>
        <td className={cellClass}>{confidence}</td>
        <td className={cellClass}>{getRiskLabel(asset)}</td>
        <td className={rightCell}>Review risk</td>
      </tr>
    );
  }

  if (bucket === "watchlist") {
    return (
      <tr className={rowClass}>
        <td className="px-5 py-3">{symbol}</td>
        <td className={cellClass}>
          <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${decisionTone}`}>
            {decisionLabel}
          </span>
        </td>
        <td className={cellClass}><MarketRelativeCell asset={asset} /></td>
        <td className={cellClass}><EntryLocationCell asset={asset} /></td>
        <td className={cellClass}>
          <p className="text-foreground">{reason}</p>
          <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
        </td>
        <td className={rightCell}>{getNeededConfirmation(asset)}</td>
      </tr>
    );
  }

  if (bucket === "neutralWatch") {
    return (
      <tr className={rowClass}>
        <td className="px-5 py-3">{symbol}</td>
        <td className={cellClass}>{formatSemanticGateDecision(decision)}</td>
        <td className={cellClass}><MarketRelativeCell asset={asset} /></td>
        <td className={cellClass}><EntryLocationCell asset={asset} /></td>
        <td className={rightCell}>{reason}</td>
      </tr>
    );
  }

  if (bucket === "waiting") {
    return (
      <tr className={rowClass}>
        <td className="px-5 py-3">{symbol}</td>
        <td className={cellClass}>{humanStatus(asset.action_bias ?? "Neutral")}</td>
        <td className={cellClass}><MarketRelativeCell asset={asset} /></td>
        <td className={cellClass}><EntryLocationCell asset={asset} /></td>
        <td className={rightCell}>{getMissingConfirmation(asset)}</td>
      </tr>
    );
  }

  if (bucket === "strategyBlocked") {
    const avoidLabel = getAvoidLabel(asset);
    const locationGuidance = getEntryLocationGuidance(asset, DASHBOARD_TIMEFRAME);
    const originalWatch = getOriginalWatchLabel(asset);
    return (
      <tr className={rowClass}>
        <td className="px-5 py-3">{symbol}</td>
        <td className={cellClass}>
          <p className="font-medium text-foreground">{formatSemanticGateDecision(avoidLabel)}</p>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground">{avoidLabel}</p>
          {locationGuidance ? <p className="mt-2 max-w-[240px] text-xs font-medium text-red-200/90">{locationGuidance}</p> : null}
          {originalWatch ? <p className="mt-1 text-[11px] text-muted-foreground">{originalWatch}</p> : null}
        </td>
        <td className={cellClass}><MarketRelativeCell asset={asset} /></td>
        <td className={cellClass}><EntryLocationCell asset={asset} /></td>
        <td className={cellClass}>{getScenarioDisplay(asset)}</td>
        <td className={rightCell}>{confidence}</td>
      </tr>
    );
  }

  if (bucket === "dataBlocked") {
    const oiReady = isReliable(getProvenanceValue(asset, "oi_delta_reliable", DASHBOARD_TIMEFRAME)) ? "Ready" : "Not ready";
    const ratioReady = getFallbackFields(asset, DASHBOARD_TIMEFRAME).length === 0 ? "Fresh" : "Not fresh";
    const fundingReady = isReliable(getProvenanceValue(asset, "funding_reliable", DASHBOARD_TIMEFRAME)) ? "Ready" : "Not ready";
    return (
      <tr className={rowClass}>
        <td className="px-5 py-3">{symbol}</td>
        <td className={cellClass}>{getDataIssue(asset)}</td>
        <td className={cellClass}>{getDqLabel(asset, DASHBOARD_TIMEFRAME)}</td>
        <td className={cellClass}>{oiReady}</td>
        <td className={cellClass}>{ratioReady}</td>
        <td className={cellClass}>{fundingReady}</td>
        <td className={rightCell}>{getLastUpdate(asset)}</td>
      </tr>
    );
  }

  return (
    <tr className={rowClass}>
      <td className="px-5 py-3">{symbol}</td>
      <td className={cellClass}>{humanStatus(asset.market_interpretation?.state ?? asset.market_state)}</td>
      <td className={cellClass}>{reason}</td>
      <td className={rightCell}>{confidence}</td>
    </tr>
  );
}

function ClosestToAllow({ assets, allDataBlocked }: { assets: AssetSnapshot[]; allDataBlocked: boolean }) {
  return (
    <section className="overflow-hidden rounded-lg border border-white/10 bg-card/50 backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
        <div>
          <h2 className="font-semibold text-foreground">Closest To Allow</h2>
          <p className="text-sm text-muted-foreground">Non-data-blocked candidates nearest to a usable setup.</p>
        </div>
        <Link href="/scanner" className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm font-semibold text-foreground hover:bg-white/10">
          Open Scanner
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </div>
      {assets.length === 0 ? (
        <p className="px-5 py-6 text-sm text-muted-foreground">
          {allDataBlocked
            ? "No closest-to-allow candidates while data foundation is warming up."
            : "No close candidates right now. The market has no clean near-entry edge."}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 p-5 md:grid-cols-2 xl:grid-cols-4">
          {assets.slice(0, 8).map((asset) => (
            <div key={`closest-${asset.symbol}`} className="rounded-lg border border-white/10 bg-white/5 p-4">
              <div className="flex items-center justify-between gap-3">
                <Link href={`/coin/${asset.symbol}?timeframe=${asset.timeframe}&snapshot_id=latest`} className="font-semibold text-foreground hover:text-primary">
                  {shortSymbol(asset.symbol)}
                </Link>
                <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${getObservabilityDecisionTone(asset, DASHBOARD_TIMEFRAME)}`}>
                  {getObservabilityDecisionLabel(asset, DASHBOARD_TIMEFRAME)}
                </span>
              </div>
              <p className="mt-3 text-sm text-muted-foreground">{getHumanReason(asset, DASHBOARD_TIMEFRAME)}</p>
              <p className="mt-1 text-xs text-muted-foreground">{getHumanDecisionSubtitle(asset)}</p>
              <p className="mt-2 text-xs text-muted-foreground">Confidence {pipelineConfidence(asset)}%</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function DataFoundationHealth({ readiness, foundation }: { readiness: SystemReadiness; foundation: { label: string; explanation: string } }) {
  return (
    <section className="rounded-lg border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
      <div className="mb-4 flex items-center gap-2">
        <Activity className="h-4 w-4 text-primary" />
        <h2 className="font-semibold text-foreground">Data Foundation Health</h2>
      </div>
      <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(foundation.label.toUpperCase())}`}>
        {foundation.label}
      </span>
      <p className="mt-3 text-sm text-muted-foreground">{foundation.explanation}</p>
      <div className="mt-5 space-y-4">
        <FoundationRow label="DQ fresh" value={readiness.dqFresh} total={readiness.total} />
        <FoundationRow label="OI ready" value={readiness.oiReliable} total={readiness.total} />
        <FoundationRow label="Ratio fresh" value={readiness.ratioValid} total={readiness.total} />
        <FoundationRow label="Funding ready" value={readiness.fundingReliable} total={readiness.total} />
        <FoundationRow label="Liquidation fresh" value={readiness.liquidationFresh} total={readiness.total} />
      </div>
    </section>
  );
}

function TopBlockers({ blockers }: { blockers: Array<[string, number]> }) {
  return (
    <section className="rounded-lg border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
      <div className="mb-4 flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-amber-300" />
        <h2 className="font-semibold text-foreground">Top Blockers</h2>
      </div>
      <div className="space-y-3">
        {blockers.length > 0 ? (
          blockers.map(([reason, count]) => (
            <div key={reason} className="rounded-lg border border-white/10 bg-white/5 p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold text-foreground">{reason}</p>
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs font-semibold text-foreground">{count}</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{BLOCKER_MEANINGS[reason] ?? "This condition prevents a clean trade decision."}</p>
            </div>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">No blockers in the current scanner feed.</p>
        )}
      </div>
    </section>
  );
}

function RegimeSummary({ interpretation, assets }: { interpretation: string; assets: AssetSnapshot[] }) {
  const stateDistribution = countBy(assets.map((asset) => humanStatus(asset.market_interpretation?.state ?? asset.market_state))).slice(0, 4);
  return (
    <section className="rounded-lg border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-blue-300" />
        <h2 className="font-semibold text-foreground">Regime Summary</h2>
      </div>
      <p className="rounded-lg border border-white/10 bg-white/5 p-3 text-sm text-foreground">{interpretation}</p>
      <div className="mt-4 space-y-2">
        {stateDistribution.map(([state, count]) => (
          <div key={state} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm">
            <span className="text-muted-foreground">{state}</span>
            <span className="font-semibold text-foreground">{count}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function LiveHeatmapContext({ items }: { items: Array<{ symbol: string; timeframe: Timeframe; signal: string; value: number }> }) {
  const legend = [
    { label: "Breakout Watch", icon: Signal, tone: "text-blue-300" },
    { label: "Neutral", icon: Search, tone: "text-slate-300" },
    { label: "Data Issue", icon: AlertTriangle, tone: "text-orange-300" },
    { label: "No Setup", icon: XCircle, tone: "text-slate-400" },
  ];

  return (
    <section className="rounded-lg border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Signal className="h-4 w-4 text-primary" />
            <h2 className="font-semibold text-foreground">Live Heatmap Context</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Context only. Heatmap tiles are not trade signals.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {legend.map(({ label, icon: Icon, tone }) => (
            <span key={label} className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-muted-foreground">
              <Icon className={`h-3.5 w-3.5 ${tone}`} />
              {label}
            </span>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        {items.slice(0, 16).map((item) => (
          <Link
            key={`${item.symbol}-${item.timeframe}`}
            href={`/coin/${item.symbol}USDT?timeframe=${item.timeframe}&snapshot_id=latest`}
            className="rounded-lg border border-white/10 bg-white/5 p-3 transition-colors hover:bg-white/10"
          >
            <p className="font-semibold text-foreground">{item.symbol}</p>
            <p className="text-xs text-muted-foreground">{humanStatus(item.signal)}</p>
            <p className="mt-1 text-sm font-semibold text-primary">{item.value}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
