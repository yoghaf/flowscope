import Link from "next/link";

import {
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
  getOpportunityScore,
  getMarketInterpretation,
} from "@/lib/interpretation";
import type {
  AssetSnapshot,
  FlowMetrics,
  PositionQuality,
  SetupPerformance,
  Timeframe,
} from "@/lib/types";

interface MarketStateCardProps {
  asset: AssetSnapshot;
  timeframe: Timeframe;
  setupStats?: SetupPerformance;
}

const QUALITY_STYLES: Record<PositionQuality | "Unknown", { text: string; bg: string; border: string }> = {
  "Strong Longs": {
    text: "text-emerald-300",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
  "Building Longs": {
    text: "text-blue-300",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  "Weak Longs": {
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
  },
  "Trapped Longs": {
    text: "text-red-300",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
  },
  "Strong Shorts": {
    text: "text-red-300",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
  },
  "Building Shorts": {
    text: "text-blue-300",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  "Weak Shorts": {
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
  },
  "Trapped Shorts": {
    text: "text-emerald-300",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
  "Absorption-High": {
    text: "text-blue-300",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  "Absorption-Mid": {
    text: "text-blue-300",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  "Pre-Squeeze-Ready": {
    text: "text-yellow-300",
    bg: "bg-yellow-500/10",
    border: "border-yellow-500/30",
  },
  "Pre-Squeeze-Building": {
    text: "text-yellow-300",
    bg: "bg-yellow-500/10",
    border: "border-yellow-500/30",
  },
  Neutral: {
    text: "text-muted-foreground",
    bg: "bg-white/5",
    border: "border-white/10",
  },
  Unknown: {
    text: "text-muted-foreground",
    bg: "bg-white/5",
    border: "border-white/10",
  },
};

function metricForTimeframe(
  asset: AssetSnapshot,
  key:
    | "price_change"
    | "funding_trend"
    | "oi_delta_z"
    | "volume_z"
    | "atr",
  timeframe: Timeframe,
): number | null {
  const field = `${key}_${timeframe}` as keyof FlowMetrics;
  return toNumberOrNull(asset.flow_metrics?.[field]) ?? null;
}

function formatZ(value: number | null): string {
  const numeric = toNumberOrNull(value);
  if (numeric === null) {
    return "--";
  }
  return numeric.toFixed(2);
}

export default function MarketStateCard({ asset, timeframe, setupStats }: MarketStateCardProps) {
  const marketInterpretation = getMarketInterpretation(asset, timeframe);
  const action = buildActionLayer(asset, timeframe);
  const execution = buildExecutionLayer(asset, timeframe);
  const executionPlanTitle = describeExecutionPlan(action, execution, asset.decision_type);
  const quality = asset.position_quality ?? "Neutral";
  const decision = asset.decision_type ?? "No-Trade";
  const stateStyle = QUALITY_STYLES[quality] ?? QUALITY_STYLES.Unknown;
  const confidence = Math.round(getOpportunityScore(asset, timeframe) * 100);
  const dataStatusLabel =
    asset.data_status === "INSUFFICIENT_HISTORY"
      ? "Insufficient History"
      : asset.data_status === "NO_DATA"
        ? "No Data"
        : "Valid";
  const dataStatusTone =
    asset.data_status === "VALID"
      ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
      : asset.data_status === "INSUFFICIENT_HISTORY"
        ? "text-amber-300 border-amber-500/30 bg-amber-500/10"
        : "text-red-300 border-red-500/30 bg-red-500/10";

  const priceChange = metricForTimeframe(asset, "price_change", timeframe);
  const fundingTrend = metricForTimeframe(asset, "funding_trend", timeframe);
  const oiDeltaZ = metricForTimeframe(asset, "oi_delta_z", timeframe);
  const volumeZ = metricForTimeframe(asset, "volume_z", timeframe);
  const atr = metricForTimeframe(asset, "atr", timeframe);

  const fundingRate = toNumberOrNull(asset.funding_rate);
  const takerRatio = toNumberOrNull(asset.taker_buy_sell_ratio);
  const longShortRatio = toNumberOrNull(asset.long_short_ratio);

  const biasTone =
    marketInterpretation.trend === "Bullish" || marketInterpretation.control === "Buyer Dominant"
      ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
      : marketInterpretation.trend === "Bearish" || marketInterpretation.control === "Seller Dominant"
        ? "text-red-300 border-red-500/30 bg-red-500/10"
        : "text-slate-300 border-white/10 bg-white/5";
  const setupTone =
    action.setupType === "Trap"
      ? "text-slate-300 border-slate-500/30 bg-slate-500/10"
      : action.setupType === "Watchlist"
        ? "text-amber-300 border-amber-500/30 bg-amber-500/10"
      : action.setupType === "Continuation"
          ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
          : action.setupType === "Squeeze"
            ? "text-yellow-300 border-yellow-500/30 bg-yellow-500/10"
          : action.setupType === "Compression"
            ? "text-blue-300 border-blue-500/30 bg-blue-500/10"
            : "text-slate-300 border-white/10 bg-white/5";
  const statusTone =
    action.status === "Triggered"
      ? "text-primary border-primary/30 bg-primary/10"
      : action.status === "Ready"
      ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
      : action.status === "Developing"
        ? "text-amber-300 border-amber-500/30 bg-amber-500/10"
        : action.status === "Unstable"
          ? "text-red-300 border-red-500/30 bg-red-500/10"
          : "text-slate-300 border-white/10 bg-white/5";
  const confidenceTone =
    action.confidenceLabel === "High"
      ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
      : action.confidenceLabel === "Medium"
        ? "text-amber-300 border-amber-500/30 bg-amber-500/10"
        : "text-slate-300 border-white/10 bg-white/5";
  const actionTone =
    marketInterpretation.action === "ENTER"
      ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
      : marketInterpretation.action === "WAIT"
        ? "text-amber-300 border-amber-500/30 bg-amber-500/10"
        : "text-red-300 border-red-500/30 bg-red-500/10";

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

  const entryMin = execution.entryMin;
  const entryMax = execution.entryMax;
  const entryRange =
    entryMin === null || entryMax === null
      ? "--"
      : entryMin === entryMax
        ? formatPrice(entryMin)
        : `${formatPrice(Math.min(entryMin, entryMax))} - ${formatPrice(Math.max(entryMin, entryMax))}`;
  const target1 = execution.target1;
  const target2 = execution.target2;
  const initialStop = execution.initialStop;

  const setupBadge = setupStats?.validated ? "Validated" : "Experimental";
  const setupBadgeTone = setupStats?.validated
    ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
    : "text-slate-300 border-white/10 bg-white/5";
  const winratePercent = setupStats ? Math.round(setupStats.winrate * 100) : null;
  const expectancyValue = setupStats?.expectancy ?? null;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-card/60 p-6 backdrop-blur-xl transition-all duration-300 hover:border-white/20">
      <div className="absolute inset-0 bg-gradient-to-br from-white/5 via-transparent to-transparent opacity-40" />
      <div className="relative flex flex-col gap-5">
        <div className="flex items-start justify-between gap-3">
          <Link
            href={`/coin/${asset.symbol}?timeframe=${asset.timeframe}&snapshot_id=latest`}
            className="group flex items-center gap-3"
          >
            <div className="relative">
              <div className="absolute inset-0 rounded-full bg-primary/20 blur-md" />
              <div className="relative flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-primary/20 to-primary/10 transition-transform group-hover:scale-110">
                <span className="text-sm font-bold text-primary">{shortSymbol(asset.symbol).charAt(0)}</span>
              </div>
            </div>
            <div>
              <div className="text-lg font-semibold text-foreground">{shortSymbol(asset.symbol)}</div>
              <div className="text-xs text-muted-foreground">{timeframe.toUpperCase()}</div>
            </div>
          </Link>

          <div className="flex flex-col items-end gap-1.5">
            <div className={`rounded-full border px-3 py-1 text-xs font-semibold ${stateStyle.bg} ${stateStyle.text} ${stateStyle.border}`}>
              {marketInterpretation.state}
            </div>
            {asset.phase && asset.phase !== "Neutral" && (
              <div className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-primary shadow-sm shadow-primary/10">
                <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                {asset.phase}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${dataStatusTone}`}>
            Data: {dataStatusLabel}
          </span>
          <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${biasTone}`}>
            Trend: {marketInterpretation.trend}
          </span>
          <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${setupTone}`}>
            Control: {marketInterpretation.control}
          </span>
          <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${statusTone}`}>
            State: {marketInterpretation.state}
          </span>
          <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${actionTone}`}>
            Action: {marketInterpretation.action}
          </span>
          <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${confidenceTone}`}>
            Confidence: {action.confidenceLabel}
          </span>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="mb-3 flex items-center justify-between text-xs uppercase tracking-wider text-muted-foreground">
            <span>Confidence</span>
            <span className="text-foreground">{confidence}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-gradient-to-r from-primary to-primary/60" style={{ width: `${confidence}%` }} />
          </div>
        </div>

        <div className="space-y-3 text-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">OI</p>
            <p className="text-foreground">{marketInterpretation.oi_intent}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Interpretation</p>
            <p className="text-foreground">{marketInterpretation.interpretation}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Action Rationale</p>
            <p className="text-foreground">{marketInterpretation.action_rationale}</p>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Classifier Trace</p>
          <div className="grid gap-2 text-sm text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>Intent</span>
              <span className="font-semibold text-foreground">{asset.position_intent ?? "None"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Quality</span>
              <span className="font-semibold text-foreground">{quality}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Decision</span>
              <span className="font-semibold text-foreground">{decision}</span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">Secondary pattern tags only. Primary read comes from trend, control, state, and action.</p>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Risk Analysis</p>
          <ul className="space-y-1 text-sm text-muted-foreground">
            <li>Trap risk: {Math.round(marketInterpretation.trap_risk * 100)}%</li>
            <li>Conflict score: {Math.round(marketInterpretation.conflict_score * 100)}%</li>
            {marketInterpretation.warnings.length > 0
              ? marketInterpretation.warnings.map((item) => <li key={item}>{item}</li>)
              : <li>No major warning flags.</li>}
          </ul>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Self-Critique</p>
          <p className="text-sm text-muted-foreground">{marketInterpretation.self_critique}</p>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Execution Plan</p>
              <p className="text-sm font-semibold text-foreground">
                {executionPlanTitle}
              </p>
            </div>
            {decision === "No-Trade" ? null : (
              <div className="flex items-center gap-2">
                <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${riskTone}`}>
                  Risk {execution.riskLevel}
                </span>
                <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${qualityTone}`}>
                  Quality {execution.qualityScore}
                </span>
              </div>
            )}
          </div>
          {decision === "No-Trade" ? (
            <p className="text-sm text-muted-foreground">
              Reliability is low or positioning is ambiguous. Stand down until clarity improves.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-3 text-xs text-muted-foreground md:grid-cols-3">
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Entry</p>
                <p className="text-sm font-semibold text-foreground">{entryRange}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Invalidation</p>
                <p className="text-sm font-semibold text-foreground">
                  {execution.invalidation === null ? "--" : formatPrice(execution.invalidation)}
                </p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
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
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Setup Performance</p>
              <p className="text-sm font-semibold text-foreground">{action.setupType}</p>
            </div>
            <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${setupBadgeTone}`}>
              {setupBadge}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground md:grid-cols-3">
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Winrate</p>
              <p className="text-sm font-semibold text-foreground">
                {winratePercent === null ? "--" : `${winratePercent}%`}
              </p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Expectancy</p>
              <p className={`text-sm font-semibold ${expectancyValue !== null && expectancyValue >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                {expectancyValue === null ? "--" : `${expectancyValue.toFixed(2)}%`}
              </p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/5 p-3">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Trades</p>
              <p className="text-sm font-semibold text-foreground">{setupStats?.trades ?? "--"}</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground">
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Funding</p>
            <p className={fundingRate !== null && fundingRate !== undefined && fundingRate < 0 ? "font-semibold text-red-400" : "font-semibold text-emerald-400"}>
              {formatFundingRate(fundingRate)}
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">
              Trend: {formatFundingRate(fundingTrend)}
            </p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Price / ATR</p>
            <p className="font-semibold text-foreground">Delta {formatPercent(priceChange)}</p>
            <p className="mt-1 text-[10px] text-muted-foreground">ATR {formatPercent(atr)}</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">OI / Vol Z</p>
            <p className="font-semibold text-foreground">OI Z {formatZ(oiDeltaZ)}</p>
            <p className="mt-1 text-[10px] text-muted-foreground">Vol Z {formatZ(volumeZ)}</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Ratios</p>
            <p className="font-semibold text-foreground">Taker {formatRatio(takerRatio)}</p>
            <p className="mt-1 text-[10px] text-muted-foreground">L/S {formatRatio(longShortRatio)}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
