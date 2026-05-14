import type { AssetSnapshot, Timeframe } from "@/lib/types";

export type DisplayDecision =
  | "TRADE READY"
  | "WATCHLIST"
  | "WAIT"
  | "BLOCKED"
  | "NO SETUP"
  | "DATA ISSUE";

export type SystemReadinessState = "READY" | "WARMING_UP" | "DEGRADED" | "NO_DATA";

export interface SystemReadiness {
  state: SystemReadinessState;
  explanation: string;
  total: number;
  oiReliable: number;
  fundingReliable: number;
  liquidationFresh: number;
  ratioValid: number;
  dqFresh: number;
}

const HARD_REASON_LABELS: Record<string, string> = {
  mixed_context_blocked: "Mixed market context",
  scenario_not_allow: "Scenario not allowed yet",
  oi_delta_unreliable: "OI data not reliable",
  clarity_below_threshold: "Clarity below threshold",
  volatile_noise_no_structure: "Volatile noise, no structure",
  continuation_higher_timeframe_not_aligned: "Higher timeframe not aligned",
  continuation_flow_alignment_below_threshold: "Flow alignment too weak",
  chasing_pump_candle: "Chasing pump candle",
  exhaustion_oi_climax: "OI climax / exhaustion risk",
  efficient_build_taker_divergence_wait: "Taker/price divergence",
  missing_at_startup: "Waiting for source",
};

const HUMAN_LABELS: Record<string, string> = {
  mixed_context: "Mixed market",
  observe: "Observe",
  not_applicable: "No structure signal",
  stale: "Data stale",
  dq_stale: "Data stale",
  fallback_only: "Data fallback",
  fallback: "Data fallback",
  no_data: "No data",
  missing: "Missing data",
  invalid: "Invalid data",
  oi_degraded: "OI not ready",
  oi_delta_degraded: "OI not ready",
  ratio_degraded: "Ratio not fresh",
  ls_ratio_degraded: "Ratio not fresh",
  taker_ratio_degraded: "Ratio not fresh",
  missing_at_startup: "Waiting for source",
  structural_block: "Structural block",
  structural_watchlist: "Structural watchlist",
  watchlist_mixed_building: "Watchlist",
  watchlist_weak_propulsion: "Watchlist",
  watchlist_healthy_expansion: "Watchlist",
  wait_risk: "Wait",
  avoid_hard_risk: "Avoid",
  clean_mixed_context_building: "Watchlist: mixed context building",
  clean_weak_propulsion_waiting_confirmation: "Watchlist: waiting for confirmation",
  healthy_expansion_watch: "Watchlist: healthy expansion",
  long_watch: "Long Watch",
  short_watch: "Short Watch",
  neutral_watch: "Neutral Watch",
  long_trap_watch: "Long Trap Watch",
  short_squeeze_watch: "Short Squeeze Watch",
  no_direction: "No direction",
  no_trade: "No setup",
  no_clear_edge: "No clear edge",
};

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function toNumberOrNull(value: unknown): number | null {
  return isFiniteNumber(value) ? value : null;
}

export function shortSymbol(symbol: string): string {
  return symbol.replace(/USDT$/, "");
}

export function scoreToPercent(score: number | null | undefined): number {
  const numericScore = toNumberOrNull(score) ?? 0;
  return Math.round(numericScore * 100);
}

export function formatPrice(value: number | null | undefined): string {
  const numericValue = toNumberOrNull(value);
  if (numericValue === null) {
    return "--";
  }

  if (numericValue >= 1000) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numericValue);
  }
  
  if (numericValue >= 1) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }).format(numericValue);
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 8,
  }).format(numericValue);
}

export function formatCompactNumber(value: number | null | undefined): string {
  const numericValue = toNumberOrNull(value);
  if (numericValue === null) {
    return "--";
  }

  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(numericValue);
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  const numericValue = toNumberOrNull(value);
  if (numericValue === null) {
    return "--";
  }

  return `${numericValue >= 0 ? "+" : ""}${(numericValue * 100).toFixed(digits)}%`;
}

export function formatFundingRate(value: number | null | undefined): string {
  const numericValue = toNumberOrNull(value);
  if (numericValue === null) {
    return "--";
  }

  return `${(numericValue * 100).toFixed(3)}%`;
}

