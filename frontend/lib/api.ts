import type {
  AlertsResponse,
  AlertPreferences,
  AlertPreferencesUpdate,
  CoinDetailResponse,
  DashboardResponse,
  PerformanceResponse,
  PerformanceTradeTableResponse,
  RealtimeEvent,
  ScannerResponse,
  TelegramTestResponse,
  Timeframe,
} from "@/lib/types";
import { getUserId } from "@/lib/user";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(
  path: string,
  query?: Record<string, string | number | undefined>,
  init?: RequestInit,
): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === "") {
      return;
    }
    url.searchParams.set(key, String(value));
  });

  const headers = new Headers(init?.headers);
  if (typeof window !== "undefined") {
    headers.set("X-User-Id", getUserId());
  }

  const response = await fetch(url.toString(), {
    cache: "no-store",
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function fetchBlob(
  path: string,
  query?: Record<string, string | number | undefined>,
  init?: RequestInit,
): Promise<Blob> {
  const url = new URL(path, API_BASE_URL);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === "") {
      return;
    }
    url.searchParams.set(key, String(value));
  });

  const headers = new Headers(init?.headers);
  if (typeof window !== "undefined") {
    headers.set("X-User-Id", getUserId());
  }

  const response = await fetch(url.toString(), {
    cache: "no-store",
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.blob();
}

export const api = {
  getLiveSignals(query: { status?: "all" | "open" | "closed"; scope?: "all" | "active"; strategy?: string; regime?: "all" | "Balanced" | "Trending" | "Ranging"; limit?: number }): Promise<any> {
    return fetchJson<any>("/signals/live", {
      status: query.status ?? "all",
      scope: query.scope ?? "active",
      strategy: query.strategy ?? "v2_balanced",
      regime: query.regime ?? "all",
      limit: query.limit ?? 50,
    });
  },
  getDashboard(query: { symbol: string; timeframe: Timeframe; snapshotId: string }): Promise<DashboardResponse> {
    return fetchJson<DashboardResponse>("/dashboard", {
      symbol: query.symbol,
      timeframe: query.timeframe,
      snapshot_id: query.snapshotId,
    });
  },
  getScanner(query: {
    symbol: string;
    timeframe: Timeframe;
    snapshotId: string;
    signalType?: string;
    minScore?: number;
    maxScore?: number;
    search?: string;
  }): Promise<ScannerResponse> {
    return fetchJson<ScannerResponse>("/scanner", {
      symbol: query.symbol,
      timeframe: query.timeframe,
      snapshot_id: query.snapshotId,
      signal_type: query.signalType,
      min_score: query.minScore,
      max_score: query.maxScore,
      search: query.search,
    });
  },
  getWhaleRadar(): Promise<any> {
    return fetchJson<any>("/scanner/whale-radar");
  },
  getCoin(symbol: string, timeframe: Timeframe, snapshotId: string): Promise<CoinDetailResponse> {
    return fetchJson<CoinDetailResponse>(`/coin/${symbol}`, {
      timeframe,
      snapshot_id: snapshotId,
    });
  },
  getPerformance(query: { symbol: string; timeframe: Timeframe; snapshotId: string }): Promise<PerformanceResponse> {
    return fetchJson<PerformanceResponse>("/performance", {
      symbol: query.symbol,
      timeframe: query.timeframe,
      snapshot_id: query.snapshotId,
    });
  },
  getPerformanceReportData(query: {
    symbol?: string;
    timeframe?: Timeframe | "ALL";
    setupType?: string;
    scope?: "active" | "all";
    strategy?: string;
    capitalPerTrade: number;
    riskPerTrade?: number | null;
  }): Promise<PerformanceTradeTableResponse> {
    const params: Record<string, string | number> = {
      symbol: query.symbol ?? "ALL",
      timeframe: query.timeframe ?? "ALL",
      scope: query.scope ?? "active",
      strategy: query.strategy ?? "v2_balanced",
      capital_per_trade: query.capitalPerTrade,
    };
    if (query.setupType) params.setup_type = query.setupType;
    if (query.riskPerTrade && query.riskPerTrade > 0) params.risk_per_trade = query.riskPerTrade;
    return fetchJson<PerformanceTradeTableResponse>("/performance/report/data", params);
  },
  downloadPerformanceReport(query: {
    symbol?: string;
    timeframe?: Timeframe | "ALL";
    setupType?: string;
    strategy?: string;
    capitalPerTrade: number;
    riskPerTrade?: number | null;
    format?: "html" | "csv";
  }): Promise<Blob> {
    const params: Record<string, string | number> = {
      symbol: query.symbol ?? "ALL",
      timeframe: query.timeframe ?? "ALL",
      strategy: query.strategy ?? "v2_balanced",
      capital_per_trade: query.capitalPerTrade,
      format: query.format ?? "html",
    };
    if (query.setupType) params.setup_type = query.setupType;
    if (query.riskPerTrade && query.riskPerTrade > 0) params.risk_per_trade = query.riskPerTrade;
    return fetchBlob("/performance/report", params);
  },
  getSignalDetail(id: number | string): Promise<any> {
    return fetchJson(`/signals/${id}`);
  },
  getAlerts(query: {
    symbol: string;
    timeframes?: Timeframe[];
    snapshotId: string;
    signalType?: string;
    limit?: number;
  }): Promise<AlertsResponse> {
    const timeframeQuery = query.timeframes?.length === 1 ? query.timeframes[0] : "ALL";
    return fetchJson<AlertsResponse>("/alerts", {
      symbol: query.symbol,
      timeframe: timeframeQuery,
      timeframes: query.timeframes?.length ? query.timeframes.join(",") : undefined,
      snapshot_id: query.snapshotId,
      signal_type: query?.signalType,
      limit: query?.limit,
    });
  },
  getAlertPreferences(): Promise<AlertPreferences> {
    return fetchJson<AlertPreferences>("/alerts/preferences");
  },
  updateAlertPreferences(payload: AlertPreferencesUpdate): Promise<AlertPreferences> {
    return fetchJson<AlertPreferences>("/alerts/preferences", undefined, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  },
  testTelegramAlert(): Promise<TelegramTestResponse> {
    return fetchJson<TelegramTestResponse>("/alerts/test-telegram", undefined, {
      method: "POST",
    });
  },
  getWebSocketUrl(): string {
    const url = new URL("/ws/market", API_BASE_URL);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.toString();
  },

  // Demo Trading
  getDemoPositions(status: string = "all"): Promise<any> {
    return fetchJson<any>("/api/demo/positions", { status });
  },
  getDemoStats(): Promise<any> {
    return fetchJson<any>("/api/demo/stats");
  },
  closeDemoPosition(id: number): Promise<any> {
    return fetchJson<any>(`/api/demo/close/${id}`, undefined, { method: "POST" });
  },
  toggleDemoTrading(): Promise<any> {
    return fetchJson<any>("/api/demo/toggle", undefined, { method: "POST" });
  },
};

export type { RealtimeEvent };
