import { toNumberOrNull } from "@/lib/formatters";
import type {
  AssetSnapshot,
  DecisionType,
  FlowMetrics,
  OiIntensity,
  PositionIntent,
  PositionQuality,
  Timeframe,
} from "@/lib/types";

export type TradeBias = "Bullish" | "Bearish" | "Neutral";
export type SetupType =
  | "Squeeze"
  | "Trap"
  | "Continuation"
  | "Compression"
  | "Watchlist"
  | "No clear edge";
export type SetupStatus = "Triggered" | "Ready" | "Developing" | "Unstable" | "Wait";
export type ConfidenceLabel = "High" | "Medium" | "Low";

export type ActionLayer = {
  tradeBias: TradeBias;
  setupType: SetupType;
  status: SetupStatus;
  confidenceLabel: ConfidenceLabel;
  opportunityScore: number;
};

export type RiskLevel = "Low" | "Medium" | "High";
export type QualityScore = "A" | "B" | "C";

export type ExecutionLayer = {
  entryType: "Breakout" | "Breakout Watch";
  entryMin: number | null;
  entryMax: number | null;
  invalidation: number | null;
  target: number | null;
  target1: number | null;
  target2: number | null;
  initialStop: number | null;
  riskLevel: RiskLevel;
  qualityScore: QualityScore;
};

export type NarrativeLayer = {
  intent: string;
  pressure: string;
  expectation: string;
};

export type TimingStage = "EARLY TREND" | "MID TREND" | "LATE TREND";

export type TimingContext = {
  stage: TimingStage;
  rationale: string;
};

export type StructureContext = {
  label: string;
  explanation: string;
};

export type DecisionReasoning = {
  title: string;
  bullets: string[];
};

export type RiskDetails = {
  squeezeProbability: number;
  crowdingLevel: "Low" | "Medium" | "High";
  lateTrendRisk: "Low" | "Medium" | "High";
  notes: string[];
};

export type ConfidenceExplanation = {
  label: ConfidenceLabel;
  reasons: string[];
};

export type PositioningExplanation = {
  summary: string;
  reasons: string[];
};

export type ExecutionContext = {
  entryRationale: string;
  invalidationRationale: string;
  confirmCondition: string;
  cancelCondition: string;
  flipBias: string;
};

export type Interpretation = {
  narrative: NarrativeLayer;
  decisionReasoning: DecisionReasoning;
  positioning: PositioningExplanation;
  conflicts: string[];
  timing: TimingContext;
  structure: StructureContext;
  risks: RiskDetails;
  confidence: ConfidenceExplanation;
  execution: ExecutionContext;
  invalidationConditions: string[];
};

type StoryInput = {
  intent?: PositionIntent | null;
  quality?: PositionQuality | null;
  decision?: DecisionType | null;
  reliability?: number | null;
};

function metric(asset: AssetSnapshot, timeframe: Timeframe, key: string): number {
  return toNumberOrNull(asset.flow_metrics?.[`${key}_${timeframe}` as keyof FlowMetrics]) ?? 0;
}

function confidenceLabel(value: number): ConfidenceLabel {
  if (value >= 0.85) {
    return "High";
  }
  if (value >= 0.75) {
    return "Medium";
  }
  return "Low";
}

function intentText(intent: PositionIntent | null | undefined): string {
  switch (intent) {
    case "Long Build-up":
      return "Long positioning fingerprint confirmed";
    case "Short Build-up":
      return "Short positioning fingerprint confirmed";
    case "Absorption":
      return "Absorption fingerprint confirmed";
    case "Pre-Squeeze":
      return "Pre-squeeze fingerprint confirmed";
    default:
      return "No valid positioning fingerprint";
  }
}