export function formatRatio(value: number | null | undefined, digits = 2): string {
  const numericValue = toNumberOrNull(value);
  if (numericValue === null) {
    return "--";
  }

  return numericValue.toFixed(digits);
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

export function formatTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export function getOiChange(asset: AssetSnapshot, timeframe: Timeframe): number | null {
  if (timeframe === "15m") {
    return toNumberOrNull(asset.flow_metrics?.oi_change_15m);
  }
  if (timeframe === "4h") {
    return toNumberOrNull(asset.flow_metrics?.oi_change_4h);
  }
  if (timeframe === "24h") {
    return toNumberOrNull(asset.flow_metrics?.oi_change_24h);
  }
  return toNumberOrNull(asset.flow_metrics?.oi_change_1h);
}

export function getVolumeChange(asset: AssetSnapshot, timeframe: Timeframe): number | null {
  if (timeframe === "15m") {
    return toNumberOrNull(asset.flow_metrics?.volume_change_15m);
  }
  if (timeframe === "4h") {
    return toNumberOrNull(asset.flow_metrics?.volume_change_4h);
  }
  if (timeframe === "24h") {
    return toNumberOrNull(asset.flow_metrics?.volume_change_24h);
  }
  return toNumberOrNull(asset.flow_metrics?.volume_change_1h);
}

function flowValue(asset: AssetSnapshot, field: string): unknown {
  return (asset.flow_metrics as unknown as Record<string, unknown> | undefined)?.[field];
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function normalizeDecisionText(value: string | null | undefined): string {
  return (value ?? "").toLowerCase().replace(/[\s-]+/g, "_");
}

function assetText(asset: AssetSnapshot): string {
  return [
    asset.decision_type,
    asset.setup_type,
    asset.signal,
    asset.market_interpretation?.action,
    asset.market_interpretation?.state,
    asset.market_interpretation?.structure_label,
    asset.market_state,
  ]
    .filter(Boolean)
    .join(" ");
}

export function normalizeReasonList(value: string[] | string | null | undefined): string[] {
  if (Array.isArray(value)) {
    return value.map(String).filter(Boolean);
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

export function getDqStatus(asset: AssetSnapshot, timeframe: Timeframe = "15m"): string {
  return (
    stringOrNull(flowValue(asset, `data_quality_status_${timeframe}`)) ??
    stringOrNull(asset.data_quality_status) ??
    asset.data_status ??
    "UNKNOWN"
  );
}

export function getFallbackFields(asset: AssetSnapshot, timeframe: Timeframe = "15m"): string[] {
  const timeframeFields = flowValue(asset, `fallback_fields_${timeframe}`);
  if (Array.isArray(timeframeFields)) {
    return timeframeFields.map(String).filter(Boolean);
  }
  return normalizeReasonList(asset.fallback_fields);
}

export function formatAge(seconds: number | null | undefined): string {
  const numeric = toNumberOrNull(seconds);
  if (numeric === null) {
    return "--";
  }
  if (numeric < 1) {
    return "<1s";
  }
  if (numeric < 60) {
    return `${Math.round(numeric)}s`;
  }
  if (numeric < 3600) {
    return `${Math.round(numeric / 60)}m`;
  }
  return `${(numeric / 3600).toFixed(1)}h`;
}

export function isReliable(value: unknown): boolean {
  return value === true || value === "true" || value === "reliable" || value === "ALIGNED" || value === "FRESH";
}

function isExplicitFalse(value: unknown): boolean {
  return value === false || value === "false" || value === "UNRELIABLE" || value === "MISSING";
}

export function getProvenanceValue(asset: AssetSnapshot, field: string, timeframe: Timeframe): unknown {
  return flowValue(asset, `${field}_${timeframe}`) ?? (asset as unknown as Record<string, unknown>)[field];
}

export function getEntryPermission(asset: AssetSnapshot): string {
  return stringOrNull(asset.final_entry_permission) ?? stringOrNull(flowValue(asset, "final_entry_permission")) ?? "UNKNOWN";
}

export function getLayer5WatchStatus(asset: AssetSnapshot): string {
  return stringOrNull(asset.layer5_watch_status) ?? stringOrNull(flowValue(asset, "layer5_watch_status")) ?? "NONE";
}

export function getLayer5WatchReason(asset: AssetSnapshot): string {
  return stringOrNull(asset.layer5_watch_reason) ?? stringOrNull(flowValue(asset, "layer5_watch_reason")) ?? "none";
}

export function getLayer5DirectionBias(asset: AssetSnapshot): string {
  return stringOrNull(asset.layer5_direction_bias) ?? stringOrNull(flowValue(asset, "layer5_direction_bias")) ?? "NO_DIRECTION";
}

export function getLayer5DirectionReason(asset: AssetSnapshot): string {
  return stringOrNull(asset.layer5_direction_reason) ?? stringOrNull(flowValue(asset, "layer5_direction_reason")) ?? "not_watchlist";
}

export function getStructuralPermission(asset: AssetSnapshot, timeframe: Timeframe = "15m"): string {
  return (
    stringOrNull(flowValue(asset, `final_structural_permission_${timeframe}`)) ??
    stringOrNull(asset.final_structural_permission) ??
    stringOrNull(flowValue(asset, "final_structural_permission")) ??
    "NOT_APPLICABLE"
  );
}

export function getScenarioLabel(asset: AssetSnapshot): string {
  return stringOrNull(asset.scenario_label) ?? stringOrNull(flowValue(asset, "scenario_label")) ?? "unknown";
}

export function getScenarioDisposition(asset: AssetSnapshot): string {
  return stringOrNull(asset.scenario_disposition) ?? stringOrNull(flowValue(asset, "scenario_disposition")) ?? "unknown";
}

export function getHardFilterReasons(asset: AssetSnapshot): string[] {
  const flowReasons = flowValue(asset, "hard_filter_reasons") as string[] | string | null | undefined;
  return normalizeReasonList(asset.hard_filter_reasons ?? flowReasons);
}

export function getBlockReasons(asset: AssetSnapshot): string[] {
  const flowReasons = flowValue(asset, "block_reasons") as string[] | string | null | undefined;
  return normalizeReasonList(asset.block_reasons ?? flowReasons);
}

export function getMainBlockReason(asset: AssetSnapshot): string {
  return getHardFilterReasons(asset)[0] ?? getBlockReasons(asset)[0] ?? "none";
}

export function getReasonLabel(reason: string): string {
  return HARD_REASON_LABELS[reason] ?? getHumanLabel(reason);
}

export function hasDataIssue(asset: AssetSnapshot, timeframe: Timeframe = "15m"): boolean {
  const dqStatus = getDqStatus(asset, timeframe).toUpperCase();
  return (
    ["STALE", "FALLBACK_ONLY", "MISSING", "NO_DATA", "INVALID"].includes(dqStatus) ||
    getFallbackFields(asset, timeframe).length > 0 ||
    isExplicitFalse(getProvenanceValue(asset, "oi_delta_reliable", timeframe)) ||
    isExplicitFalse(getProvenanceValue(asset, "funding_reliable", timeframe))
  );
}

export function isStructuralBlock(asset: AssetSnapshot, timeframe: Timeframe = "15m"): boolean {
  return getStructuralPermission(asset, timeframe).toUpperCase() === "STRUCTURAL_BLOCK";
}

export function isWatchlist(asset: AssetSnapshot, timeframe: Timeframe = "15m"): boolean {
  const entry = getEntryPermission(asset).toUpperCase();
  const structural = getStructuralPermission(asset, timeframe).toUpperCase();
  const layer5 = getLayer5WatchStatus(asset).toUpperCase();
  const text = normalizeDecisionText(assetText(asset));
  return (
    entry.includes("WATCHLIST") ||
    structural === "STRUCTURAL_WATCHLIST" ||
    layer5 === "WATCHLIST_MIXED_BUILDING" ||
    layer5 === "WATCHLIST_WEAK_PROPULSION" ||
    layer5 === "WATCHLIST_HEALTHY_EXPANSION" ||
    text.includes("watchlist")
  );
}

export function formatPipelineLabel(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  const normalized = value
    .replace(/^STRUCTURAL_/, "")
    .replace(/_/g, " ")
    .toLowerCase()
    .trim();
  if (!normalized) {
    return "Unknown";
  }
  return normalized
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function getHumanLabel(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }

  const normalized = normalizeDecisionText(value);
  if (HUMAN_LABELS[normalized]) {
    return HUMAN_LABELS[normalized];
  }

  return formatPipelineLabel(value);
}

export function getDqLabel(asset: AssetSnapshot, timeframe: Timeframe = "15m"): string {
  const status = normalizeDecisionText(getDqStatus(asset, timeframe));
  if (status === "stale") {
    return "Data stale";
  }
  return getHumanLabel(getDqStatus(asset, timeframe));
}

export function getScenarioDisplay(asset: AssetSnapshot): string {
  const label = getHumanLabel(getScenarioLabel(asset));
  const disposition = getHumanLabel(getScenarioDisposition(asset));
  return `${label} / ${disposition}`;
}

export function getStructureDisplay(asset: AssetSnapshot, timeframe: Timeframe = "15m"): string {
  return getHumanLabel(getStructuralPermission(asset, timeframe));
}

export function hasNoSetup(asset: AssetSnapshot): boolean {
  const text = normalizeDecisionText(assetText(asset));
  return text.includes("no_trade") || text.includes("no_clear_edge") || normalizeDecisionText(asset.decision_type) === "no_trade";
}

export function hasSomeSetup(asset: AssetSnapshot): boolean {
  return !hasNoSetup(asset) && Boolean(asset.decision_type ?? asset.setup_type ?? asset.signal ?? asset.market_interpretation?.state);
}

function hasDisplayDataIssue(asset: AssetSnapshot, timeframe: Timeframe): boolean {
  const dqStatus = normalizeDecisionText(getDqStatus(asset, timeframe));
  const dqCritical =
    dqStatus === "stale" ||
    dqStatus === "fallback" ||
    dqStatus === "fallback_only" ||
    dqStatus === "missing" ||
    dqStatus === "no_data" ||
    dqStatus === "invalid";
  const activeSetup = hasSomeSetup(asset);
  const requiredReliabilityFalse =
    isExplicitFalse(getProvenanceValue(asset, "oi_delta_reliable", timeframe)) ||
    isExplicitFalse(getProvenanceValue(asset, "funding_reliable", timeframe));

  return dqCritical || (activeSetup && requiredReliabilityFalse);
}

export function getDisplayDecision(asset: AssetSnapshot, timeframe: Timeframe = "15m"): DisplayDecision {
  const entry = normalizeDecisionText(getEntryPermission(asset));
  const scenario = normalizeDecisionText(getScenarioDisposition(asset));
  const structure = normalizeDecisionText(getStructuralPermission(asset, timeframe));
  const hardReasons = getHardFilterReasons(asset);
  const layer5 = normalizeDecisionText(getLayer5WatchStatus(asset));
  const text = normalizeDecisionText(assetText(asset));

  if (hasDisplayDataIssue(asset, timeframe)) {
    return "DATA ISSUE";
  }

  if (layer5 === "avoid_hard_risk") {
    return "BLOCKED";
  }

  if (
    layer5 === "watchlist_mixed_building" ||
    layer5 === "watchlist_weak_propulsion" ||
    layer5 === "watchlist_healthy_expansion"
  ) {
    return "WATCHLIST";
  }

  if (layer5 === "wait_risk") {
    return "WAIT";
  }

  if (entry === "block" || hardReasons.length > 0 || structure === "block" || structure === "structural_block") {
    return "BLOCKED";
  }

  const forbiddenReady =
    hasNoSetup(asset) ||
    scenario === "wait" ||
    scenario === "observe" ||
    scenario === "mixed_context" ||
    text.includes("mixed_context") ||
    text.includes("observe");

  if (
    entry === "allow" &&
    scenario === "allow" &&
    normalizeDecisionText(getDqStatus(asset, timeframe)) === "fresh" &&
    hardReasons.length === 0 &&
    !forbiddenReady
  ) {
    return "TRADE READY";
  }

  if (isWatchlist(asset, timeframe) || structure === "structural_watchlist") {
    return "WATCHLIST";
  }

  if ((scenario === "wait" || scenario === "observe") && hasSomeSetup(asset)) {
    return "WAIT";
  }

  if (hasNoSetup(asset)) {
    return "NO SETUP";
  }

  return "WAIT";
}

export function getHumanReason(asset: AssetSnapshot, timeframe: Timeframe = "15m"): string {
  const layer5 = normalizeDecisionText(getLayer5WatchStatus(asset));
  const layer5Reason = getLayer5WatchReason(asset);
  if (
    layer5 === "watchlist_mixed_building" ||
    layer5 === "watchlist_weak_propulsion" ||
    layer5 === "watchlist_healthy_expansion"
  ) {
    const direction = normalizeDecisionText(getLayer5DirectionBias(asset));
    if (
      direction === "long_watch" ||
      direction === "short_watch" ||
      direction === "neutral_watch" ||
      direction === "long_trap_watch" ||
      direction === "short_squeeze_watch"
    ) {
      return getHumanLabel(direction);
    }
    return getHumanLabel(layer5Reason);
  }
  if (layer5 === "wait_risk") {
    return layer5Reason.startsWith("wait_risk:")
      ? getHumanLabel(layer5Reason.split(":")[1])
      : getHumanLabel(layer5Reason);
  }

  const hardReason = getHardFilterReasons(asset)[0] ?? getBlockReasons(asset)[0];
  if (hardReason) {
    return getReasonLabel(hardReason);
  }

  const scenario = normalizeDecisionText(getScenarioDisposition(asset));
  const text = normalizeDecisionText(assetText(asset));
  const dqStatus = normalizeDecisionText(getDqStatus(asset, timeframe));

  if (hasNoSetup(asset)) {
    return "No clear edge";
  }
  if (isWatchlist(asset, timeframe)) {
    return "Watchlist only";
  }
  if (scenario === "observe") {
    return "Waiting for confirmation";
  }
  if (scenario === "mixed_context" || text.includes("mixed_context")) {
    return "Mixed market context";
  }
  if (dqStatus && dqStatus !== "fresh" && dqStatus !== "valid_signal" && dqStatus !== "valid") {
    return "Data quality degraded";
  }

  return "No trade reason available";
}

export function getDecisionTone(decision: DisplayDecision): string {
  switch (decision) {
    case "TRADE READY":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    case "WATCHLIST":
      return "border-blue-500/30 bg-blue-500/10 text-blue-300";
    case "WAIT":
      return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    case "BLOCKED":
      return "border-red-500/30 bg-red-500/10 text-red-300";
    case "DATA ISSUE":
      return "border-orange-500/30 bg-orange-500/10 text-orange-300";
    case "NO SETUP":
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

export function getSystemReadiness(assets: AssetSnapshot[], timeframe: Timeframe = "15m"): SystemReadiness {
  const total = assets.length;
  const oiReliable = assets.filter((asset) => isReliable(getProvenanceValue(asset, "oi_delta_reliable", timeframe))).length;
  const fundingReliable = assets.filter((asset) => isReliable(getProvenanceValue(asset, "funding_reliable", timeframe))).length;
  const liquidationFresh = assets.filter((asset) => {
    const source = String(getProvenanceValue(asset, "liquidation_source", timeframe) ?? "missing");
    return source !== "missing";
  }).length;
  const ratioValid = assets.filter((asset) => {
    const fallback = getFallbackFields(asset, timeframe);
    const takerSource = String(getProvenanceValue(asset, "taker_ratio_source", timeframe) ?? "missing");
    const longShortSource = String(getProvenanceValue(asset, "long_short_ratio_source", timeframe) ?? "missing");
    return (
      !fallback.some((field) => ["taker_ratio", "ls_ratio", "long_short_ratio"].includes(field)) &&
      takerSource !== "missing" &&
      longShortSource !== "missing"
    );
  }).length;
  const dqFresh = assets.filter((asset) => normalizeDecisionText(getDqStatus(asset, timeframe)) === "fresh").length;

  if (total === 0) {
    return {
      state: "NO_DATA",
      explanation: "No active 15m scanner data yet.",
      total,
      oiReliable,
      fundingReliable,
      liquidationFresh,
      ratioValid,
      dqFresh,
    };
  }

  const allHealthy =
    oiReliable === total &&
    fundingReliable === total &&
    liquidationFresh === total &&
    ratioValid === total &&
    dqFresh === total;
  if (allHealthy) {
    return {
      state: "READY",
      explanation: "Data foundation is healthy.",
      total,
      oiReliable,
      fundingReliable,
      liquidationFresh,
      ratioValid,
      dqFresh,
    };
  }

  const sourceCoverage = oiReliable + fundingReliable + liquidationFresh + ratioValid + dqFresh;
  const state: SystemReadinessState = dqFresh === 0 || sourceCoverage <= total ? "WARMING_UP" : "DEGRADED";

  return {
    state,
    explanation:
      state === "WARMING_UP"
        ? "Waiting for clean 15m data rollover."
        : "Some required data sources are stale or missing.",
    total,
    oiReliable,
    fundingReliable,
    liquidationFresh,
    ratioValid,
    dqFresh,
  };
}

export function getReadinessTone(state: SystemReadinessState): string {
  switch (state) {
    case "READY":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    case "WARMING_UP":
      return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    case "DEGRADED":
      return "border-orange-500/30 bg-orange-500/10 text-orange-300";
    case "NO_DATA":
      return "border-red-500/30 bg-red-500/10 text-red-300";
  }
}
