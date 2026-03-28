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
    capitalPerTrade: number;
  }): Promise<PerformanceTradeTableResponse> {
    return fetchJson<PerformanceTradeTableResponse>("/performance/report/data", {
      symbol: query.symbol ?? "ALL",
      timeframe: query.timeframe ?? "ALL",
      setup_type: query.setupType,
      capital_per_trade: query.capitalPerTrade,
    });
  },
  downloadPerformanceReport(query: {
    symbol?: string;
    timeframe?: Timeframe | "ALL";
    setupType?: string;
    capitalPerTrade: number;
    format?: "html" | "csv";
  }): Promise<Blob> {
    return fetchBlob("/performance/report", {
      symbol: query.symbol ?? "ALL",
      timeframe: query.timeframe ?? "ALL",
      setup_type: query.setupType,
      capital_per_trade: query.capitalPerTrade,
      format: query.format ?? "html",
    });
  },
  getAlerts(query: {
    symbol: string;
    timeframe: Timeframe;
    snapshotId: string;
    signalType?: string;
    limit?: number;
  }): Promise<AlertsResponse> {
    return fetchJson<AlertsResponse>("/alerts", {
      symbol: query.symbol,
      timeframe: query.timeframe,
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
  getWebSocketUrl(): string {
    const url = new URL("/ws/market", API_BASE_URL);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.toString();
  },
};

export type { RealtimeEvent };
