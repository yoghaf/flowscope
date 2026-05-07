"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, TrendingUp, DollarSign, BarChart3 } from "lucide-react";

import { useState, useEffect } from "react";
import ControlPanel from "./components/ControlPanel";
import StatCard from "./components/StatCard";
import EquityChart from "./components/EquityChart";
import TabsHeader from "./components/TabsHeader";
import PositionsTable from "./components/PositionsTable";
import OpenOrdersTable from "./components/OpenOrdersTable";
import OrderHistoryTable from "./components/OrderHistoryTable";
import TradeHistoryTable from "./components/TradeHistoryTable";
import AssetsPanel from "./components/AssetsPanel";
import SignalLog from "./components/SignalLog";
import DemoSettingsPanel from "./components/DemoSettingsPanel";
import NotificationModal, {
  type NotificationState,
  type NotificationTone,
} from "./components/NotificationModal";
import { api } from "@/lib/api";
import type {
  DemoStatus,
  DemoPosition,
  SignalEvent,
} from "@/lib/types";

export default function DemoTradingPage() {
  const queryClient = useQueryClient();
  
  // TAB STATE (BINANCE-STYLE)
  const [activeTab, setActiveTab] = useState<"positions" | "open" | "orders" | "trades" | "assets">("positions");
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [notification, setNotification] = useState<NotificationState | null>(null);

  const notify = (
    title: string,
    message: string,
    tone: NotificationTone = "info",
  ) => {
    setNotification({ title, message, tone });
  };

  const alert = (message: string) => {
    const lower = message.toLowerCase();
    const tone: NotificationTone = lower.includes("failed") || lower.includes("error")
      ? "error"
      : lower.includes("cannot") || lower.includes("validation")
        ? "warning"
        : lower.includes("success") || lower.includes("stopped") || lower.includes("closed")
          ? "success"
          : "info";
    notify("Demo Trading", message, tone);
  };
  
  // FRONTEND HAS NO STATE - Backend is single source of truth
  // User must explicitly click "Start Demo" to begin session

  // RULE 1: Fetch demo status FIRST (gate keeper)
  const { data: statusResponse, isLoading: statusLoading } = useQuery<{
    success: boolean;
    running: boolean;
    data?: any;
  }>({
    queryKey: ["demo", "status"],
    queryFn: () => api.getDemoStatus(),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });

  const status = statusResponse?.data;
  const isSessionRunning = statusResponse?.running === true;

  const { data: demoSettings, isLoading: settingsLoading } = useQuery({
    queryKey: ["demo", "settings"],
    queryFn: () => api.getDemoSettings(),
    refetchOnWindowFocus: false,
  });

  const updateSettingsMutation = useMutation({
    mutationFn: (payload: NonNullable<typeof demoSettings>) =>
      api.updateDemoSettings(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["demo", "settings"] });
      notify("Settings Saved", "Demo execution settings have been updated.", "success");
    },
    onError: (error: any) => {
      notify(
        "Failed To Save Settings",
        error?.message || "Unknown error",
        "error",
      );
    },
  });

  // RULE 2: Conditional fetch - ONLY fetch if session is running
  // Fetch active positions (DISABLED if session not running)
  const { data: positions, isLoading: positionsLoading } = useQuery<
    DemoPosition[]
  >({
    queryKey: ["demo", "positions"],
    queryFn: () => api.getDemoPositions(),
    refetchInterval: 3000,
    refetchIntervalInBackground: true,
    enabled: isSessionRunning, // 🔥 CRITICAL: Don't fetch if session not running
  });

  // Fetch signal events (DISABLED if session not running)
  const { data: signals, isLoading: signalsLoading } = useQuery<SignalEvent[]>({
    queryKey: ["demo", "signals"],
    queryFn: () => api.getDemoSignals(),
    refetchInterval: 2000,
    enabled: isSessionRunning, // 🔥 CRITICAL: Don't fetch if session not running
  });

  // 🔥 BINANCE-STYLE TABS - All queries gated by isSessionRunning
  const { data: openOrders, isLoading: openOrdersLoading } = useQuery({
    queryKey: ["demo", "open-orders"],
    queryFn: () => api.getDemoOpenOrders(),
    refetchInterval: 5000,
    enabled: isSessionRunning,
  });

  const { data: orderHistory, isLoading: orderHistoryLoading } = useQuery({
    queryKey: ["demo", "order-history"],
    queryFn: () => api.getDemoOrderHistory(100),
    refetchInterval: 15000,
    refetchOnWindowFocus: false,
    enabled: isSessionRunning,
  });

  const { data: tradeHistoryData, isLoading: tradeHistoryLoading } = useQuery({
    queryKey: ["demo", "trade-history"],
    queryFn: () => api.getDemoTradeHistory(100),
    refetchInterval: 15000,
    refetchOnWindowFocus: false,
    enabled: isSessionRunning,
  });

  const { data: assets, isLoading: assetsLoading } = useQuery({
    queryKey: ["demo", "assets"],
    queryFn: () => api.getDemoAssets(),
    refetchInterval: 10000,
    enabled: isSessionRunning,
  });

  // Start demo mutation
  const startMutation = useMutation({
    mutationFn: () => api.startDemo(),
    onSuccess: () => {
      // Invalidate ALL queries to refresh data
      queryClient.invalidateQueries({ queryKey: ["demo", "status"] });
      queryClient.invalidateQueries({ queryKey: ["demo", "assets"] });
      queryClient.invalidateQueries({ queryKey: ["demo", "positions"] });
      queryClient.invalidateQueries({ queryKey: ["demo", "open-orders"] });
      queryClient.invalidateQueries({ queryKey: ["demo", "order-history"] });
      queryClient.invalidateQueries({ queryKey: ["demo", "trade-history"] });
    },
    onError: (error: any) => {
      console.error("Failed to start demo:", error);

      // Handle specific error cases
      if (error?.response?.status === 400) {
        const detail = error?.response?.data?.detail || error.message;
        alert(
          `Cannot start demo session:\n\n${detail}\n\n` +
            `Solution:\n` +
            `1. Click "⚠️ Force Stop" to clear stuck session\n` +
            `2. Or click "⏹ Stop Demo" for graceful shutdown`,
        );
      } else if (error?.response?.status === 422) {
        alert(
          "Validation error:\n\n" +
            "Initial balance must be between $100 and $1,000,000\n\n" +
            "Please use the default value or enter a valid amount.",
        );
      } else {
        alert("Failed to start demo: " + (error?.message || "Unknown error"));
      }
    },
  });

  // Stop demo mutation
  const stopMutation = useMutation({
    mutationFn: () => api.stopDemo(),
    onSuccess: () => {
      // Clear ALL data queries, invalidate status
      queryClient.removeQueries({ queryKey: ["demo", "positions"] });
      queryClient.removeQueries({ queryKey: ["demo", "signals"] });
      queryClient.removeQueries({ queryKey: ["demo", "open-orders"] });
      queryClient.removeQueries({ queryKey: ["demo", "order-history"] });
      queryClient.removeQueries({ queryKey: ["demo", "trade-history"] });
      queryClient.removeQueries({ queryKey: ["demo", "assets"] });
      queryClient.invalidateQueries({ queryKey: ["demo", "status"] });
    },
    onError: (error) => {
      console.error("Failed to stop demo:", error);
      alert("Failed to stop demo: " + (error?.message || "Unknown error"));
    },
  });

  // Force stop demo mutation (for stuck sessions)
  const forceStopMutation = useMutation({
    mutationFn: () => api.forceStopDemo(),
    onSuccess: () => {
      // Clear ALL data queries, invalidate status
      queryClient.removeQueries({ queryKey: ["demo", "positions"] });
      queryClient.removeQueries({ queryKey: ["demo", "signals"] });
      queryClient.removeQueries({ queryKey: ["demo", "open-orders"] });
      queryClient.removeQueries({ queryKey: ["demo", "order-history"] });
      queryClient.removeQueries({ queryKey: ["demo", "trade-history"] });
      queryClient.removeQueries({ queryKey: ["demo", "assets"] });
      queryClient.invalidateQueries({ queryKey: ["demo", "status"] });
      alert(
        "✅ Demo session force stopped!\n\nYou can now start a new session.",
      );
    },
    onError: (error) => {
      console.error("Failed to force stop demo:", error);
      alert("Failed to force stop: " + (error?.message || "Unknown error"));
    },
  });

  // 🔥 BINANCE-STYLE ACTIONS
  const closePositionMutation = useMutation({
    mutationFn: (symbol: string) => api.closePosition(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["demo", "positions"] });
      alert("✅ Position closed successfully");
    },
    onError: (error) => {
      console.error("Failed to close position:", error);
      alert("Failed to close position: " + (error?.message || "Unknown error"));
    },
  });

  const reversePositionMutation = useMutation({
    mutationFn: (symbol: string) => api.reversePosition(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["demo", "positions"] });
      alert("✅ Position reversed successfully");
    },
    onError: (error) => {
      console.error("Failed to reverse position:", error);
      alert("Failed to reverse position: " + (error?.message || "Unknown error"));
    },
  });

  const cancelOrderMutation = useMutation({
    mutationFn: ({ symbol, orderId }: { symbol: string; orderId: number }) =>
      api.cancelOrder(symbol, orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["demo", "open-orders"] });
      alert("✅ Order cancelled successfully");
    },
    onError: (error) => {
      console.error("Failed to cancel order:", error);
      alert("Failed to cancel order: " + (error?.message || "Unknown error"));
    },
  });

  // Close all positions
  const closeAllPositionsMutation = useMutation({
    mutationFn: async () => {
      if (!positions || positions.length === 0) return;
      const results = await Promise.allSettled(
        positions.map((p) => api.closePosition(p.symbol))
      );
      return results;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["demo", "positions"] });
      queryClient.invalidateQueries({ queryKey: ["demo", "assets"] });
      queryClient.invalidateQueries({ queryKey: ["demo", "status"] });
      alert("✅ All positions closed");
    },
    onError: (error) => {
      alert("Failed to close all positions: " + (error?.message || "Unknown error"));
    },
  });

  // RULE 3: Calculate statistics - ONLY show if session running
  const hasActiveSession =
    statusResponse?.success === true && statusResponse?.running === true;

  // 🧪 STATE VALIDATION: Detect inconsistencies
  const hasInconsistency =
    hasActiveSession &&
    status &&
    positions &&
    // If session running but balance is null/undefined
    (status.current_balance === null ||
      status.current_balance === undefined ||
      // If session running but positions fetch failed unexpectedly
      (positions === null && status.current_balance > 0));

  // Log inconsistency for debugging
  if (hasInconsistency) {
    console.warn("⚠️ STATE INCONSISTENCY DETECTED:", {
      hasActiveSession,
      current_balance: status?.current_balance,
      positions_count: positions?.length,
    });
  }

  // RULE 4: UI State - idle vs trading dashboard
  const stats =
    hasActiveSession && status
      ? {
          // Trading dashboard state (session running)
          balance: status.current_balance ?? 0,
          balanceChange: 0,
          unrealizedPnl: status.total_unrealized_pnl ?? 0,
          totalTrades: status.statistics?.total_trades ?? 0,
          winningTrades: status.statistics?.winning_trades ?? 0,
          losingTrades: status.statistics?.losing_trades ?? 0,
          breakevenTrades: status.statistics?.breakeven_trades ?? 0,
          openPositions: status.statistics?.open_positions ?? status.positions_count ?? positions?.length ?? 0,
          partialCloses: status.statistics?.partial_closes ?? 0,
          winRate: status.statistics?.winrate ?? 0,
          profitFactor: 0,
          avgR: 0,
        }
      : {
          // Idle state (session not running)
          balance: 0,
          balanceChange: 0,
          unrealizedPnl: 0,
          totalTrades: 0,
          winningTrades: 0,
          losingTrades: 0,
          breakevenTrades: 0,
          openPositions: 0,
          partialCloses: 0,
          winRate: 0,
          profitFactor: 0,
          avgR: 0,
        };

  return (
    <div className="space-y-6">
      <NotificationModal
        notification={notification}
        onClose={() => setNotification(null)}
      />
      {/* Hero Section */}
      <div className="relative">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 via-blue-500/10 to-emerald-500/10 blur-3xl opacity-30" />
        <div className="relative">
          <div className="mb-3 flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">
              Binance Testnet Paper Trading
            </span>
          </div>
          <h1 className="mb-2 text-4xl font-bold tracking-tight text-foreground">
            🚀 FlowScope Demo Trading
          </h1>
          <p className="text-lg text-muted-foreground">
            V3 Adaptive Strategy - Real-time execution with virtual capital
          </p>
        </div>
      </div>

      {/* Control Panel */}
      <ControlPanel
        isRunning={isSessionRunning}
        status={status}
        isLoading={statusLoading}
        onStart={() => startMutation.mutate()}
        onStop={() => stopMutation.mutate()}
        onForceStop={() => forceStopMutation.mutate()}
        isStarting={startMutation.isPending}
        isStopping={stopMutation.isPending}
        isForceStopping={forceStopMutation.isPending}
      />

      <DemoSettingsPanel
        settings={demoSettings}
        isLoading={settingsLoading}
        isSaving={updateSettingsMutation.isPending}
        onSave={(settings) => updateSettingsMutation.mutate(settings)}
      />

      {/* Session State Warning */}
      {!hasActiveSession && !statusLoading && (
        <div className="rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-4 text-yellow-600 dark:text-yellow-400">
          <div className="flex items-center gap-2">
            <span className="text-xl">⚠️</span>
            <div>
              <p className="font-semibold">Demo session not started</p>
              <p className="text-sm opacity-80">
                Click &quot;▶ Start Demo&quot; to connect to Binance Testnet and
                fetch real balance
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Balance Error Warning */}
      {hasActiveSession && status?.current_balance === null && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4 text-red-600 dark:text-red-400">
          <div className="flex items-center gap-2">
            <span className="text-xl">🚨</span>
            <div>
              <p className="font-semibold">
                Failed to fetch balance from Binance Testnet
              </p>
              <p className="text-sm opacity-80">
                {status?.error || "API error - check backend logs"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 🧪 State Inconsistency Warning */}
      {hasInconsistency && (
        <div className="rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-4 text-yellow-600 dark:text-yellow-400">
          <div className="flex items-center gap-2">
            <span className="text-xl">⚠️</span>
            <div>
              <p className="font-semibold">State Inconsistency Detected</p>
              <p className="text-sm opacity-80">
                Session is running but data is incomplete. Try refreshing or
                restarting session.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* RULE 4: Render Logic - ONLY show dashboard if session running */}
      {hasActiveSession ? (
        // Trading Dashboard (session running)
        <>
          {/* Statistics Cards */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Balance"
              value={`$${stats.balance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              change={undefined}
              icon={DollarSign}
              trend="neutral"
            />
            <StatCard
              title="Unrealized PnL"
              value={`${stats.unrealizedPnl >= 0 ? "+" : ""}$${Math.abs(stats.unrealizedPnl).toFixed(2)}`}
              change={
                stats.unrealizedPnl !== 0
                  ? `${((stats.unrealizedPnl / (stats.balance || 1)) * 100).toFixed(2)}%`
                  : undefined
              }
              icon={TrendingUp}
              trend={stats.unrealizedPnl >= 0 ? "up" : "down"}
            />
            <StatCard
              title="Closed Trades"
              value={stats.totalTrades.toString()}
              change={
                stats.totalTrades > 0
                  ? `${stats.winningTrades}W / ${stats.losingTrades}L${stats.breakevenTrades ? ` / ${stats.breakevenTrades}BE` : ""}`
                  : stats.openPositions > 0
                    ? `${stats.openPositions} open${stats.partialCloses ? ` / ${stats.partialCloses} partial` : ""}`
                    : "No closed trades"
              }
              icon={Activity}
              trend="neutral"
            />
            <StatCard
              title="Win Rate"
              value={`${stats.winRate.toFixed(1)}%`}
              change={
                stats.totalTrades > 0
                  ? `${stats.winRate.toFixed(1)}% WR`
                  : "Closed trades only"
              }
              icon={BarChart3}
              trend={stats.winRate >= 50 ? "up" : "down"}
            />
          </div>

          {/* 🔥 BINANCE-STYLE TABS */}
          <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur">
            <TabsHeader
              activeTab={activeTab}
              onTabChange={setActiveTab}
              counts={{
                positions: positions?.length ?? 0,
                openOrders: openOrders?.length ?? 0,
                orderHistory: orderHistory?.length ?? 0,
                tradeHistory: tradeHistoryData?.length ?? 0,
              }}
            />

            {/* Positions Tab */}
            {activeTab === "positions" && (
              <PositionsTable
                positions={positions ?? []}
                isLoading={positionsLoading}
                protection={status?.protection ?? []}
                onClosePosition={(symbol) =>
                  closePositionMutation.mutate(symbol)
                }
                onReversePosition={(symbol) =>
                  reversePositionMutation.mutate(symbol)
                }
                onCloseAll={() => closeAllPositionsMutation.mutate()}
              />
            )}

            {/* Open Orders Tab */}
            {activeTab === "open" && (
              <OpenOrdersTable
                orders={openOrders ?? []}
                isLoading={openOrdersLoading}
                onCancelOrder={(symbol, orderId) =>
                  cancelOrderMutation.mutate({ symbol, orderId })
                }
              />
            )}

            {/* Order History Tab */}
            {activeTab === "orders" && (
              <OrderHistoryTable
                orders={orderHistory ?? []}
                isLoading={orderHistoryLoading}
              />
            )}

            {/* Trade History Tab */}
            {activeTab === "trades" && (
              <TradeHistoryTable
                trades={tradeHistoryData ?? []}
                isLoading={tradeHistoryLoading}
              />
            )}

            {/* Assets Tab */}
            {activeTab === "assets" && (
              <AssetsPanel assets={assets ?? {}} isLoading={assetsLoading} />
            )}
          </div>
        </>
      ) : (
        // Idle State (session not running)
        <div className="rounded-2xl border border-dashed border-muted-foreground/25 bg-muted/20 p-12 text-center">
          <Activity className="mx-auto h-16 w-16 text-muted-foreground/50" />
          <h3 className="mt-4 text-xl font-semibold">No Active Demo Session</h3>
          <p className="mt-2 text-muted-foreground">
            Click &quot;▶ Start Demo&quot; to begin trading with virtual capital
            on Binance Testnet
          </p>
          <div className="mt-6 flex justify-center gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4" />
              <span>Real-time balance from Binance</span>
            </div>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4" />
              <span>Live positions & PnL tracking</span>
            </div>
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              <span>Trade history & statistics</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
