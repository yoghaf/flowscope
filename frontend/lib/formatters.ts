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

  const minimumFractionDigits = numericValue >= 1000 ? 2 : numericValue >= 1 ? 2 : 4;
  const maximumFractionDigits = numericValue >= 1000 ? 2 : numericValue >= 1 ? 4 : 6;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits,
    maximumFractionDigits,
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
