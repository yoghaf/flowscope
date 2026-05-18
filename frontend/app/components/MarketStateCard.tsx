import Link from "next/link";

import {
  formatAge,
  formatEntryLocationPhase,
  formatEntryLocationQuality,
  formatFundingRate,
  formatMarketRelativeStatus,
  formatPercent,
  formatPipelineLabel,
  formatPrice,
  formatRatio,
  formatRelativeScore,
  getBlockReasons,
  getDqStatus,
  getEntryLocationWarning,
  getEntryLocationPhase,
  getEntryLocationQuality,
  getEntryLocationReason,
  getEntryPermission,
  getFallbackFields,
  getHardFilterReasons,
  getHumanDecisionSubtitle,
  getHumanReason,
  getMarketIndependenceScore,
  getMarketRelativeStatus,
  getObservabilityDecisionLabel,
  getObservabilityDecisionTone,
  getProvenanceValue,
  getRelativeStrengthScore,
  getRelativeWeaknessScore,
  getScenarioDisposition,
  getScenarioLabel,
  getStructuralPermission,
  isReliable,
  shouldShowRelativeScore,
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
import type { AssetSnapshot, SetupPerformance, Timeframe } from "@/lib/types";

interface MarketStateCardProps {
  asset: AssetSnapshot;
  timeframe: Timeframe;
  setupStats?: SetupPerformance;
}

function tone(status: string): string {
  const normalized = status.toUpperCase().replace(/^STRUCTURAL_/, "");
  if (["ALLOW", "ENTER", "FRESH", "ALIGNED", "OK", "RELIABLE"].includes(normalized)) {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }
  if (["WATCHLIST", "WAIT", "PARTIAL", "STALE", "FALLBACK_ONLY", "UNRELIABLE", "PENALTY"].includes(normalized)) {
    return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  }
  if (["BLOCK", "NO TRADE", "MISSING", "NO_DATA", "INVALID"].includes(normalized)) {
    return "border-red-500/30 bg-red-500/10 text-red-300";
  }
  return "border-white/10 bg-white/5 text-slate-300";
}

function source(value: unknown): string {
  return typeof value === "string" && value.length > 0 ? value : "missing";
}

function firstText(value: string[], fallback = "none"): string {
  return value.length > 0 ? value[0] : fallback;
}

export default function MarketStateCard({ asset, timeframe, setupStats }: MarketStateCardProps) {
  const marketInterpretation = getMarketInterpretation(asset, timeframe);
  const action = buildActionLayer(asset, timeframe);
  const execution = buildExecutionLayer(asset, timeframe);
  const executionPlanTitle = describeExecutionPlan(action, execution, asset.decision_type);
  const confidence = Math.round(getOpportunityScore(asset, timeframe) * 100);
  const entryPermission = getEntryPermission(asset);
  const dqStatus = getDqStatus(asset, timeframe);
  const fallbackFields = getFallbackFields(asset, timeframe);
  const scenarioLabel = getScenarioLabel(asset);
  const scenarioDisposition = getScenarioDisposition(asset);
  const structuralPermission = getStructuralPermission(asset, timeframe);
  const hardFilterReasons = getHardFilterReasons(asset);
  const blockReasons = getBlockReasons(asset);
  const decisionSubtitle = getHumanDecisionSubtitle(asset);
  const humanReason = getHumanReason(asset, timeframe);
  const marketRelativeStatus = getMarketRelativeStatus(asset, timeframe);
  const relativeScore =
    getRelativeStrengthScore(asset, timeframe) ??
    getRelativeWeaknessScore(asset, timeframe) ??
    getMarketIndependenceScore(asset, timeframe);
  const entryPhase = getEntryLocationPhase(asset, timeframe);
  const entryQuality = getEntryLocationQuality(asset, timeframe);
  const entryReason = getEntryLocationReason(asset, timeframe);
  const decisionLabel = getObservabilityDecisionLabel(asset, timeframe);
  const decisionTone = getObservabilityDecisionTone(asset, timeframe);
  const locationWarning = getEntryLocationWarning(asset, timeframe);
  const displaySubtitle = locationWarning ?? decisionSubtitle;
  const showRelativeScore = shouldShowRelativeScore(marketRelativeStatus, relativeScore);

  const oiAlignment = source(getProvenanceValue(asset, "oi_alignment_status", timeframe)).toUpperCase();
  const oiReliabilityRaw = getProvenanceValue(asset, "oi_delta_reliable", timeframe);
  const oiReliable = isReliable(oiReliabilityRaw);
  const fundingSource = source(getProvenanceValue(asset, "funding_source", timeframe));
  const fundingReliabilityRaw = getProvenanceValue(asset, "funding_reliable", timeframe);
  const fundingReliable = isReliable(fundingReliabilityRaw);
  const fundingAge = toNumberOrNull(getProvenanceValue(asset, "funding_age_seconds", timeframe));
  const liquidationSource = source(getProvenanceValue(asset, "liquidation_source", timeframe));
  const liquidationAge = toNumberOrNull(getProvenanceValue(asset, "liquidation_age_seconds", timeframe));
  const takerSource = source(getProvenanceValue(asset, "taker_ratio_source", timeframe));
  const takerAge = toNumberOrNull(getProvenanceValue(asset, "taker_ratio_age_seconds", timeframe));
  const longShortSource = source(getProvenanceValue(asset, "long_short_ratio_source", timeframe));
  const longShortAge = toNumberOrNull(getProvenanceValue(asset, "long_short_ratio_age_seconds", timeframe));
  const ratioFallback = fallbackFields.some((field) => ["taker_ratio", "ls_ratio", "long_short_ratio"].includes(field));
  const fundingIssue = (fundingReliabilityRaw === false || fundingReliabilityRaw === "false" || fundingSource === "missing") && !fundingReliable;
  const thirdBadge = ratioFallback
    ? { label: "Ratio Fallback", status: "FALLBACK_ONLY" }
    : fundingIssue
      ? { label: "Fund Issue", status: "UNRELIABLE" }
      : null;

  const fundingRate = toNumberOrNull(asset.funding_rate);
  const takerRatio = toNumberOrNull(asset.taker_buy_sell_ratio);
  const longShortRatio = toNumberOrNull(asset.long_short_ratio);
  const entryMin = execution.entryMin;
  const entryMax = execution.entryMax;
  const entryRange =
    entryMin === null || entryMax === null
      ? "--"
      : entryMin === entryMax
        ? formatPrice(entryMin)
        : `${formatPrice(Math.min(entryMin, entryMax))} - ${formatPrice(Math.max(entryMin, entryMax))}`;
  const oiBadgeStatus = oiReliable && oiAlignment === "ALIGNED" ? "ALIGNED" : "UNRELIABLE";

  return (
    <article className="rounded-xl border border-white/10 bg-card/60 p-4 backdrop-blur-xl transition-colors hover:border-white/20">
      <div className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-4">
          <Link href={`/coin/${asset.symbol}?timeframe=${asset.timeframe}&snapshot_id=latest`} className="min-w-0">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-primary/10">
                <span className="text-sm font-bold text-primary">{shortSymbol(asset.symbol).charAt(0)}</span>
              </div>
              <div className="min-w-0">
                <p className="truncate text-lg font-semibold text-foreground">{shortSymbol(asset.symbol)}</p>
                <p className="text-xs text-muted-foreground">{timeframe.toUpperCase()} - {asset.decision_type ?? "No-Trade"}</p>
              </div>
            </div>
          </Link>
          <div className="shrink-0 text-right">
            <span className={`inline-flex rounded-lg border px-3 py-1.5 text-xs font-bold uppercase tracking-wide ${decisionTone}`}>
              {decisionLabel}
            </span>
            <p className="mt-1 max-w-[220px] text-xs text-muted-foreground">{displaySubtitle}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-3 xl:grid-cols-6">
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Decision</p>
            <p className="mt-1 font-semibold text-foreground">{decisionLabel}</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Market</p>
            <p className="mt-1 font-semibold text-foreground">{formatMarketRelativeStatus(marketRelativeStatus)}</p>
            {showRelativeScore ? <p className="mt-1 text-[11px] text-muted-foreground">Score {formatRelativeScore(relativeScore)}</p> : null}
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Entry Location</p>
            <p className="mt-1 font-semibold text-foreground">{formatEntryLocationPhase(entryPhase)}</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Quality</p>
            <p className="mt-1 font-semibold text-foreground">{formatEntryLocationQuality(entryQuality)}</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Reason</p>
            <p className="mt-1 truncate font-semibold text-amber-300" title={entryReason ?? humanReason}>{entryReason ?? humanReason}</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Confidence</p>
            <p className="mt-1 font-semibold text-foreground">{confidence}%</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 text-[11px]">
          <span className={`rounded-full border px-2.5 py-1 font-semibold uppercase tracking-wide ${tone(dqStatus)}`}>
            DQ {formatPipelineLabel(dqStatus)}
          </span>
          <span className={`rounded-full border px-2.5 py-1 font-semibold uppercase tracking-wide ${tone(oiBadgeStatus)}`}>
            OI {oiBadgeStatus === "ALIGNED" ? "OK" : "UNREL"}
          </span>
          {thirdBadge ? (
            <span className={`rounded-full border px-2.5 py-1 font-semibold uppercase tracking-wide ${tone(thirdBadge.status)}`}>
              {thirdBadge.label}
            </span>
          ) : null}
        </div>

        <details className="group rounded-lg border border-white/10 bg-white/5">
          <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground transition-colors group-open:border-b group-open:border-white/10 hover:text-foreground">
            Details
          </summary>
          <div className="grid gap-4 p-3 text-sm text-muted-foreground lg:grid-cols-3">
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Interpretation / Risk</p>
              <p className="mb-1 font-semibold text-foreground">{marketInterpretation.state}</p>
              <p>{marketInterpretation.interpretation}</p>
              <p className="mt-2 text-xs">{marketInterpretation.action_rationale}</p>
              <p className="mt-2">Trap risk: {Math.round(marketInterpretation.trap_risk * 100)}%</p>
              <p>Conflict: {Math.round(marketInterpretation.conflict_score * 100)}%</p>
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Execution / Classifier</p>
              <p className="font-semibold text-foreground">{executionPlanTitle}</p>
              <p>Entry: {entryRange}</p>
              <p>Invalidation: {execution.invalidation === null ? "--" : formatPrice(execution.invalidation)}</p>
              <p>Targets: {execution.target1 === null ? "--" : formatPrice(execution.target1)}{execution.target2 === null ? "" : ` / ${formatPrice(execution.target2)}`}</p>
              <p className="mt-2">Intent: <span className="text-foreground">{asset.position_intent ?? "None"}</span></p>
              <p>Quality: <span className="text-foreground">{asset.position_quality ?? "Neutral"}</span></p>
            </div>
            <div className="space-y-1 text-xs">
              <p className="mb-1 font-semibold uppercase tracking-wider text-muted-foreground">Provenance / Filters</p>
              <p>Funding: {formatFundingRate(fundingRate)} - {fundingReliable ? "OK" : "UNREL"} - {fundingSource} - {formatAge(fundingAge)}</p>
              <p>Liquidation: {liquidationSource} - {formatAge(liquidationAge)}</p>
              <p>Taker: {formatRatio(takerRatio)} - {takerSource} - {formatAge(takerAge)}</p>
              <p>L/S: {formatRatio(longShortRatio)} - {longShortSource} - {formatAge(longShortAge)}</p>
              <p>Fallbacks: {fallbackFields.length > 0 ? fallbackFields.join(", ") : "none"}</p>
              <p>Scenario: {formatPipelineLabel(scenarioLabel)} / {formatPipelineLabel(scenarioDisposition)}</p>
              <p>Structure: {formatPipelineLabel(structuralPermission)}</p>
              <p>Final permission: {formatPipelineLabel(entryPermission)}</p>
              <p>Hard filters: {firstText(hardFilterReasons)}</p>
              <p>Blocks: {firstText(blockReasons)}</p>
              <p>Price: {formatPercent(toNumberOrNull(getProvenanceValue(asset, "price_change", timeframe)))} - OI Z {toNumberOrNull(getProvenanceValue(asset, "oi_delta_z", timeframe))?.toFixed(2) ?? "--"}</p>
              <p>Setup stats: <span className="text-foreground">{setupStats?.validated ? "validated" : "experimental"}</span></p>
            </div>
          </div>
        </details>
      </div>
    </article>
  );
}
