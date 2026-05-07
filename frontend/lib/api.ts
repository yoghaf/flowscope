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

const CONFIGURED_API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

function getApiBaseUrl(): string {
  if (CONFIGURED_API_BASE_URL) {
    return CONFIGURED_API_BASE_URL;
  }

  if (typeof window !== "undefined") {
    const url = new URL(window.location.origin);
    url.port = "8000";
    return url.toString();
  }

  return "http://localhost:8000";
}

function unwrapArrayResponse<T>(
  response: unknown,
  keys: string[],
): T[] {
  if (Array.isArray(response)) {
    return response as T[];
  }

  if (!response || typeof response !== "object") {
    return [];
  }

  const body = response as Record<string, unknown>;
  for (const key of keys) {
    if (Array.isArray(body[key])) {
      return body[key] as T[];
    }
  }

  if (Array.isArray(body.data)) {
    return body.data as T[];
  }

  return [];
}

function unwrapObjectResponse<T extends object>(
  response: unknown,
  key: string,
): T {
  if (response && typeof response === "object") {
    const body = response as Record<string, unknown>;
    const nested = body[key];
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      return nested as T;
    }
    return body as T;
  }

  return {} as T;
}

async function fetchJson<T>(
  path: string,
  query?: Record<string, string | number | boolean | undefined>,
  init?: RequestInit,
): Promise<T> {
  const url = new URL(path, getApiBaseUrl());
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
    // Try to extract detail message from FastAPI error response
    let detail = `Request failed: ${response.status}`;
    let errorBody: unknown = null;
    try {
      errorBody = await response.json();
      if (
        errorBody &&
        typeof errorBody === "object" &&
        "detail" in errorBody
      ) {
        detail = String((errorBody as { detail: unknown }).detail);
      }
    } catch {
      // Response body is not JSON, use status text
      detail = `Request failed: ${response.status} ${response.statusText}`;
    }
    const error = new Error(detail) as Error & {
      status?: number;
      response?: { status: number; data: unknown };
    };
    error.status = response.status;
    error.response = { status: response.status, data: errorBody };
    throw error;
  }

  return response.json() as Promise<T>;
}