function qualityText(quality: PositionQuality | null | undefined): string {
  switch (quality) {
    case "Strong Longs":
      return "High-conviction long positioning";
    case "Building Longs":
      return "Long build is forming but not fully sharp yet";
    case "Weak Longs":
      return "Long build exists but lacks enough intensity";
    case "Trapped Longs":
      return "Long positioning is trapped and vulnerable to reversal";
    case "Strong Shorts":
      return "High-conviction short positioning";
    case "Building Shorts":
      return "Short build is forming but not fully sharp yet";
    case "Weak Shorts":
      return "Short build exists but lacks enough intensity";
    case "Trapped Shorts":
      return "Short positioning is trapped and vulnerable to reversal";
    case "Absorption-High":
      return "High-quality absorption with contained price";
    case "Absorption-Mid":
      return "Moderate absorption, still needs more pressure";
    case "Pre-Squeeze-Ready":
      return "Crowded pre-squeeze condition is ready";
    case "Pre-Squeeze-Building":
      return "Pre-squeeze structure is building";
    default:
      return "Position quality is neutral";
  }
}

function decisionText(decision: DecisionType | null | undefined, reliability: number | null | undefined): string {
  switch (decision) {
    case "Continuation-Long":
      return "Bullish continuation is favored";
    case "Continuation-Short":
      return "Bearish continuation is favored";
    case "Trap-Long":
      return "Short-side trap favors upside reversal";
    case "Trap-Short":
      return "Long-side trap favors downside reversal";
    case "Squeeze-Setup":
      return "Squeeze setup is forming but not triggered";
    case "Squeeze-Immediate":
      return "Squeeze setup is triggered";
    case "Watchlist-Long":
      return "Long structure is interesting but not executable yet";
    case "Watchlist-Short":
      return "Short structure is interesting but not executable yet";
    case "Watchlist-Squeeze":
      return "Squeeze structure is building, wait for trigger";
    default:
      if ((reliability ?? 0) < 0.75) {
        return "Edge is below the sharpness threshold";
      }
      return "No clear edge yet";
  }
}

function decisionBias(asset: AssetSnapshot, timeframe: Timeframe): TradeBias {
  switch (asset.decision_type) {
    case "Continuation-Long":
    case "Trap-Long":
      return "Bullish";
    case "Continuation-Short":
    case "Trap-Short":
      return "Bearish";
    case "Squeeze-Setup":
    case "Squeeze-Immediate": {
      const funding = metric(asset, timeframe, "funding_trend");
      const ls = metric(asset, timeframe, "long_short_ratio_delta");
      const taker = metric(asset, timeframe, "taker_buy_sell_ratio_delta");
      const crowdScore = (funding > 0 ? 1 : funding < 0 ? -1 : 0) + (ls > 0 ? 1 : ls < 0 ? -1 : 0) + (taker > 0 ? 1 : taker < 0 ? -1 : 0);
      if (crowdScore > 0) {
        return "Bearish";
      }
      if (crowdScore < 0) {
        return "Bullish";
      }
      return "Neutral";
    }
    default:
      return "Neutral";
  }
}

export function buildMarketStory(input: StoryInput) {
  return {
    intent: intentText(input.intent ?? null),
    pressure: qualityText(input.quality ?? null),
    expectation: decisionText(input.decision ?? null, input.reliability ?? null),
  };
}

export function buildStoryFromAsset(
  asset: AssetSnapshot,
  timeframe: Timeframe,
): { intent: string; pressure: string; expectation: string } {
  return buildInterpretation(asset, timeframe).narrative;
}

export function setupTypeFromDecision(
  decision: DecisionType | undefined | null,
  quality: PositionQuality | undefined | null,
): SetupType {
  if (decision === "Squeeze-Setup" || decision === "Squeeze-Immediate" || decision === "Watchlist-Squeeze") {
    return "Squeeze";
  }
  if (decision === "Trap-Long" || decision === "Trap-Short" || quality === "Trapped Longs" || quality === "Trapped Shorts") {
    return "Trap";
  }
  if (decision === "Continuation-Long" || decision === "Continuation-Short") {
    return "Continuation";
  }
  if (decision === "Watchlist-Long" || decision === "Watchlist-Short") {
    return "Watchlist";
  }
  if (quality === "Absorption-High" || quality === "Absorption-Mid") {
    return "Compression";
  }
  return "No clear edge";
}

