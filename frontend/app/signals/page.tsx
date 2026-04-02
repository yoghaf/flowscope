"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Target,
  Shield,
  Zap,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  ArrowDownRight,
  Loader2,
  BarChart3,
  Brain,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Signal {
  id: number;
  symbol: string;
  timeframe: string;
  bias: string;
  setup_type: string;
  status: string;
  result: string;
  market_regime: string;
  volatility_regime: string;
  entry_price: number | null;
  invalidation_price: number | null;
  target_price_1: number | null;
  target_price_2: number | null;
  risk_level: string;
  quality_score: string;
  confidence: number;
  pnl_pct: number;
  max_drawdown_pct: number;
  max_profit_pct: number;
  tp1_hit: boolean;
  insights: string[];
  created_at: string | null;
  closed_at: string | null;
  close_reason: string | null;
}

interface SignalsData {
  generated_at: string;
  total: number;
  summary: {
    total_closed: number;
    wins: number;
    losses: number;
    winrate: number;
    open_trades: number;
  };
  signals: Signal[];
}

function formatPrice(price: number | null) {
  if (price === null || price === undefined) return "—";
  return price < 1 ? price.toPrecision(4) : price.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function timeAgo(dateStr: string | null) {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function SignalsPage() {
  const [data, setData] = useState<SignalsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "open" | "closed">("all");
  const [error, setError] = useState<string | null>(null);

  const fetchSignals = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/signals/live?status=${filter}&limit=100`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch signals");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 30000);
    return () => clearInterval(interval);
  }, [fetchSignals]);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-lg shadow-violet-500/25">
              <Brain className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">AI Signals</h1>
              <p className="text-sm text-muted-foreground">
                Live trade signals powered by FlowScope V14 Engine
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {(["all", "open", "closed"] as const).map((f) => (
            <button
              key={f}
              id={`filter-${f}`}
              onClick={() => setFilter(f)}
              className={`rounded-xl px-4 py-2 text-sm font-medium capitalize transition-all ${
                filter === f
                  ? "bg-violet-500/20 text-violet-400 shadow-lg shadow-violet-500/10"
                  : "text-muted-foreground hover:bg-white/5"
              }`}
            >
              {f}
            </button>
          ))}
          <button
            id="refresh-signals"
            onClick={fetchSignals}
            className="ml-2 rounded-xl p-2.5 text-muted-foreground transition hover:bg-white/5 hover:text-foreground"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Summary cards */}
      {data?.summary && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard
            icon={<Activity className="h-4 w-4" />}
            label="Open Trades"
            value={data.summary.open_trades}
            color="blue"
          />
          <StatCard
            icon={<CheckCircle2 className="h-4 w-4" />}
            label="Wins"
            value={data.summary.wins}
            color="emerald"
          />
          <StatCard
            icon={<XCircle className="h-4 w-4" />}
            label="Losses"
            value={data.summary.losses}
            color="rose"
          />
          <StatCard
            icon={<Target className="h-4 w-4" />}
            label="Winrate"
            value={`${data.summary.winrate}%`}
            color={data.summary.winrate >= 60 ? "emerald" : data.summary.winrate >= 50 ? "amber" : "rose"}
          />
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-6 text-center">
          <p className="text-rose-400">{error}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Make sure the backend is running and accessible.
          </p>
        </div>
      )}

      {/* Loading state */}
      {loading && !data && (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
          <p className="mt-4 text-muted-foreground">Loading signals...</p>
        </div>
      )}

      {/* Empty state */}
      {data && data.signals.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-white/5 bg-card/50 py-20">
          <Zap className="h-12 w-12 text-muted-foreground/30" />
          <p className="mt-4 text-lg font-medium text-muted-foreground">No signals yet</p>
          <p className="mt-1 text-sm text-muted-foreground/60">
            The V14 engine is monitoring 143 tokens. Signals will appear here when A-Grade setups are detected.
          </p>
        </div>
      )}

      {/* Signals list */}
      {data && data.signals.length > 0 && (
        <div className="space-y-4">
          {data.signals.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    blue: "from-blue-500/20 to-blue-600/5 text-blue-400 border-blue-500/10",
    emerald: "from-emerald-500/20 to-emerald-600/5 text-emerald-400 border-emerald-500/10",
    rose: "from-rose-500/20 to-rose-600/5 text-rose-400 border-rose-500/10",
    amber: "from-amber-500/20 to-amber-600/5 text-amber-400 border-amber-500/10",
  };

  return (
    <div
      className={`rounded-2xl border bg-gradient-to-br p-5 ${colorMap[color] ?? colorMap.blue}`}
    >
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider opacity-80">
        {icon}
        {label}
      </div>
      <p className="mt-2 text-2xl font-bold">{value}</p>
    </div>
  );
}

function SignalCard({ signal }: { signal: Signal }) {
  const isBullish = signal.bias === "Bullish";
  const isOpen = signal.result === "open";
  const isWin = signal.result === "win";

  const resultColors: Record<string, string> = {
    open: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    win: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    loss: "bg-rose-500/10 text-rose-400 border-rose-500/20",
    breakeven: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    timeout: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  };

  const qualityColors: Record<string, string> = {
    A: "bg-emerald-500/15 text-emerald-400",
    B: "bg-amber-500/15 text-amber-400",
    C: "bg-slate-500/15 text-slate-400",
  };

  return (
    <div
      id={`signal-${signal.id}`}
      className={`group relative overflow-hidden rounded-2xl border transition-all duration-300 hover:scale-[1.005] hover:shadow-xl ${
        isOpen
          ? "border-violet-500/20 bg-gradient-to-br from-violet-500/5 to-card/80 shadow-lg shadow-violet-500/5"
          : "border-white/5 bg-card/50 hover:border-white/10"
      }`}
    >
      {/* Glow for open trades */}
      {isOpen && (
        <div className="absolute -right-20 -top-20 h-40 w-40 rounded-full bg-violet-500/10 blur-3xl" />
      )}

      <div className="relative p-6">
        {/* Top row */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`flex h-11 w-11 items-center justify-center rounded-xl ${
                isBullish
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "bg-rose-500/15 text-rose-400"
              }`}
            >
              {isBullish ? (
                <TrendingUp className="h-5 w-5" />
              ) : (
                <TrendingDown className="h-5 w-5" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold">{signal.symbol}</span>
                <span
                  className={`rounded-lg px-2 py-0.5 text-[10px] font-semibold uppercase ${qualityColors[signal.quality_score] ?? qualityColors.C}`}
                >
                  {signal.quality_score}-Grade
                </span>
                <span
                  className={`rounded-lg border px-2 py-0.5 text-[10px] font-semibold uppercase ${resultColors[signal.result] ?? resultColors.open}`}
                >
                  {signal.result}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {signal.setup_type} · {signal.timeframe} · {signal.market_regime} ·{" "}
                <Clock className="inline h-3 w-3" /> {timeAgo(signal.created_at)}
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-1 text-sm font-semibold">
              <BarChart3 className="h-3.5 w-3.5 text-violet-400" />
              <span className="text-violet-400">{signal.confidence}%</span>
            </div>
            <p className="text-[10px] text-muted-foreground">Confidence</p>
          </div>
        </div>

        {/* Price levels */}
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <PriceBox label="Entry" value={formatPrice(signal.entry_price)} icon={<ArrowUpRight className="h-3 w-3" />} />
          <PriceBox
            label="Stop Loss"
            value={formatPrice(signal.invalidation_price)}
            icon={<Shield className="h-3 w-3 text-rose-400" />}
            danger
          />
          <PriceBox
            label="TP1"
            value={formatPrice(signal.target_price_1)}
            icon={<Target className="h-3 w-3 text-emerald-400" />}
            success
            hit={signal.tp1_hit}
          />
          <PriceBox
            label="TP2"
            value={formatPrice(signal.target_price_2)}
            icon={<Target className="h-3 w-3 text-emerald-400" />}
            success
          />
        </div>

        {/* PnL bar for closed trades */}
        {!isOpen && (
          <div className="mt-4 flex items-center gap-4 rounded-xl bg-white/[0.02] px-4 py-3">
            <div className="flex items-center gap-1.5">
              {isWin ? (
                <ArrowUpRight className="h-4 w-4 text-emerald-400" />
              ) : (
                <ArrowDownRight className="h-4 w-4 text-rose-400" />
              )}
              <span className={`text-sm font-bold ${isWin ? "text-emerald-400" : "text-rose-400"}`}>
                {signal.pnl_pct > 0 ? "+" : ""}
                {signal.pnl_pct}%
              </span>
            </div>
            <div className="h-4 w-px bg-white/10" />
            <span className="text-xs text-muted-foreground">
              Max Profit: <span className="text-emerald-400/80">+{signal.max_profit_pct}%</span>
            </span>
            <span className="text-xs text-muted-foreground">
              Max DD: <span className="text-rose-400/80">-{signal.max_drawdown_pct}%</span>
            </span>
            {signal.close_reason && (
              <>
                <div className="h-4 w-px bg-white/10" />
                <span className="text-xs text-muted-foreground">
                  Reason: <span className="text-foreground/70">{signal.close_reason}</span>
                </span>
              </>
            )}
          </div>
        )}

        {/* Data Insights */}
        {signal.insights && signal.insights.length > 0 && (
          <div className="mt-4 rounded-xl border border-violet-500/10 bg-violet-500/[0.03] p-4">
            <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-violet-400">
              <Brain className="h-3.5 w-3.5" />
              Data Insights
            </div>
            <ul className="space-y-1">
              {signal.insights.map((insight, i) => (
                <li key={i} className="text-xs leading-relaxed text-foreground/70">
                  {insight}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function PriceBox({
  label,
  value,
  icon,
  danger,
  success,
  hit,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
  danger?: boolean;
  success?: boolean;
  hit?: boolean;
}) {
  return (
    <div
      className={`rounded-xl px-3 py-2.5 ${
        hit
          ? "bg-emerald-500/10 ring-1 ring-emerald-500/20"
          : danger
            ? "bg-rose-500/5"
            : success
              ? "bg-emerald-500/5"
              : "bg-white/[0.03]"
      }`}
    >
      <div className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {icon}
        {label}
        {hit && <CheckCircle2 className="h-3 w-3 text-emerald-400" />}
      </div>
      <p className="mt-1 text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}