async function fetchBlob(
  path: string,
  query?: Record<string, string | number | boolean | undefined>,
  init?: RequestInit,
): Promise<Blob> {
  const url = new URL(path, getApiBaseUrl());
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
  getLiveSignals(query: {
    status?: "all" | "open" | "closed";
    scope?: "all" | "active";
    strategy?: string;
    regime?: "all" | "Balanced" | "Trending" | "Ranging";
    timeframe?: Timeframe | "all";
    month?: string;
    limit?: number;
  }): Promise<any> {
    return fetchJson<any>("/signals/live", {
      status: query.status ?? "all",
      scope: query.scope ?? "active",
      strategy: query.strategy ?? "v2_balanced",
      regime: query.regime ?? "all",
      timeframe: query.timeframe ?? "all",
      month: query.month,
      limit: query.limit ?? 50,
    });
  },
  getDashboard(query: {
    symbol: string;
    timeframe: Timeframe;
    snapshotId: string;
  }): Promise<DashboardResponse> {
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
  getCoin(
    symbol: string,
    timeframe: Timeframe,
    snapshotId: string,
  ): Promise<CoinDetailResponse> {
    return fetchJson<CoinDetailResponse>(`/coin/${symbol}`, {
      timeframe,
      snapshot_id: snapshotId,
    });
  },
  getPerformance(query: {
    symbol: string;
    timeframe: Timeframe;
    snapshotId: string;
  }): Promise<PerformanceResponse> {
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
    regime?: "Trending" | "Ranging" | "Balanced" | "ALL";
    result?: "open" | "win" | "loss" | "breakeven" | "timeout" | "closed" | "ALL";
    month?: string;
    search?: string;
    scope?: "active" | "all";
    strategy?: string;
    simulationMode?: "fixed_size" | "fixed_risk" | "equity_risk_pct";
    startingCapital?: number;
    capitalPerTrade: number;
    riskPerTrade?: number | null;
    riskPctPerTrade?: number;
    feePct?: number;
    usePositionMultiplier?: boolean;
  }): Promise<PerformanceTradeTableResponse> {
    const params: Record<string, string | number | boolean> = {
      symbol: query.symbol ?? "ALL",
      timeframe: query.timeframe ?? "ALL",
      regime: query.regime ?? "ALL",
      result: query.result ?? "ALL",
      scope: query.scope ?? "active",
      strategy: query.strategy ?? "v2_balanced",
      simulation_mode: query.simulationMode ?? "fixed_risk",
      starting_capital: query.startingCapital ?? 1000,
      capital_per_trade: query.capitalPerTrade,
      risk_pct_per_trade: query.riskPctPerTrade ?? 1,
      fee_pct: query.feePct ?? 0,
      use_position_multiplier: query.usePositionMultiplier ?? true,
    };
    if (query.setupType) params.setup_type = query.setupType;
    if (query.month) params.month = query.month;
    if (query.search) params.search = query.search;
    if (query.riskPerTrade && query.riskPerTrade > 0)
      params.risk_per_trade = query.riskPerTrade;
    return fetchJson<PerformanceTradeTableResponse>(
      "/performance/report/data",
      params,
    );
  },
  downloadPerformanceReport(query: {
    symbol?: string;
    timeframe?: Timeframe | "ALL";
    setupType?: string;
    regime?: "Trending" | "Ranging" | "Balanced" | "ALL";
    result?: "open" | "win" | "loss" | "breakeven" | "timeout" | "closed" | "ALL";
    month?: string;
    search?: string;
    scope?: "active" | "all";
    strategy?: string;
    simulationMode?: "fixed_size" | "fixed_risk" | "equity_risk_pct";
    startingCapital?: number;
    capitalPerTrade: number;
    riskPerTrade?: number | null;
    riskPctPerTrade?: number;
    feePct?: number;
    usePositionMultiplier?: boolean;
    format?: "html" | "csv";
  }): Promise<Blob> {
    const params: Record<string, string | number | boolean> = {
      symbol: query.symbol ?? "ALL",
      timeframe: query.timeframe ?? "ALL",
      regime: query.regime ?? "ALL",
      result: query.result ?? "ALL",
      scope: query.scope ?? "active",
      strategy: query.strategy ?? "v2_balanced",
      simulation_mode: query.simulationMode ?? "fixed_risk",
      starting_capital: query.startingCapital ?? 1000,
      capital_per_trade: query.capitalPerTrade,
      risk_pct_per_trade: query.riskPctPerTrade ?? 1,
      fee_pct: query.feePct ?? 0,
      use_position_multiplier: query.usePositionMultiplier ?? true,
      format: query.format ?? "html",
    };
    if (query.setupType) params.setup_type = query.setupType;
    if (query.month) params.month = query.month;
    if (query.search) params.search = query.search;
    if (query.riskPerTrade && query.riskPerTrade > 0)
      params.risk_per_trade = query.riskPerTrade;
    return fetchBlob("/performance/report", params);
  },
  getSignalDetail(id: number | string): Promise<any> {
    return fetchJson(`/signals/${id}`);
  },
  getSignalKlines(query: {
    symbol: string;
    interval: "1m" | "5m" | "15m" | "1h" | "4h" | "1d";
    limit?: number;
  }): Promise<{
    symbol: string;
    interval: string;
    cached: boolean;
    generated_at: string;
    items: Array<{
      time: number;
      open: number;
      high: number;
      low: number;
      close: number;
    }>;
  }> {
    return fetchJson("/signals/klines", {
      symbol: query.symbol,
      interval: query.interval,
      limit: query.limit ?? 500,
    });
  },
  getAlerts(query: {
    symbol: string;
    timeframes?: Timeframe[];
    snapshotId: string;
    signalType?: string;
    limit?: number;
  }): Promise<AlertsResponse> {
    const timeframeQuery =
      query.timeframes?.length === 1 ? query.timeframes[0] : "ALL";
    return fetchJson<AlertsResponse>("/alerts", {
      symbol: query.symbol,
      timeframe: timeframeQuery,
      timeframes: query.timeframes?.length
        ? query.timeframes.join(",")
        : undefined,
      snapshot_id: query.snapshotId,
      signal_type: query?.signalType,
      limit: query?.limit,
    });
  },
  getAlertPreferences(): Promise<AlertPreferences> {
    return fetchJson<AlertPreferences>("/alerts/preferences");
  },
  updateAlertPreferences(
    payload: AlertPreferencesUpdate,
  ): Promise<AlertPreferences> {
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
  // Demo Trading API methods
  async getDemoStatus() {
    // Return FULL response - running is at ROOT, not in data
    const response = await fetchJson<{
      success: boolean;
      running: boolean;
      data?: any;
      balance?: number;
      positions?: any[];
    }>("/demo/status");
    return response; // ✅ Return entire response (success, running, data)
  },
  async getDemoPositions() {
    const response = await fetchJson<{
      success: boolean;
      data?: any[];
      positions?: any[];
    }>("/demo/positions");
    // Return positions array from backend response
    return response.positions || response.data || [];
  },
  async getDemoTrades() {
    const response = await fetchJson<{
      success: boolean;
      data?: any[];
      trades?: any[];
    }>("/demo/trades");
    return response.data || response.trades || [];
  },
  async getDemoSignals() {
    const response = await fetchJson<{
      success: boolean;
      data?: any[];
      signals?: any[];
    }>("/demo/signals");
    return response.data || response.signals || [];
  },
  async getDemoSettings() {
    return fetchJson<{
      auto_execute: boolean;
      risk_usdt: number;
      entry_mode: "market_only" | "market_pullback_limit";
      max_entry_drift_pct: number;
      max_market_tp1_progress_pct: number;
      max_pullback_tp1_progress_pct: number;
      tp1_close_pct: number;
      enabled_timeframes: string[];
      enabled_setups: string[];
      enabled_regimes: string[];
    }>("/demo/settings");
  },
  async updateDemoSettings(payload: {
    auto_execute?: boolean;
    risk_usdt?: number;
    entry_mode?: "market_only" | "market_pullback_limit";
    max_entry_drift_pct?: number;
    max_market_tp1_progress_pct?: number;
    max_pullback_tp1_progress_pct?: number;
    tp1_close_pct?: number;
    enabled_timeframes?: string[];
    enabled_setups?: string[];
    enabled_regimes?: string[];
  }) {
    return fetchJson<{
      auto_execute: boolean;
      risk_usdt: number;
      entry_mode: "market_only" | "market_pullback_limit";
      max_entry_drift_pct: number;
      max_market_tp1_progress_pct: number;
      max_pullback_tp1_progress_pct: number;
      tp1_close_pct: number;
      enabled_timeframes: string[];
      enabled_setups: string[];
      enabled_regimes: string[];
    }>("/demo/settings", undefined, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  },
  async startDemo() {
    const response = await fetchJson<{ success: boolean; data?: any }>(
      "/demo/start",
      undefined,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          description: "Demo trading session",
        }),
      },
    );
    return response.data || {};
  },
  async stopDemo() {
    const response = await fetchJson<{ success: boolean; data?: any }>(
      "/demo/stop",
      undefined,
      {
        method: "POST",
      },
    );
    return response.data || {};
  },
  async forceStopDemo() {
    const response = await fetchJson<{ success: boolean; data?: any }>(
      "/demo/force-stop",
      undefined,
      {
        method: "POST",
      },
    );
    return response.data || {};
  },
  // Binance-style tabs API methods (backend returns flat arrays directly)
  async getDemoOpenOrders() {
    const response = await fetchJson<unknown>("/demo/open-orders");
    return unwrapArrayResponse<any>(response, ["orders", "openOrders"]);
  },
  async getDemoOrderHistory(limit: number = 100) {
    const response = await fetchJson<unknown>("/demo/order-history", { limit });
    return unwrapArrayResponse<any>(response, ["orders", "orderHistory"]);
  },
  async getDemoTradeHistory(limit: number = 100) {
    const response = await fetchJson<unknown>("/demo/trade-history", { limit });
    return unwrapArrayResponse<any>(response, ["trades", "tradeHistory"]);
  },
  async getDemoAssets() {
    const response = await fetchJson<unknown>("/demo/assets");
    return unwrapObjectResponse<{
      wallet_balance: number;
      available_balance: number;
      unrealized_pnl: number;
      margin_balance: number;
      initial_margin: number;
      maintenance_margin: number;
    }>(response, "assets");
  },
  async closePosition(symbol: string) {
    const response = await fetchJson<{ success: boolean; message?: string }>(
      `/demo/close-position?symbol=${symbol}`,
      undefined,
      {
        method: "POST",
      },
    );
    return response;
  },
  async reversePosition(symbol: string) {
    const response = await fetchJson<{ success: boolean; message?: string }>(
      `/demo/reverse-position/${symbol}`,
      undefined,
      {
        method: "POST",
      },
    );
    return response;
  },
  async cancelOrder(symbol: string, orderId: number) {
    const response = await fetchJson<{ success: boolean; message?: string }>(
      `/demo/cancel-order?symbol=${symbol}&order_id=${orderId}`,
      undefined,
      {
        method: "POST",
      },
    );
    return response;
  },
  getWebSocketUrl(): string {
    const url = new URL("/ws/market", getApiBaseUrl());
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.toString();
  },
};

export type { RealtimeEvent };
