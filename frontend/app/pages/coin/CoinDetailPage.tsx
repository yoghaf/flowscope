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
  formatCompactNumber,
  formatFundingRate,
  formatPercent,
  formatPrice,
  formatRatio,
  shortSymbol,
  toNumberOrNull,
} from "@/lib/formatters";
import {
  buildActionLayer,
  buildExecutionLayer,
  describeExecutionPlan,
  getMarketInterpretation,
  setupTypeFromDecision,
} from "@/lib/interpretation";
import type { FlowMetrics, Timeframe } from "@/lib/types";

function metricTone(value: number | null | undefined): string {
  const numericValue = toNumberOrNull(value);
  if (numericValue === null) {
    return "font-semibold text-muted-foreground";
  }

  return numericValue >= 0 ? "font-semibold text-emerald-400" : "font-semibold text-red-400";
}

export default function CoinDetailPage({ symbol }: { symbol: string }) {
  const searchParams = useSearchParams();
  const timeframeParam = searchParams.get("timeframe") as Timeframe | null;
  const snapshotId = searchParams.get("snapshot_id");

  const { data, isLoading } = useQuery({
    queryKey: ["coin", symbol.toUpperCase(), timeframeParam, snapshotId],
    enabled: Boolean(timeframeParam && snapshotId),
    queryFn: () => api.getCoin(symbol.toUpperCase(), timeframeParam ?? "1h", snapshotId ?? ""),
  });

  const { data: performanceData } = useQuery({
    queryKey: ["performance", symbol.toUpperCase(), timeframeParam, snapshotId],
    enabled: Boolean(timeframeParam && snapshotId),
    queryFn: () => api.getPerformance({ symbol: symbol.toUpperCase(), timeframe: timeframeParam ?? "1h", snapshotId: snapshotId ?? "" }),
    staleTime: 60_000,
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
  const reliability = toNumberOrNull(coin.reliability_score) ?? 0;
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
              <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-foreground">
                {marketInterpretation.state}
              </div>
              <div className="rounded-xl border border-primary/20 bg-primary/10 px-4 py-2 font-semibold text-primary">
                Reliability: {Math.round(reliability * 100)}%
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
