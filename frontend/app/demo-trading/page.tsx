"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Bot,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  Target,
  Shield,
  Power,
  XCircle,
  CheckCircle2,
  Clock,
  Loader2,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  BarChart3,
} from "lucide-react";
import { api } from "@/lib/api";

function formatPrice(price: number | null | undefined) {
  if (price === null || price === undefined) return "—";
  return price < 1
    ? price.toPrecision(4)
    : price.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export default function DemoTradingPage() {
  const [stats, setStats] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"open" | "closed">("open");
  const [closingId, setClosingId] = useState<number | null>(null);
  const [toggling, setToggling] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [statsData, posData] = await Promise.all([
        api.getDemoStats(),
        api.getDemoPositions(tab),
      ]);
      setStats(statsData);
      setPositions(posData.positions || []);
    } catch (err) {
      console.error("Failed to load demo data:", err);
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleClose = async (id: number) => {
    setClosingId(id);
    try {
      await api.closeDemoPosition(id);
      await loadData();
    } catch (err) {
      console.error("Failed to close position:", err);
    } finally {
      setClosingId(null);
    }
  };

  const handleToggle = async () => {
    setToggling(true);
    try {
      await api.toggleDemoTrading();
      await loadData();
    } catch (err) {
      console.error("Failed to toggle:", err);
    } finally {
      setToggling(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
        <p className="mt-4 text-muted-foreground">Loading Demo Trading...</p>
      </div>
    );
  }

  const isEnabled = stats?.bot_enabled;

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="absolute inset-0 rounded-2xl bg-violet-500/20 blur-xl" />
            <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-violet-600">
              <Bot className="h-7 w-7 text-white" />
            </div>
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Demo Trading</h1>
            <p className="text-sm text-muted-foreground">
              Autonomous bot — Binance Futures {stats?.use_testnet ? "Testnet" : "Live"}
            </p>
          </div>
        </div>

        <button
          onClick={handleToggle}
          disabled={toggling}
          className={`flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-bold transition-all ${
            isEnabled
              ? "bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/30"
              : "bg-rose-500/15 text-rose-400 hover:bg-rose-500/25 border border-rose-500/30"
          }`}
        >
          {toggling ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Power className="h-4 w-4" />
          )}
          {isEnabled ? "Bot ACTIVE" : "Bot DISABLED"}
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          label="Portfolio Value"
          value={`$${stats?.capital?.toLocaleString() ?? "—"}`}
          subvalue={`Initial: $${stats?.initial_capital?.toLocaleString()}`}
          icon={<DollarSign className="h-5 w-5" />}
          color="violet"
        />
        <StatCard
          label="Total PnL"
          value={`${stats?.total_pnl >= 0 ? "+" : ""}$${stats?.total_pnl?.toFixed(2) ?? "0"}`}
          subvalue={`${stats?.total_pnl_pct >= 0 ? "+" : ""}${stats?.total_pnl_pct?.toFixed(1)}%`}
          icon={stats?.total_pnl >= 0 ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
          color={stats?.total_pnl >= 0 ? "emerald" : "rose"}
        />
        <StatCard
          label="Win Rate"
          value={`${stats?.win_rate?.toFixed(0) ?? "0"}%`}
          subvalue={`${stats?.wins ?? 0}W / ${stats?.losses ?? 0}L`}
          icon={<Target className="h-5 w-5" />}
          color="blue"
        />
        <StatCard
          label="Total Trades"
          value={stats?.total_trades ?? 0}
          subvalue={`${stats?.open_positions ?? 0} Open`}
          icon={<BarChart3 className="h-5 w-5" />}
          color="amber"
        />
        <StatCard
          label="Avg Win / Loss"
          value={`$${stats?.avg_win?.toFixed(1) ?? "0"}`}
          subvalue={`Loss: $${stats?.avg_loss?.toFixed(1) ?? "0"}`}
          icon={<Activity className="h-5 w-5" />}
          color="cyan"
        />
      </div>

      {/* Bot Config Summary */}
      <div className="rounded-2xl border border-white/10 bg-card p-4">
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Base Size:</span>
            <span className="font-bold">${stats?.base_size}</span>
          </div>
          <div className="h-4 w-px bg-white/10" />
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Leverage:</span>
            <span className="font-bold text-amber-400">Max</span>
          </div>
          <div className="h-4 w-px bg-white/10" />
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Dynamic Sizing:</span>
            <span className="font-bold text-emerald-400">Enabled</span>
          </div>
          <div className="h-4 w-px bg-white/10" />
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Network:</span>
            <span className={`font-bold ${stats?.use_testnet ? "text-amber-400" : "text-rose-400"}`}>
              {stats?.use_testnet ? "Testnet (Demo)" : "Live"}
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {(["open", "closed"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-xl px-5 py-2.5 text-sm font-semibold capitalize transition-all ${
              tab === t
                ? "bg-violet-500/15 text-violet-400 shadow-lg shadow-violet-500/10"
                : "text-muted-foreground hover:bg-white/5"
            }`}
          >
            {t === "open" ? `Open (${stats?.open_positions ?? 0})` : `History (${stats?.total_trades ?? 0})`}
          </button>
        ))}
      </div>

      {/* Positions Table */}
      {positions.length === 0 ? (
        <div className="rounded-2xl border border-white/10 bg-card p-12 text-center">
          <Bot className="mx-auto h-12 w-12 text-muted-foreground/30" />
          <p className="mt-4 text-lg font-semibold text-muted-foreground">
            {tab === "open" ? "No open positions" : "No trade history yet"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground/70">
            {tab === "open"
              ? "The bot will automatically open positions when new V2 signals are generated."
              : "Completed trades will appear here."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {positions.map((pos) => (
            <PositionCard
              key={pos.id}
              position={pos}
              isClosing={closingId === pos.id}
              onClose={() => handleClose(pos.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  subvalue,
  icon,
  color,
}: {
  label: string;
  value: string | number;
  subvalue: string;
  icon: React.ReactNode;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    violet: "from-violet-500/15 to-violet-500/5 border-violet-500/20 text-violet-400",
    emerald: "from-emerald-500/15 to-emerald-500/5 border-emerald-500/20 text-emerald-400",
    rose: "from-rose-500/15 to-rose-500/5 border-rose-500/20 text-rose-400",
    blue: "from-blue-500/15 to-blue-500/5 border-blue-500/20 text-blue-400",
    amber: "from-amber-500/15 to-amber-500/5 border-amber-500/20 text-amber-400",
    cyan: "from-cyan-500/15 to-cyan-500/5 border-cyan-500/20 text-cyan-400",
  };

  return (
    <div className={`rounded-2xl border bg-gradient-to-br p-5 ${colorMap[color]}`}>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
        {icon}
      </div>
      <p className="text-2xl font-black tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{subvalue}</p>
    </div>
  );
}

function PositionCard({
  position,
  isClosing,
  onClose,
}: {
  position: any;
  isClosing: boolean;
  onClose: () => void;
}) {
  const isBuy = position.side === "BUY";
  const isOpen = position.status === "open";
  const isWin = position.result === "win";
  const isLoss = position.result === "loss";
  const pnlPositive = position.pnl_pct > 0;

  return (
    <div
      className={`rounded-2xl border bg-card p-5 transition-all hover:border-white/20 ${
        isOpen ? "border-violet-500/20" : isWin ? "border-emerald-500/15" : isLoss ? "border-rose-500/15" : "border-white/10"
      }`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        {/* Left */}
        <div className="flex items-center gap-4">
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-xl ${
              isBuy ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"
            }`}
          >
            {isBuy ? <ArrowUpRight className="h-5 w-5" /> : <ArrowDownRight className="h-5 w-5" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold">{position.symbol}</span>
              <span
                className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase ${
                  isBuy ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                }`}
              >
                {position.side}
              </span>
              {position.position_size_multiplier !== 1.0 && (
                <span className="rounded-md bg-violet-500/10 px-2 py-0.5 text-[10px] font-bold text-violet-400">
                  {position.position_size_multiplier.toFixed(2)}x
                </span>
              )}
              {isOpen && (
                <span className="flex items-center gap-1 rounded-md bg-blue-500/10 px-2 py-0.5 text-[10px] font-bold text-blue-400">
                  <Activity className="h-3 w-3" />
                  LIVE
                </span>
              )}
              {!isOpen && position.result && (
                <span
                  className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase ${
                    isWin ? "bg-emerald-500/10 text-emerald-400" : isLoss ? "bg-rose-500/10 text-rose-400" : "bg-amber-500/10 text-amber-400"
                  }`}
                >
                  {position.result}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Entry: ${formatPrice(position.entry_price)} · Qty: {position.quantity} · Size: ${position.notional_usdt?.toFixed(0)}
            </p>
          </div>
        </div>

        {/* Middle — Levels */}
        <div className="flex gap-6 text-center">
          <div>
            <p className="text-[10px] font-medium uppercase text-rose-400">SL</p>
            <p className="text-sm font-semibold tabular-nums">${formatPrice(position.sl_price)}</p>
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase text-emerald-400">TP1</p>
            <p className="text-sm font-semibold tabular-nums">${formatPrice(position.tp1_price)}</p>
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase text-emerald-400">TP2</p>
            <p className="text-sm font-semibold tabular-nums">${formatPrice(position.tp2_price)}</p>
          </div>
        </div>

        {/* Right — PnL & Actions */}
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p
              className={`text-xl font-black tabular-nums ${
                pnlPositive ? "text-emerald-400" : position.pnl_pct < 0 ? "text-rose-400" : "text-foreground"
              }`}
            >
              {pnlPositive ? "+" : ""}${position.pnl_usdt?.toFixed(2)}
            </p>
            <p
              className={`text-sm font-semibold ${
                pnlPositive ? "text-emerald-400/70" : position.pnl_pct < 0 ? "text-rose-400/70" : "text-muted-foreground"
              }`}
            >
              {pnlPositive ? "+" : ""}{position.pnl_pct?.toFixed(2)}%
            </p>
          </div>

          {isOpen && (
            <button
              onClick={onClose}
              disabled={isClosing}
              className="rounded-xl bg-rose-500/10 px-4 py-2 text-sm font-bold text-rose-400 transition hover:bg-rose-500/20 border border-rose-500/20"
            >
              {isClosing ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
            </button>
          )}

          {!isOpen && position.close_reason && (
            <span className="rounded-lg bg-white/5 px-3 py-1.5 text-xs text-muted-foreground">
              {position.close_reason}
            </span>
          )}

          {position.trade_signal_id && (
            <Link
              href={`/signals/${position.trade_signal_id}`}
              className="rounded-xl bg-violet-500/10 px-3 py-2 text-xs font-bold text-violet-400 transition hover:bg-violet-500/20"
            >
              Signal
            </Link>
          )}
        </div>
      </div>

      {position.error_message && (
        <div className="mt-3 rounded-xl bg-rose-500/5 px-4 py-2 text-xs text-rose-400 border border-rose-500/10">
          ⚠ {position.error_message}
        </div>
      )}
    </div>
  );
}