function priceBreakThreshold(timeframe: Timeframe): number {
  if (timeframe === "15m") {
    return 0.012;
  }
  if (timeframe === "4h") {
    return 0.04;
  }
  if (timeframe === "24h") {
    return 0.08;
  }
  return 0.02;
}

function describeOiIntensity(intensity: OiIntensity | null | undefined, oiDeltaZ: number): string {
  if (intensity === "High") {
    return `High OI expansion (z ${oiDeltaZ.toFixed(2)})`;
  }
  if (intensity === "Mid") {
    return `Moderate OI expansion (z ${oiDeltaZ.toFixed(2)})`;
  }
  return `Low OI expansion (z ${oiDeltaZ.toFixed(2)})`;
}

function countConflicts(
  intent: PositionIntent,
  priceChange: number,
  takerDelta: number,
  fundingTrend: number,
  lsDelta: number,
): number {
  if (intent === "None" || intent === "Absorption" || intent === "Pre-Squeeze") {
    return 0;
  }
  const isLong = intent === "Long Build-up";
  let conflicts = 0;
  if ((priceChange < 0 && isLong) || (priceChange > 0 && !isLong)) {
    conflicts += 1;
  }
  if ((takerDelta < 0 && isLong) || (takerDelta > 0 && !isLong)) {
    conflicts += 1;
  }
  if ((fundingTrend < 0 && isLong) || (fundingTrend > 0 && !isLong)) {
    conflicts += 1;
  }
  if ((lsDelta < 0 && isLong) || (lsDelta > 0 && !isLong)) {
    conflicts += 1;
  }
  return conflicts;
}

export function buildActionLayer(
  asset: AssetSnapshot,
  timeframe: Timeframe,
): ActionLayer {
  const reliability = toNumberOrNull(asset.reliability_score) ?? 0;
  const decision = asset.decision_type ?? "No-Trade";
  const tradeBias = decisionBias(asset, timeframe);
  const conflictCount = countConflicts(
    asset.position_intent ?? "None",
    metric(asset, timeframe, "price_change"),
    metric(asset, timeframe, "taker_buy_sell_ratio_delta"),
    metric(asset, timeframe, "funding_trend"),
    metric(asset, timeframe, "long_short_ratio_delta"),
  );

  let setupType = setupTypeFromDecision(decision, asset.position_quality);
  let status: SetupStatus = "Wait";

  if (decision === "Squeeze-Immediate") {
    status = "Triggered";
  } else if (decision === "No-Trade") {
    status = "Wait";
  } else if (conflictCount >= 2) {
    status = "Unstable";
  } else if (reliability >= 0.8) {
    status = "Ready";
  } else {
    status = "Developing";
  }

  if (tradeBias === "Neutral" && decision !== "No-Trade") {
    setupType = setupType === "No clear edge" ? "Watchlist" : setupType;
  }

  return {
    tradeBias,
    setupType,
    status,
    confidenceLabel: confidenceLabel(reliability),
    opportunityScore: reliability * (toNumberOrNull(asset.priority_multiplier) ?? 1),
  };
}

export function getOpportunityScore(
  asset: AssetSnapshot,
  timeframe: Timeframe,
): number {
  return buildActionLayer(asset, timeframe).opportunityScore;
}

