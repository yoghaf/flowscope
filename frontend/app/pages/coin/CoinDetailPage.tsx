"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowLeft, DollarSign, Scale, TrendingUp } from "lucide-react";

import {
  FundingChart,
  LiquidationChart,
  PriceOpenInterestChart,
  VolumeChart,
} from "@/app/components/Charts";
import { api } from "@/lib/api";
import {
  formatAge,
  formatCompactNumber,
  formatFundingRate,
  formatPercent,
  formatPrice,
  formatRatio,
  getDqStatus,
  getFallbackFields,
  getProvenanceValue,
  isReliable,
  normalizeReasonList,
  shortSymbol,
  toNumberOrNull,
} from "@/lib/formatters";
import {
  buildActionLayer,
  buildExecutionLayer,
  describeExecutionPlan,
  getOpportunityScore,
  getMarketInterpretation,
  setupTypeFromDecision,
} from "@/lib/interpretation";
import type { FlowMetrics, Timeframe } from "@/lib/types";

function getDetailRefetchInterval(timeframe: Timeframe): number {
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

function metricTone(value: number | null | undefined): string {
  const numericValue = toNumberOrNull(value);
  if (numericValue === null) {
    return "font-semibold text-muted-foreground";
  }

  return numericValue >= 0 ? "font-semibold text-emerald-400" : "font-semibold text-red-400";
}

const BAR_COLORS: Record<string, string> = {
  emerald: "bg-emerald-500",
  red: "bg-red-500",
  amber: "bg-amber-500",
  blue: "bg-blue-500",
  purple: "bg-purple-500",
  slate: "bg-slate-500",
};

function MetricRow({
  label,
  value,
  format,
  colorize,
  barColor,
}: {
  label: string;
  value: number | boolean | null | undefined;
  format: "percent" | "decimal" | "bar" | "zscore" | "ratio" | "price" | "funding" | "boolean";
  colorize?: boolean;
  barColor?: string;
}) {
  const num = format === "boolean" ? null : toNumberOrNull(value as number | null | undefined);

  if (format === "boolean") {
    const boolVal = value === true || value === 1;
    return (
      <div className="flex items-center justify-between">
        <span className="text-muted-foreground">{label}</span>
        <span className={`font-semibold ${boolVal ? "text-red-400" : "text-emerald-400"}`}>
          {boolVal ? "⚠ YES" : "NO"}
        </span>
      </div>
    );
  }

  if (num === null) {
    return (
      <div className="flex items-center justify-between">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold text-muted-foreground">--</span>
      </div>
    );
  }

  const tone = colorize
    ? num >= 0
      ? "font-semibold text-emerald-400"
      : "font-semibold text-red-400"
    : "font-semibold text-foreground";

  if (format === "bar") {
    const pct = Math.min(100, Math.max(0, num * 100));
    const bg = BAR_COLORS[barColor ?? "blue"] ?? BAR_COLORS.blue;
    return (
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-semibold text-foreground">{(num * 100).toFixed(1)}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
          <div className={`h-full rounded-full ${bg} transition-all`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  }

  let display: string;
  switch (format) {
    case "percent":
      display = `${(num * 100).toFixed(3)}%`;
      break;
    case "funding":
      display = `${(num * 100).toFixed(5)}%`;
      break;
    case "zscore":
      display = `z ${num.toFixed(3)}`;
      break;
    case "ratio":
      display = num.toFixed(4);
      break;
    case "price":
      display = formatPrice(num);
      break;
    default:
      display = num.toFixed(4);
  }

  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={tone}>{display}</span>
    </div>
  );
}

function dqTone(status: string): string {
  const normalized = status.toUpperCase();
  if (["FRESH", "ALIGNED", "OK", "RELIABLE", "ALLOW"].includes(normalized)) {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";
  }
  if (["PARTIAL", "STALE", "FALLBACK_ONLY", "UNRELIABLE", "WATCHLIST", "PENALTY"].includes(normalized)) {
    return "border-amber-500/20 bg-amber-500/10 text-amber-300";
  }
  if (["MISSING", "NO_DATA", "INVALID", "BLOCK"].includes(normalized)) {
    return "border-red-500/20 bg-red-500/10 text-red-300";
  }
  return "border-white/10 bg-white/5 text-slate-300";
}

function displaySource(value: unknown): string {
  return typeof value === "string" && value.length > 0 ? value : "missing";
}

function ProvenanceCard({
  title,
  status,
  lines,
}: {
  title: string;
  status: string;
  lines: string[];
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>
        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${dqTone(status)}`}>
          {status}
        </span>
      </div>
      <div className="space-y-1 text-xs text-muted-foreground">
        {lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
    </div>
  );
}

export default function CoinDetailPage({ symbol }: { symbol: string }) {
  const searchParams = useSearchParams();
  const timeframeParam = searchParams.get("timeframe") as Timeframe | null;
  const snapshotId = searchParams.get("snapshot_id");

  const { data, isLoading } = useQuery({
    queryKey: ["coin", symbol.toUpperCase(), timeframeParam, snapshotId],
    enabled: Boolean(timeframeParam && snapshotId),
    staleTime: 5_000,
    refetchInterval: timeframeParam && snapshotId === "latest" ? getDetailRefetchInterval(timeframeParam) : false,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    queryFn: () => api.getCoin(symbol.toUpperCase(), timeframeParam ?? "1h", snapshotId ?? ""),
  });

  const { data: performanceData } = useQuery({
    queryKey: ["performance", symbol.toUpperCase(), timeframeParam, snapshotId],
    enabled: Boolean(timeframeParam && snapshotId),
    staleTime: 60_000,
    refetchInterval: snapshotId === "latest" ? 60_000 : false,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    queryFn: () => api.getPerformance({ symbol: symbol.toUpperCase(), timeframe: timeframeParam ?? "1h", snapshotId: snapshotId ?? "" }),
  });

  if (!timeframeParam || !snapshotId) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-10 text-muted-foreground">
        Snapshot reference is missing. Return to the scanner to open a valid snapshot.
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-10 text-muted-foreground">
        Loading coin detail...
      </div>
    );
  }

  const coin = data.asset;
  const fundingRate = toNumberOrNull(coin.funding_rate);
  const longShortRatio = toNumberOrNull(coin.long_short_ratio);
  const clarityConfidence = getOpportunityScore(coin, timeframeParam);
  const marketInterpretation = getMarketInterpretation(coin, timeframeParam);
  const action = buildActionLayer(coin, timeframeParam);
  const execution = buildExecutionLayer(coin, timeframeParam);
  const executionPlanTitle = describeExecutionPlan(action, execution, coin.decision_type);
  const entryRange =
    execution.entryMin === null || execution.entryMax === null
      ? "--"
      : execution.entryMin === execution.entryMax
        ? formatPrice(execution.entryMin)
        : `${formatPrice(Math.min(execution.entryMin, execution.entryMax))} - ${formatPrice(Math.max(execution.entryMin, execution.entryMax))}`;
  const target1 = execution.target1;
  const target2 = execution.target2;
  const initialStop = execution.initialStop;
  const setupKey = setupTypeFromDecision(coin.decision_type, coin.position_quality) ?? "No clear edge";
  const setupStats =
    performanceData?.setups?.find((item) => item.setup_type === setupKey) ?? null;
  const setupHasClosedTrades = (setupStats?.closed_trades ?? 0) > 0;
  const setupHasOpenTrades = (setupStats?.open_trades ?? 0) > 0;
  const setupBadge = setupStats?.validated ? "Validated" : setupHasOpenTrades && !setupHasClosedTrades ? "Collecting" : "Experimental";
  const setupBadgeTone = setupStats?.validated
    ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
    : setupHasOpenTrades && !setupHasClosedTrades
      ? "text-blue-300 border-blue-500/30 bg-blue-500/10"
    : "text-slate-300 border-white/10 bg-white/5";
  const winratePercent = setupStats && setupHasClosedTrades ? Math.round(setupStats.winrate * 100) : null;
  const expectancyValue = setupStats && setupHasClosedTrades ? setupStats.expectancy : null;
  const riskTone =
    execution.riskLevel === "High"
      ? "text-red-300 border-red-500/30 bg-red-500/10"
      : execution.riskLevel === "Medium"
        ? "text-amber-300 border-amber-500/30 bg-amber-500/10"
        : "text-emerald-300 border-emerald-500/30 bg-emerald-500/10";
  const qualityTone =
    execution.qualityScore === "A"
      ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
      : execution.qualityScore === "B"
        ? "text-amber-300 border-amber-500/30 bg-amber-500/10"
        : "text-slate-300 border-white/10 bg-white/5";
  const oiChangeValue =
    toNumberOrNull(coin.flow_metrics[`oi_change_${timeframeParam}` as keyof FlowMetrics]);
  const volumeZValue =
    toNumberOrNull(coin.flow_metrics[`volume_z_${timeframeParam}` as keyof FlowMetrics]);
  const fundingTrendValue =
    toNumberOrNull(coin.flow_metrics[`funding_trend_${timeframeParam}` as keyof FlowMetrics]);
  const dataStatusLabel =
    coin.data_status === "INSUFFICIENT_HISTORY"
      ? "INSUFFICIENT HISTORY"
      : coin.data_status === "NO_DATA"
        ? "NO DATA"
        : "VALID";
  const dataStatusTone =
    coin.data_status === "VALID"
      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
      : coin.data_status === "INSUFFICIENT_HISTORY"
        ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
        : "border-red-500/20 bg-red-500/10 text-red-300";
  const dqStatus = getDqStatus(coin, timeframeParam);
  const fallbackFields = getFallbackFields(coin, timeframeParam);
  const usingFrontendInterpretationFallback = !coin.market_interpretation;
  const oiAlignment = displaySource(getProvenanceValue(coin, "oi_alignment_status", timeframeParam)).toUpperCase();
  const oiReliable = isReliable(getProvenanceValue(coin, "oi_delta_reliable", timeframeParam));
  const fundingSource = displaySource(getProvenanceValue(coin, "funding_source", timeframeParam));
  const fundingAge = toNumberOrNull(getProvenanceValue(coin, "funding_age_seconds", timeframeParam));
  const fundingReliable = isReliable(getProvenanceValue(coin, "funding_reliable", timeframeParam));
  const liquidationSource = displaySource(getProvenanceValue(coin, "liquidation_source", timeframeParam));
  const liquidationAge = toNumberOrNull(getProvenanceValue(coin, "liquidation_age_seconds", timeframeParam));
  const takerRatioSource = displaySource(getProvenanceValue(coin, "taker_ratio_source", timeframeParam));
  const takerRatioAge = toNumberOrNull(getProvenanceValue(coin, "taker_ratio_age_seconds", timeframeParam));
  const longShortRatioSource = displaySource(getProvenanceValue(coin, "long_short_ratio_source", timeframeParam));
  const longShortRatioAge = toNumberOrNull(getProvenanceValue(coin, "long_short_ratio_age_seconds", timeframeParam));
  const hardFilterReasons = normalizeReasonList(
    coin.hard_filter_reasons ?? coin.flow_metrics.hard_filter_reasons,
  );
  const blockReasons = normalizeReasonList(
    coin.block_reasons ?? coin.flow_metrics.block_reasons,
  );
  const scenarioLabel = coin.scenario_label ?? coin.flow_metrics.scenario_label ?? "unknown";
  const scenarioDisposition = coin.scenario_disposition ?? coin.flow_metrics.scenario_disposition ?? "unknown";
  const structuralPermission = coin.final_structural_permission ?? coin.flow_metrics.final_structural_permission ?? "NOT_APPLICABLE";
  const efficientBuildQuality = coin.efficient_build_quality ?? coin.flow_metrics.efficient_build_quality ?? "UNKNOWN";
  const efficientBuildReason = coin.efficient_build_quality_reason ?? coin.flow_metrics.efficient_build_quality_reason ?? "none";

  return (
    <div className="space-y-6">
      <Link
        href="/scanner"
        className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground transition-all hover:bg-white/10 hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        <span className="font-medium">Back to Scanner</span>
      </Link>

      <div className="rounded-2xl border border-white/10 bg-card/50 p-8 backdrop-blur-xl transition-all hover:border-white/20">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 rounded-full bg-primary/30 blur-2xl" />
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-white/20 bg-gradient-to-br from-primary/30 to-primary/10">
                <span className="text-2xl font-bold text-primary">{shortSymbol(coin.symbol).charAt(0)}</span>
              </div>
            </div>
            <div>
              <h1 className="text-4xl font-bold tracking-tight text-foreground">{shortSymbol(coin.symbol)}</h1>
              <p className="mt-1 text-lg text-muted-foreground">{coin.name}</p>
            </div>
          </div>

          <div className="text-left lg:text-right">
            <p className="mb-3 text-4xl font-bold text-foreground">{formatPrice(coin.price)}</p>
            <div className="flex flex-wrap items-center gap-3 lg:justify-end">
              <div className={`rounded-xl border px-4 py-2 text-sm font-semibold ${dataStatusTone}`}>
                Data: {dataStatusLabel}
              </div>
              <div className={`rounded-xl border px-4 py-2 text-sm font-semibold ${dqTone(dqStatus)}`}>
                DQ: {dqStatus}
              </div>
              {usingFrontendInterpretationFallback ? (
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-2 text-sm font-semibold text-amber-300">
                  Frontend fallback interpretation
                </div>
              ) : null}
              <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-foreground">
                {marketInterpretation.state}
              </div>
              <div className="rounded-xl border border-primary/20 bg-primary/10 px-4 py-2 font-semibold text-primary">
                Clarity: {Math.round(clarityConfidence * 100)}%
              </div>
              {coin.phase && coin.phase !== "Neutral" && (
                <div className="inline-flex items-center gap-1.5 rounded-xl border border-primary/30 bg-primary/20 px-4 py-2 font-bold uppercase tracking-wider text-primary shadow-sm shadow-primary/20">
                  <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                  Phase: {coin.phase}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-white/20">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2.5">
              <TrendingUp className="h-5 w-5 text-blue-400" />
            </div>
            <span className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">OI Change</span>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">{timeframeParam.toUpperCase()}:</span>
              <span className={metricTone(oiChangeValue)}>
                {formatPercent(oiChangeValue)}
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-white/20">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl border border-purple-500/20 bg-purple-500/10 p-2.5">
              <Activity className="h-5 w-5 text-purple-400" />
            </div>
            <span className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Volume</span>
          </div>
          <p className="text-3xl font-bold text-foreground">{formatCompactNumber(coin.volume)}</p>
          <p className="mt-2 text-xs text-muted-foreground">Combined spot and futures turnover</p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-white/20">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-2.5">
              <DollarSign className="h-5 w-5 text-amber-400" />
            </div>
            <span className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Funding</span>
          </div>
          <p
            className={
              fundingRate === null
                ? "text-3xl font-bold text-muted-foreground"
                : fundingRate >= 0
                  ? "text-3xl font-bold text-emerald-400"
                  : "text-3xl font-bold text-red-400"
            }
          >
            {formatFundingRate(fundingRate)}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">Latest exchange-weighted funding rate</p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-white/20">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-2.5">
              <Scale className="h-5 w-5 text-emerald-400" />
            </div>
            <span className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">L/S Ratio</span>
          </div>
          <p className="text-3xl font-bold text-foreground">{formatRatio(longShortRatio)}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            {longShortRatio === null ? "Unavailable" : longShortRatio > 1 ? "Long bias" : longShortRatio < 1 ? "Short bias" : "Balanced"}
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/5 to-blue-500/5 p-6 backdrop-blur-xl">
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold text-foreground">Market State</h3>
            <div className="mt-4 grid grid-cols-1 gap-4 text-sm md:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Trend</p>
                <p className="mt-2 text-base font-semibold text-foreground">{marketInterpretation.trend}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Control</p>
                <p className="mt-2 text-base font-semibold text-foreground">{marketInterpretation.control}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">State</p>
                <p className="mt-2 text-base font-semibold text-foreground">{marketInterpretation.state}</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Structure</p>
              <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>Label</span>
                  <span className="font-semibold text-foreground">{marketInterpretation.structure_label}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Shift</span>
                  <span className="font-semibold text-foreground">{marketInterpretation.structure_shift}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Recent high</span>
                  <span className="font-semibold text-foreground">{marketInterpretation.recent_high === null ? "--" : formatPrice(marketInterpretation.recent_high)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Recent low</span>
                  <span className="font-semibold text-foreground">{marketInterpretation.recent_low === null ? "--" : formatPrice(marketInterpretation.recent_low)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Higher timeframe</span>
                  <span className="font-semibold text-foreground">{marketInterpretation.higher_timeframe_trend}</span>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Flow</p>
              <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>OI intent</span>
                  <span className="font-semibold text-foreground">{marketInterpretation.oi_intent}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>OI change</span>
                  <span className={metricTone(oiChangeValue)}>{formatPercent(oiChangeValue)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Volume z-score</span>
                  <span className="font-semibold text-foreground">{volumeZValue === null ? "--" : volumeZValue.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Funding impulse</span>
                  <span className={metricTone(fundingTrendValue)}>{formatFundingRate(fundingTrendValue)}</span>
                </div>
              </div>
            </div>
          </div>

            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Interpretation</p>
              <p className="mt-3 text-base font-semibold text-foreground">{marketInterpretation.interpretation}</p>
            </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Risk</p>
              <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>Trap risk</span>
                  <span className="font-semibold text-foreground">{Math.round(marketInterpretation.trap_risk * 100)}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Conflict score</span>
                  <span className="font-semibold text-foreground">{Math.round(marketInterpretation.conflict_score * 100)}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Clarity confidence</span>
                  <span className="font-semibold text-foreground">{Math.round(marketInterpretation.clarity_confidence * 100)}%</span>
                </div>
              </div>
              <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
                {marketInterpretation.risk_notes.length > 0
                  ? marketInterpretation.risk_notes.map((item) => <li key={item}>{item}</li>)
                  : <li>No additional risk notes.</li>}
              </ul>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Warnings</p>
              <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
                {marketInterpretation.warnings.length > 0
                  ? marketInterpretation.warnings.map((item) => <li key={item}>{item}</li>)
                  : <li>No major warning flags.</li>}
              </ul>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Action</p>
            <p className="mt-3 text-base font-semibold text-foreground">{marketInterpretation.action}</p>
            <p className="mt-2 text-sm text-muted-foreground">{marketInterpretation.action_rationale}</p>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">What could make this analysis wrong?</p>
            <p className="mt-3 text-sm text-muted-foreground">{marketInterpretation.self_critique}</p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-white/20">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Execution Plan</p>
                <p className="text-sm font-semibold text-foreground">
                  {executionPlanTitle}
                </p>
              </div>
              {coin.decision_type === "No-Trade" ? null : (
                <div className="flex items-center gap-2">
                  <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${riskTone}`}>
                    Risk {execution.riskLevel}
                  </span>
                  <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${qualityTone}`}>
                    Quality {execution.qualityScore}
                  </span>
                </div>
              )}
            </div>
            {coin.decision_type === "No-Trade" ? (
              <p className="text-sm text-muted-foreground">
                Execution is disabled until positioning aligns with a tradable edge.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-4 text-xs text-muted-foreground md:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Entry</p>
                  <p className="text-sm font-semibold text-foreground">{entryRange}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Invalidation</p>
                  <p className="text-sm font-semibold text-foreground">
                    {execution.invalidation === null ? "--" : formatPrice(execution.invalidation)}
                  </p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Targets</p>
                  <p className="text-sm font-semibold text-foreground">
                    {target1 === null ? "--" : formatPrice(target1)}
                    {target2 === null ? "" : ` / ${formatPrice(target2)}`}
                  </p>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    Initial Stop: {initialStop === null ? "--" : formatPrice(initialStop)}
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Classifier Trace</p>
            <div className="mt-3 grid grid-cols-1 gap-2 text-sm text-muted-foreground md:grid-cols-3">
              <div className="flex items-center justify-between md:block">
                <span>Intent</span>
                <p className="font-semibold text-foreground">{coin.position_intent ?? "None"}</p>
              </div>
              <div className="flex items-center justify-between md:block">
                <span>Quality</span>
                <p className="font-semibold text-foreground">{coin.position_quality ?? "Neutral"}</p>
              </div>
              <div className="flex items-center justify-between md:block">
                <span>Decision</span>
                <p className="font-semibold text-foreground">{coin.decision_type ?? "No-Trade"}</p>
              </div>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">These are secondary classifier outputs. Primary interpretation is the market state, flow context, risk, and action above.</p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-white/20">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Setup Performance (Kocak)</p>
                <p className="text-sm font-semibold text-foreground">{action.setupType}</p>
              </div>
              <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${setupBadgeTone}`}>
                {setupBadge}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs text-muted-foreground md:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Winrate</p>
                <p className="text-sm font-semibold text-foreground">
                  {winratePercent === null ? "--" : `${winratePercent}%`}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Expectancy</p>
                <p className={`text-sm font-semibold ${expectancyValue !== null && expectancyValue >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                  {expectancyValue === null ? "--" : `${expectancyValue.toFixed(2)}%`}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Trades</p>
                <p className="text-sm font-semibold text-foreground">{setupStats?.trades ?? "--"}</p>
                {setupStats ? (
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    Open: {setupStats.open_trades ?? 0} / Closed: {setupStats.closed_trades ?? 0}
                  </p>
                ) : null}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Execution Context</p>
            <div className="mt-3 space-y-2 text-sm text-muted-foreground">
              {coin.decision_type === "No-Trade" ? (
                <p>NO TRADE - wait for alignment before activating an execution plan.</p>
              ) : (
                <>
                  <p>Entry stays inactive until price reaches the structural trigger zone shown in the execution plan.</p>
                  <p>Confirmation requires the active market state to stay aligned with {marketInterpretation.control.toLowerCase()} and {marketInterpretation.oi_intent.toLowerCase()}.</p>
                  <p>If structure slips back into {marketInterpretation.state.toLowerCase()} or warnings expand, the plan should stay on watch.</p>
                  <p>Invalidation is the level where the current structural read breaks down, not a prediction target.</p>
                  <p>If higher timeframe control flips against this setup, the directional read should be reassessed.</p>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all hover:border-white/20">
        <h3 className="mb-5 text-lg font-semibold text-foreground">Flow Metrics Deep Dive</h3>
        <div className="mb-6 rounded-xl border border-white/10 bg-white/5 p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Data Provenance</p>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${dqTone(dqStatus)}`}>
              DQ {dqStatus}
            </span>
            <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${dqTone(structuralPermission)}`}>
              Structural {structuralPermission}
            </span>
            <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${dqTone(coin.final_entry_permission ?? "UNKNOWN")}`}>
              Entry {coin.final_entry_permission ?? "UNKNOWN"}
            </span>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-300">
              Scenario {scenarioLabel} / {scenarioDisposition}
            </span>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-300">
              Efficient {efficientBuildQuality}
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
            <ProvenanceCard
              title="OI"
              status={oiReliable && oiAlignment === "ALIGNED" ? "ALIGNED" : "UNRELIABLE"}
              lines={[
                `alignment: ${oiAlignment}`,
                `reliable: ${oiReliable ? "true" : "false"}`,
              ]}
            />
            <ProvenanceCard
              title="Funding"
              status={fundingReliable ? "RELIABLE" : "UNRELIABLE"}
              lines={[
                `source: ${fundingSource}`,
                `age: ${formatAge(fundingAge)}`,
                `reliable: ${fundingReliable ? "true" : "false"}`,
              ]}
            />
            <ProvenanceCard
              title="Liquidation"
              status={liquidationSource === "missing" ? "MISSING" : "FRESH"}
              lines={[
                `source: ${liquidationSource}`,
                `age: ${formatAge(liquidationAge)}`,
              ]}
            />
            <ProvenanceCard
              title="Taker Ratio"
              status={fallbackFields.includes("taker_ratio") ? "FALLBACK_ONLY" : "FRESH"}
              lines={[
                `source: ${takerRatioSource}`,
                `age: ${formatAge(takerRatioAge)}`,
              ]}
            />
            <ProvenanceCard
              title="L/S Ratio"
              status={fallbackFields.some((field) => field === "ls_ratio" || field === "long_short_ratio") ? "FALLBACK_ONLY" : "FRESH"}
              lines={[
                `source: ${longShortRatioSource}`,
                `age: ${formatAge(longShortRatioAge)}`,
              ]}
            />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 text-xs text-muted-foreground md:grid-cols-2">
            <div>
              <p className="mb-2 font-semibold uppercase tracking-wider text-muted-foreground">Fallback Fields</p>
              <p>{fallbackFields.length > 0 ? fallbackFields.join(", ") : "none"}</p>
            </div>
            <div>
              <p className="mb-2 font-semibold uppercase tracking-wider text-muted-foreground">Hard Filters</p>
              <p>{hardFilterReasons.length > 0 ? hardFilterReasons.join(", ") : blockReasons.length > 0 ? blockReasons.join(", ") : "none"}</p>
              <p className="mt-1">efficient reason: {efficientBuildReason}</p>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* ── Price & Momentum ── */}
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Price &amp; Momentum</p>
            <div className="space-y-3 text-sm">
              <MetricRow
                label="Price Change"
                value={toNumberOrNull(coin.flow_metrics[`price_change_${timeframeParam}` as keyof FlowMetrics])}
                format="percent"
                colorize
              />
              <MetricRow
                label="Market Pressure"
                value={toNumberOrNull(coin.flow_metrics[`market_pressure_${timeframeParam}` as keyof FlowMetrics])}
                format="decimal"
                colorize
              />
              <MetricRow
                label="Compression Score"
                value={toNumberOrNull(coin.flow_metrics[`compression_score_${timeframeParam}` as keyof FlowMetrics])}
                format="bar"
                barColor="blue"
              />
              <MetricRow
                label="ATR"
                value={toNumberOrNull(coin.flow_metrics[`atr_${timeframeParam}` as keyof FlowMetrics])}
                format="decimal"
              />
              <MetricRow
                label="Wick Ratio"
                value={toNumberOrNull(coin.flow_metrics[`wick_ratio_${timeframeParam}` as keyof FlowMetrics])}
                format="bar"
                barColor={
                  (toNumberOrNull(coin.flow_metrics[`wick_ratio_${timeframeParam}` as keyof FlowMetrics]) ?? 0) >= 0.4
                    ? "amber"
                    : "slate"
                }
              />
            </div>
          </div>

          {/* ── Taker & Positioning ── */}
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Taker &amp; Positioning</p>
            <div className="space-y-3 text-sm">
              <MetricRow
                label="Taker Buy/Sell Ratio"
                value={toNumberOrNull(coin.flow_metrics[`taker_buy_sell_ratio_level_${timeframeParam}` as keyof FlowMetrics])}
                format="ratio"
              />
              <MetricRow
                label="Taker Delta"
                value={toNumberOrNull(coin.flow_metrics[`taker_buy_sell_ratio_delta_${timeframeParam}` as keyof FlowMetrics])}
                format="decimal"
                colorize
              />
              <MetricRow
                label="L/S Ratio Level"
                value={toNumberOrNull(coin.flow_metrics[`long_short_ratio_level_${timeframeParam}` as keyof FlowMetrics])}
                format="ratio"
              />
              <MetricRow
                label="L/S Ratio Delta"
                value={toNumberOrNull(coin.flow_metrics[`long_short_ratio_delta_${timeframeParam}` as keyof FlowMetrics])}
                format="decimal"
                colorize
              />
            </div>
          </div>

          {/* ── OI Detail ── */}
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Open Interest Detail</p>
            <div className="space-y-3 text-sm">
              <MetricRow
                label="OI Percentile"
                value={toNumberOrNull(coin.flow_metrics[`oi_percentile_${timeframeParam}` as keyof FlowMetrics])}
                format="bar"
                barColor={
                  (toNumberOrNull(coin.flow_metrics[`oi_percentile_${timeframeParam}` as keyof FlowMetrics]) ?? 0) >= 0.75
                    ? "red"
                    : (toNumberOrNull(coin.flow_metrics[`oi_percentile_${timeframeParam}` as keyof FlowMetrics]) ?? 0) >= 0.5
                      ? "amber"
                      : "emerald"
                }
              />
              <MetricRow
                label="OI Delta Z-Score"
                value={toNumberOrNull(coin.flow_metrics[`oi_delta_z_${timeframeParam}` as keyof FlowMetrics])}
                format="zscore"
                colorize
              />
              <MetricRow
                label="OI Delta"
                value={toNumberOrNull(coin.flow_metrics[`oi_delta_${timeframeParam}` as keyof FlowMetrics])}
                format="decimal"
                colorize
              />
            </div>
          </div>

          {/* ── Liquidation ── */}
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Liquidation Metrics</p>
            <div className="space-y-3 text-sm">
              <MetricRow
                label="Liq Pressure"
                value={toNumberOrNull(coin.flow_metrics[`liq_pressure_${timeframeParam}` as keyof FlowMetrics])}
                format="decimal"
                colorize
              />
              <MetricRow
                label="Liq Z-Score"
                value={toNumberOrNull(coin.flow_metrics[`liq_z_score_${timeframeParam}` as keyof FlowMetrics])}
                format="zscore"
              />
              <MetricRow
                label="Liq Delta"
                value={toNumberOrNull(coin.flow_metrics[`liq_delta_${timeframeParam}` as keyof FlowMetrics])}
                format="decimal"
                colorize
              />
            </div>
          </div>

          {/* ── Funding Detail ── */}
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Funding Detail</p>
            <div className="space-y-3 text-sm">
              <MetricRow
                label="Funding Level"
                value={toNumberOrNull(coin.flow_metrics[`funding_level_${timeframeParam}` as keyof FlowMetrics])}
                format="funding"
                colorize
              />
              <MetricRow
                label="Funding Trend"
                value={toNumberOrNull(coin.flow_metrics[`funding_trend_${timeframeParam}` as keyof FlowMetrics])}
                format="funding"
                colorize
              />
              <MetricRow
                label="Funding Extreme"
                value={coin.flow_metrics[`funding_extreme_${timeframeParam}` as keyof FlowMetrics] as unknown as number}
                format="boolean"
              />
            </div>
          </div>

          {/* ── Alignment Scores ── */}
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Alignment Scores</p>
            <div className="space-y-3 text-sm">
              <MetricRow
                label="Flow Alignment"
                value={marketInterpretation.flow_alignment}
                format="bar"
                barColor={marketInterpretation.flow_alignment >= 0.7 ? "emerald" : marketInterpretation.flow_alignment >= 0.5 ? "amber" : "red"}
              />
              <MetricRow
                label="Trend Alignment"
                value={marketInterpretation.trend_alignment}
                format="bar"
                barColor={marketInterpretation.trend_alignment >= 0.7 ? "emerald" : marketInterpretation.trend_alignment >= 0.5 ? "amber" : "red"}
              />
              <MetricRow
                label="Structure Strength"
                value={marketInterpretation.structure_strength}
                format="bar"
                barColor={marketInterpretation.structure_strength >= 0.7 ? "emerald" : marketInterpretation.structure_strength >= 0.5 ? "amber" : "red"}
              />
              <MetricRow
                label="Range Mid"
                value={toNumberOrNull(coin.flow_metrics[`range_mid_${timeframeParam}` as keyof FlowMetrics])}
                format="price"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all hover:border-white/20">
          <h3 className="mb-5 font-semibold text-foreground">Price vs Open Interest</h3>
          <PriceOpenInterestChart data={data.price_open_interest} />
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all hover:border-white/20">
          <h3 className="mb-5 font-semibold text-foreground">Volume Analysis</h3>
          <VolumeChart data={data.volume_history} />
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all hover:border-white/20">
          <h3 className="mb-5 font-semibold text-foreground">Funding Rate Trend</h3>
          <FundingChart data={data.funding_history} />
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all hover:border-white/20">
          <h3 className="mb-5 font-semibold text-foreground">Liquidation Events</h3>
          <LiquidationChart data={data.liquidation_history} />
        </div>
      </div>
    </div>
  );
}
