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
  buildInterpretation,
  formatDecisionBadge,
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
  const interpretation = buildInterpretation(coin, timeframeParam);
  const conflicts = interpretation.conflicts;
  const squeezePercent = Math.round(interpretation.risks.squeezeProbability * 100);
  const action = buildActionLayer(coin, timeframeParam);
  const execution = buildExecutionLayer(coin, timeframeParam);
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
  const setupBadge = setupStats?.validated ? "Validated" : "Experimental";
  const setupBadgeTone = setupStats?.validated
    ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
    : "text-slate-300 border-white/10 bg-white/5";
  const winratePercent = setupStats ? Math.round(setupStats.winrate * 100) : null;
  const expectancyValue = setupStats?.expectancy ?? null;
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
                {formatDecisionBadge(coin.decision_type)}
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
            <h3 className="text-lg font-semibold text-foreground">Market Narrative</h3>
            <div className="mt-4 grid grid-cols-1 gap-4 text-sm text-muted-foreground md:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Intent</p>
                <p className="mt-2 text-base font-semibold text-foreground">{interpretation.narrative.intent}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Pressure</p>
                <p className="mt-2 text-base font-semibold text-foreground">{interpretation.narrative.pressure}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Expectation</p>
                <p className="mt-2 text-base font-semibold text-foreground">{interpretation.narrative.expectation}</p>
              </div>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Decision Reasoning</h4>
            <div className="mt-3 rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-base font-semibold text-foreground">{interpretation.decisionReasoning.title}</p>
              <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
                {interpretation.decisionReasoning.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Timing Context</p>
              <p className="mt-2 text-base font-semibold text-foreground">{interpretation.timing.stage}</p>
              <p className="mt-2 text-sm text-muted-foreground">{interpretation.timing.rationale}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Structure Context</p>
              <p className="mt-2 text-base font-semibold text-foreground">{interpretation.structure.label}</p>
              <p className="mt-2 text-sm text-muted-foreground">{interpretation.structure.explanation}</p>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Positioning Explanation</h4>
            <p className="mt-3 text-base font-semibold text-foreground">
              {interpretation.positioning.summary}
            </p>
            <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
              {interpretation.positioning.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Decision Confidence</p>
            <p className="mt-2 text-base font-semibold text-foreground">
              {interpretation.confidence.label} reliability ({Math.round(reliability * 100)}%)
            </p>
            <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
              {interpretation.confidence.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Risk Overview</p>
              <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>Squeeze probability</span>
                  <span className="font-semibold text-foreground">{squeezePercent}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Crowding level</span>
                  <span className="font-semibold text-foreground">{interpretation.risks.crowdingLevel}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Late trend risk</span>
                  <span className="font-semibold text-foreground">{interpretation.risks.lateTrendRisk}</span>
                </div>
              </div>
              <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
                {interpretation.risks.notes.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Conflict Signals</p>
              <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
                {conflicts.length
                  ? conflicts.map((item) => <li key={item}>{item}</li>)
                  : <li>No major conflicts detected.</li>}
              </ul>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Invalidation Conditions</p>
            <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
              {interpretation.invalidationConditions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-white/20">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Execution Plan</p>
                <p className="text-sm font-semibold text-foreground">
                  {coin.decision_type === "No-Trade" ? "NO TRADE - WAIT" : execution.entryMin === null ? "Waiting for trigger" : `${execution.entryType} entry`}
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
                  <p>{interpretation.execution.entryRationale}</p>
                  <p>{interpretation.execution.confirmCondition}</p>
                  <p>{interpretation.execution.cancelCondition}</p>
                  <p>{interpretation.execution.invalidationRationale}</p>
                  <p>{interpretation.execution.flipBias}</p>
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