function alignmentScore(quality: PositionQuality, bias: TradeBias): number {
  if (quality === "Strong Longs") {
    return bias === "Bullish" ? 1 : 0;
  }
  if (quality === "Trapped Longs") {
    return bias === "Bearish" ? 1 : 0.2;
  }
  if (quality === "Strong Shorts") {
    return bias === "Bearish" ? 1 : 0;
  }
  if (quality === "Trapped Shorts") {
    return bias === "Bullish" ? 1 : 0.2;
  }
  if (quality === "Building Longs" || quality === "Building Shorts") {
    return bias === "Neutral" ? 0.4 : 0.65;
  }
  if (quality === "Absorption-High" || quality === "Absorption-Mid") {
    return bias === "Neutral" ? 0.5 : 0.7;
  }
  if (quality === "Pre-Squeeze-Ready" || quality === "Pre-Squeeze-Building") {
    return bias === "Neutral" ? 0.5 : 0.75;
  }
  return bias === "Neutral" ? 0.4 : 0.3;
}

function riskLevel(confidence: number): RiskLevel {
  if (confidence > 0.85) {
    return "Low";
  }
  if (confidence >= 0.75) {
    return "Medium";
  }
  return "High";
}

function qualityScore(confidence: number): QualityScore {
  return confidence > 0.85 ? "A" : confidence >= 0.75 ? "B" : "C";
}

export function buildExecutionLayer(
  asset: AssetSnapshot,
  timeframe: Timeframe,
): ExecutionLayer {
  const execution = asset.execution;
  if (!execution) {
    return {
      entryType: "Breakout",
      entryMin: null,
      entryMax: null,
      invalidation: null,
      target: null,
      target1: null,
      target2: null,
      initialStop: null,
      riskLevel: riskLevel(toNumberOrNull(asset.reliability_score) ?? 0),
      qualityScore: qualityScore(toNumberOrNull(asset.reliability_score) ?? 0),
    };
  }

  return {
    entryType: execution.entry_type === "Breakout" ? "Breakout" : "Breakout Watch",
    entryMin: execution.entry_min,
    entryMax: execution.entry_max,
    invalidation: execution.invalidation,
    target: execution.target,
    target1: execution.target_1,
    target2: execution.target_2,
    initialStop: execution.initial_stop,
    riskLevel: execution.risk_level,
    qualityScore: execution.quality_score,
  };
}

function timingContext(priceChange: number, oiDeltaZ: number, fundingTrend: number): TimingContext {
  if (Math.abs(priceChange) >= 0.03 && oiDeltaZ >= 1.5 && Math.abs(fundingTrend) >= 0.0025) {
    return {
      stage: "LATE TREND",
      rationale: "Price is extended, OI is already high, and crowding is elevated.",
    };
  }
  if (Math.abs(priceChange) >= 0.015 && oiDeltaZ >= 1.0) {
    return {
      stage: "MID TREND",
      rationale: "The move is active and OI is already confirming it.",
    };
  }
  return {
    stage: "EARLY TREND",
    rationale: "Structure is forming and the move is not yet fully extended.",
  };
}

function structureContext(
  timeframe: Timeframe,
  priceChange: number,
  compression: number,
): StructureContext {
  const breakThreshold = priceBreakThreshold(timeframe);
  if (compression >= 0.6 && Math.abs(priceChange) < breakThreshold) {
    return {
      label: "Compression",
      explanation: "Price is still inside a compressed range.",
    };
  }
  if (priceChange >= breakThreshold) {
    return {
      label: "Breakout",
      explanation: "Price has pushed above the breakout threshold.",
    };
  }
  if (priceChange <= -breakThreshold) {
    return {
      label: "Breakdown",
      explanation: "Price has pushed below the breakdown threshold.",
    };
  }
  return {
    label: "Range",
    explanation: "Price is still inside its active range.",
  };
}

