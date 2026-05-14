import type { AssetSnapshot, Timeframe } from "@/lib/types";

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
  return value === true || value === "true" || value === "reliable" || value === "ALIGNED";
}

export function getProvenanceValue(asset: AssetSnapshot, field: string, timeframe: Timeframe): unknown {
  return flowValue(asset, `${field}_${timeframe}`) ?? (asset as unknown as Record<string, unknown>)[field];
}