export function buildInterpretation(
  asset: AssetSnapshot,
  timeframe: Timeframe,
): Interpretation {
  const intent = asset.position_intent ?? "None";
  const quality = asset.position_quality ?? "Neutral";
  const decision = asset.decision_type ?? "No-Trade";
  const reliability = toNumberOrNull(asset.reliability_score) ?? 0;
  const oiIntensity = asset.oi_intensity ?? "Low";
  const priceChange = metric(asset, timeframe, "price_change");
  const oiDeltaZ = metric(asset, timeframe, "oi_delta_z");
  const volumeZ = metric(asset, timeframe, "volume_z");
  const takerDelta = metric(asset, timeframe, "taker_buy_sell_ratio_delta");
  const fundingTrend = metric(asset, timeframe, "funding_trend");
  const lsDelta = metric(asset, timeframe, "long_short_ratio_delta");
  const oiChange = metric(asset, timeframe, "oi_change");
  const compression = metric(asset, timeframe, "compression_score");
  const fundingRate = toNumberOrNull(asset.funding_rate) ?? 0;
  const action = buildActionLayer(asset, timeframe);

  const narrative = buildMarketStory({ intent, quality, decision, reliability });
  const conflicts: string[] = [];
  const conflictCount = countConflicts(intent, priceChange, takerDelta, fundingTrend, lsDelta);
  if (conflictCount >= 2) {
    conflicts.push("Multiple inputs conflict with the active intent.");
  }
  if (asset.tf_conflict) {
    conflicts.push("15m intent conflicts with the 4h intent.");
  }

  const positionReasons = [
    describeOiIntensity(oiIntensity, oiDeltaZ),
    `Price change ${priceChange.toFixed(4)} vs active threshold.`,
    `Taker delta ${takerDelta.toFixed(4)} and L/S delta ${lsDelta.toFixed(4)}.`,
    `Funding trend ${fundingTrend.toFixed(6)} with funding rate ${fundingRate.toFixed(6)}.`,
  ];

  const decisionReasoning: DecisionReasoning = {
    title:
      decision === "Continuation-Long"
        ? "Bullish continuation"
        : decision === "Continuation-Short"
          ? "Bearish continuation"
          : decision === "Trap-Long"
            ? "Bullish trap reversal"
            : decision === "Trap-Short"
              ? "Bearish trap reversal"
            : decision === "Squeeze-Immediate"
              ? "Squeeze trigger armed"
            : decision === "Squeeze-Setup"
              ? "Squeeze setup forming"
              : decision.startsWith("Watchlist")
                ? "Watchlist only"
                : "No clear edge",
    bullets: [
      qualityText(quality),
      decisionText(decision, reliability),
      `State validator: ${asset.market_state} (${Math.round((asset.state_confidence ?? 0) * 100)}%).`,
    ],
  };

  const squeezeProbability = Math.min(
    0.95,
    Math.max(
      0.1,
      (decision === "Squeeze-Immediate" ? 0.75 : decision === "Squeeze-Setup" ? 0.6 : 0.2) +
        (Math.abs(fundingRate) >= 0.003 ? 0.05 : 0) +
        (Math.abs(lsDelta) >= 0.05 ? 0.05 : 0),
    ),
  );

  const crowdingValue = Math.abs(fundingRate) + (Math.abs(lsDelta) >= 0.05 ? 0.002 : 0) + (oiIntensity === "High" ? 0.002 : 0);
  const crowdingLevel: RiskDetails["crowdingLevel"] =
    crowdingValue >= 0.006 ? "High" : crowdingValue >= 0.003 ? "Medium" : "Low";

  const confidenceReasons: string[] = [];
  if (reliability >= 0.75) {
    confidenceReasons.push("Reliability is above the sharpness threshold.");
  } else {
    confidenceReasons.push("Reliability is below the sharpness threshold.");
  }
  if (oiIntensity === "High") {
    confidenceReasons.push("OI intensity is high.");
  } else if (oiIntensity === "Mid") {
    confidenceReasons.push("OI intensity is moderate.");
  } else {
    confidenceReasons.push("OI intensity is weak.");
  }
  if (volumeZ >= 0.8) {
    confidenceReasons.push("Volume confirms the structure.");
  } else {
    confidenceReasons.push("Volume confirmation is modest.");
  }
  if (conflicts.length) {
    confidenceReasons.push("Timeframe or signal conflict reduces trust.");
  }

  const execution = buildExecutionLayer(asset, timeframe);
  const executionContext: ExecutionContext =
    execution.entryMin === null
      ? {
          entryRationale: "Execution is not armed because the breakout trigger is not valid yet.",
          invalidationRationale: "No active invalidation because no executable setup is armed.",
          confirmCondition: "Wait for a valid breakout with OI and volume confirmation.",
          cancelCondition: "Cancel if the structure degrades or intent returns to neutral.",
          flipBias: "Bias flips only if the opposite fingerprint and validator confirm.",
        }
      : execution.entryType === "Breakout Watch"
        ? {
            entryRationale: "Execution is staged as a breakout watch and activates only if price reaches the trigger level.",
            invalidationRationale: "Invalidation sits on the opposite side of the current structure while the breakout is still pending.",
            confirmCondition: "Confirm entry only if price expands through the trigger with OI and volume support.",
            cancelCondition: "Cancel if price drifts away from the trigger or positioning collapses before the break.",
            flipBias: "Bias flips if the opposite fingerprint becomes valid and passes the validator.",
          }
      : {
          entryRationale: "Execution is armed on a breakout trigger that passed the backend gate.",
          invalidationRationale: "Invalidation is set at the opposite side of the breakout structure.",
          confirmCondition: "Entry remains valid while price, OI, and volume stay aligned.",
          cancelCondition: "Cancel if price rejects back through the breakout and OI unwinds.",
          flipBias: "Bias flips if the opposite continuation or squeeze condition becomes dominant.",
        };

  const invalidationConditions =
    action.tradeBias === "Bullish"
      ? [
          "Price falls back through the breakout area.",
          "Taker flow flips decisively negative.",
          "OI begins to unwind against the move.",
        ]
      : action.tradeBias === "Bearish"
        ? [
            "Price reclaims the breakdown area.",
            "Taker flow flips decisively positive.",
            "OI begins to unwind against the move.",
          ]
        : ["No trade. Wait for a fresh valid fingerprint."];

  return {
    narrative,
    decisionReasoning,
    positioning: {
      summary: `${quality} | ${decision}`,
      reasons: positionReasons,
    },
    conflicts,
    timing: timingContext(priceChange, oiDeltaZ, fundingTrend),
    structure: structureContext(timeframe, priceChange, compression),
    risks: {
      squeezeProbability,
      crowdingLevel,
      lateTrendRisk: Math.abs(priceChange) >= 0.03 && oiDeltaZ >= 1.5 ? "High" : Math.abs(priceChange) >= 0.015 ? "Medium" : "Low",
      notes: [
        `Funding rate ${fundingRate.toFixed(6)} and funding trend ${fundingTrend.toFixed(6)}.`,
        `LS delta ${lsDelta.toFixed(4)} and volume z ${volumeZ.toFixed(2)}.`,
      ],
    },
    confidence: {
      label: confidenceLabel(reliability),
      reasons: confidenceReasons,
    },
    execution: executionContext,
    invalidationConditions,
  };
}

export function formatDecisionBadge(decision: DecisionType | undefined | null): string {
  switch (decision) {
    case "Continuation-Long":
      return "Continuation Long";
    case "Continuation-Short":
      return "Continuation Short";
    case "Trap-Long":
      return "Trap Long";
    case "Trap-Short":
      return "Trap Short";
    case "Squeeze-Setup":
      return "Squeeze Setup";
    case "Squeeze-Immediate":
      return "Squeeze Triggered";
    case "Watchlist-Long":
      return "Watchlist Long";
    case "Watchlist-Short":
      return "Watchlist Short";
    case "Watchlist-Squeeze":
      return "Watchlist Squeeze";
    default:
      return "No Trade";
  }
}

export function conflictInsights(
  asset: AssetSnapshot,
  timeframe: Timeframe,
): string[] {
  return buildInterpretation(asset, timeframe).conflicts;
}
