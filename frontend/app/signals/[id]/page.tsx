"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Activity,
  TrendingUp,
  TrendingDown,
  Target,
  Shield,
  Clock,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  ArrowDownRight,
  Loader2,
  Brain,
  Layers,
} from "lucide-react";
import { api } from "@/lib/api";

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function formatPrice(price: number | null) {
  if (price === null || price === undefined) return "—";
  return price < 1 ? price.toPrecision(4) : price.toLocaleString(undefined, { maximumFractionDigits: 4 });
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

export default function SignalDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [trade, setTrade] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Live Price State
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  const wsRef = useRef<WebSocket | null>(null);

  const loadTrade = useCallback(
    async (background = false) => {
      try {
        if (!background) {
          setLoading(true);
        }
        const data = await api.getSignalDetail(id);
        setTrade(data);
        setError(null);
      } catch (err: any) {
        if (!background) {
          setError(err.message || "Failed to load trade detail");
        }
      } finally {
        if (!background) {
          setLoading(false);
        }
      }
    },
    [id],
  );

  useEffect(() => {
    if (id) {
      void loadTrade(false);
    }
  }, [id, loadTrade]);

  useEffect(() => {
    if (!id || trade?.result !== "open") return;

    const interval = setInterval(() => {
      void loadTrade(true);
    }, 60000);

    return () => clearInterval(interval);
  }, [id, loadTrade, trade?.result]);

  // Binance WebSocket for Live Price
  useEffect(() => {
    if (!trade || trade.result !== "open") return;

    const symbol = typeof trade.symbol === "string" ? trade.symbol.toLowerCase() : "";
    if (!symbol) return;

    const wsUrl = `wss://fstream.binance.com/ws/${symbol}@ticker`;

    const connectWs = () => {
      setWsStatus("connecting");
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setWsStatus("connected");
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.c) {
            setLivePrice(parseFloat(data.c));
          }
        } catch (e) {}
      };
      ws.onclose = () => {
        setWsStatus("disconnected");
        // Reconnect after 3s
        setTimeout(connectWs, 3000);
      };
    };

    connectWs();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [trade?.result, trade?.symbol]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
        <p className="mt-4 text-muted-foreground">Loading trade detail...</p>
      </div>
    );
  }

  if (error || !trade) {
    return (
      <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-6 text-center">
        <p className="text-rose-400">{error || "Signal not found"}</p>
        <button
          onClick={() => router.push("/signals")}
          className="mt-4 rounded-xl bg-white/5 px-4 py-2 text-sm transition hover:bg-white/10"
        >
          Back to Signals
        </button>
      </div>
    );
  }

  const isBullish = trade.bias === "Bullish";
  const isOpen = trade.result === "open";
  const isWin = trade.result === "win";
  const tradeSymbol = typeof trade.symbol === "string" ? trade.symbol : "UNKNOWN";
  const entryPrice = asNumber(trade.entry_price);
  const invalidationPrice = asNumber(trade.invalidation_price);
  const targetPrice1 = asNumber(trade.target_price_1);
  const targetPrice2 = asNumber(trade.target_price_2);
  const confidenceRaw = asNumber(trade.confidence_score);
  const confidenceFallback = asNumber(trade.confidence);
  const confidenceScore =
    confidenceRaw ?? (confidenceFallback === null ? 0 : confidenceFallback > 1 ? confidenceFallback / 100 : confidenceFallback);
  const positionSizeMultiplier = asNumber(trade.position_size_multiplier);
  const insights = asStringArray(trade.insights);

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

  // Calculate live distance
  const currentPrice = isOpen && livePrice !== null ? livePrice : trade.closed_at ? null : entryPrice;
  
  const getDistanceStr = (target: number | null, current: number | null) => {
    if (target === null || current === null) return null;
    const diff = target - current;
    const pct = (diff / current) * 100;
    return `${diff > 0 ? '+' : ''}${pct.toFixed(2)}%`;
  };

  const livePnl =
    currentPrice !== null && entryPrice !== null
      ? ((currentPrice - entryPrice) / entryPrice) * 100 * (isBullish ? 1 : -1)
      : 0;

  const historyLogs = Array.isArray(trade?.history_logs)
    ? trade.history_logs
        .filter((log: unknown): log is Record<string, unknown> => Boolean(log) && typeof log === "object")
        .sort(
          (left: Record<string, unknown>, right: Record<string, unknown>) =>
            new Date(String(left.timestamp ?? 0)).getTime() - new Date(String(right.timestamp ?? 0)).getTime(),
        )
    : [];

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-20">
      {/* Header */}
      <button
        onClick={() => router.push("/signals")}
        className="group flex items-center gap-2 text-sm text-muted-foreground transition hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
        Back to Signals
      </button>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-4">
          <div
            className={`flex h-14 w-14 items-center justify-center rounded-2xl ${
              isBullish ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"
            }`}
          >
            {isBullish ? <TrendingUp className="h-7 w-7" /> : <TrendingDown className="h-7 w-7" />}
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight">{tradeSymbol}</h1>
              <span
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold uppercase ${
                  qualityColors[trade.quality_score] ?? qualityColors.C
                }`}
              >
                {trade.quality_score}-Grade
              </span>
              <span
                className={`rounded-lg border px-2.5 py-1 text-xs font-semibold uppercase ${
                  resultColors[trade.result] ?? resultColors.open
                }`}
              >
                {trade.result}
              </span>
              {trade.strategy_version !== "unknown" && (
                <span className="rounded-lg border border-violet-500/20 bg-violet-500/10 px-2.5 py-1 text-xs font-semibold uppercase text-violet-400">
                  {trade.strategy_version}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {trade.setup_type} · {trade.timeframe} · {trade.market_regime}
            </p>
          </div>
        </div>

        <div className="flex flex-col items-end gap-1 text-right">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>Created {new Date(trade.timestamp || trade.created_at).toLocaleString()}</span>
          </div>
          {trade.entry_touched_at && (
            <div className="text-xs text-muted-foreground/70">
              Entry hit at {new Date(trade.entry_touched_at).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      {/* Live Monitor */}
      {isOpen && (
        <div className="rounded-2xl border border-violet-500/20 bg-gradient-to-br from-violet-500/10 to-card p-6 shadow-lg shadow-violet-500/5">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-violet-400" />
              <h2 className="text-lg font-bold text-foreground">Live Monitor</h2>
              <div className="flex items-center gap-1.5 ml-2">
                <div className={`h-2 w-2 rounded-full ${wsStatus === 'connected' ? 'bg-emerald-500 animate-pulse' : 'bg-slate-500'}`} />
                <span className="text-xs text-muted-foreground">
                  {wsStatus === 'connected' ? 'Binance Live' : wsStatus}
                </span>
              </div>
            </div>
            {livePrice !== null && (
              <div className="text-right">
                <p className="text-2xl font-bold tabular-nums">${formatPrice(livePrice)}</p>
                <p className={`text-sm font-semibold ${livePnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {livePnl >= 0 ? '+' : ''}{livePnl.toFixed(2)}% from entry
                </p>
              </div>
            )}
          </div>

          {livePrice !== null && entryPrice !== null && invalidationPrice !== null && targetPrice1 !== null && (
            <div className="mt-6 relative h-24 rounded-xl bg-black/40 p-4 border border-white/5 overflow-hidden">
              {/* Visual Distance Bar */}
              <div className="absolute inset-0 flex flex-col justify-center px-8">
                <div className="h-1.5 w-full rounded-full bg-white/10 relative">
                  {/* Markers */}
                  <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)] z-10" style={{ left: '10%' }} title="Stop Loss" />
                  <div className="absolute top-1/2 -translate-y-1/2 w-1.5 h-6 bg-blue-500/50 z-0" style={{ left: '30%' }} title="Entry" />
                  <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)] z-10" style={{ left: '70%' }} title="TP1" />
                  
                  {/* Current Price Dot */}
                  {(() => {
                    // Very rough normalization for the visual bar (SL = 10%, Entry = 30%, TP1 = 70%)
                    const sl = invalidationPrice;
                    const en = entryPrice;
                    const tp = targetPrice1;
                    
                    let pos = 30; // default at entry
                    if (isBullish) {
                      if (livePrice <= sl) pos = 10;
                      else if (livePrice >= tp) pos = 70;
                      else if (livePrice < en) pos = 10 + ((livePrice - sl) / (en - sl)) * 20;
                      else pos = 30 + ((livePrice - en) / (tp - en)) * 40;
                    } else {
                      if (livePrice >= sl) pos = 10;
                      else if (livePrice <= tp) pos = 70;
                      else if (livePrice > en) pos = 10 + ((sl - livePrice) / (sl - en)) * 20;
                      else pos = 30 + ((en - livePrice) / (en - tp)) * 40;
                    }
                    
                    return (
                      <div 
                        className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center z-20 transition-all duration-500 ease-out" 
                        style={{ left: `${Math.max(5, Math.min(95, pos))}%` }}
                      >
                        <div className="text-[10px] font-bold text-white mb-1">${formatPrice(livePrice)}</div>
                        <div className="w-4 h-4 rounded-full border-2 border-white bg-violet-500 shadow-[0_0_15px_rgba(139,92,246,0.8)]" />
                      </div>
                    );
                  })()}
                </div>
              </div>
            </div>
          )}
        </div>
      )}


      {/* Trade Summary */}
      <div className="rounded-2xl border border-white/10 bg-card p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-bold">Trade Parameters</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-xl bg-white/[0.03] p-4">
            <p className="text-xs font-medium uppercase text-muted-foreground">Entry Zone</p>
            <p className="mt-1 text-xl font-bold">{formatPrice(entryPrice)}</p>
          </div>
          <div className="rounded-xl bg-rose-500/5 p-4 ring-1 ring-rose-500/10">
            <p className="text-xs font-medium uppercase text-rose-400">Stop Loss</p>
            <p className="mt-1 text-xl font-bold">{formatPrice(invalidationPrice)}</p>
            {currentPrice && (
              <p className="mt-1 text-xs text-rose-400/70">{getDistanceStr(invalidationPrice, currentPrice)}</p>
            )}
          </div>
          <div className={`rounded-xl p-4 ring-1 ${trade.tp1_hit ? 'bg-emerald-500/10 ring-emerald-500/20' : 'bg-emerald-500/5 ring-emerald-500/10'}`}>
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium uppercase text-emerald-400">Take Profit 1</p>
              {trade.tp1_hit && <CheckCircle2 className="h-3 w-3 text-emerald-400" />}
            </div>
            <p className="mt-1 text-xl font-bold">{formatPrice(targetPrice1)}</p>
            {currentPrice && !trade.tp1_hit && (
              <p className="mt-1 text-xs text-emerald-400/70">{getDistanceStr(targetPrice1, currentPrice)}</p>
            )}
          </div>
          <div className="rounded-xl bg-emerald-500/5 p-4 ring-1 ring-emerald-500/10">
            <p className="text-xs font-medium uppercase text-emerald-400">Take Profit 2</p>
            <p className="mt-1 text-xl font-bold">{formatPrice(targetPrice2)}</p>
          </div>
        </div>

        {!isOpen && (
          <div className="mt-6 flex flex-wrap items-center gap-4 rounded-xl bg-white/[0.02] p-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Final PnL:</span>
              <span className={`text-lg font-bold ${isWin ? "text-emerald-400" : "text-rose-400"}`}>
                {trade.pnl_pct > 0 ? "+" : ""}{trade.pnl_pct}%
              </span>
            </div>
            <div className="h-4 w-px bg-white/10" />
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Max Profit:</span>
              <span className="text-sm font-semibold text-emerald-400">+{trade.max_profit_pct}%</span>
            </div>
            <div className="h-4 w-px bg-white/10" />
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Max DD:</span>
              <span className="text-sm font-semibold text-rose-400">-{trade.max_drawdown_pct}%</span>
            </div>
            {trade.close_reason && (
              <>
                <div className="h-4 w-px bg-white/10" />
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Reason:</span>
                  <span className="rounded-md bg-white/10 px-2 py-0.5 text-xs font-medium">
                    {trade.close_reason}
                  </span>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        {/* Entry Rationale */}
        <div className="rounded-2xl border border-white/10 bg-card p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Brain className="h-5 w-5 text-violet-400" />
            <h2 className="text-lg font-bold">Entry Rationale</h2>
          </div>
          
          {insights.length > 0 && (
            <div className="mb-6 space-y-2">
              {insights.map((insight: string, i: number) => (
                <div key={i} className="flex items-start gap-2 text-sm text-foreground/80">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
                  <p>{insight}</p>
                </div>
              ))}
            </div>
          )}

          <div className="space-y-4 rounded-xl bg-white/[0.02] p-4">
            <div>
              <p className="text-xs font-medium text-muted-foreground">Market Interpretation</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {trade.trend && <Badge label="Trend" value={trade.trend} />}
                {trade.control && <Badge label="Control" value={trade.control} />}
                {trade.structure_label && <Badge label="Structure" value={trade.structure_label} />}
              </div>
            </div>
            {trade.scenario_rationale && (
              <div>
                <p className="text-xs font-medium text-muted-foreground">Scenario Rationale</p>
                <p className="mt-1 text-sm text-foreground/70">{trade.scenario_rationale}</p>
              </div>
            )}
          </div>
        </div>

        {/* Confidence Breakdown */}
        <div className="rounded-2xl border border-white/10 bg-card p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Target className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-bold">Confidence Breakdown</h2>
            <span className="ml-auto text-xl font-black text-emerald-400">{Math.round(confidenceScore * 100)}%</span>
          </div>

          <div className="space-y-4">
            <ProgressBar label="Flow Alignment" value={trade.flow_alignment} color="emerald" />
            <ProgressBar label="Structure Strength" value={trade.structure_strength} color="emerald" />
            <ProgressBar label="Clarity Score" value={trade.clarity_confidence} color="blue" />
            <ProgressBar label="Phase Confirmation" value={trade.phase_confidence} color="violet" />
            
            <div className="my-2 border-t border-white/5" />
            
            <ProgressBar label="Trap Risk" value={trade.trap_risk} color="rose" inverse />
            <ProgressBar label="Conflict Score" value={trade.conflict_score} color="rose" inverse />
          </div>

          <div className="mt-6 flex items-center justify-between rounded-xl bg-white/[0.03] p-4">
            <div>
              <p className="text-xs font-medium text-muted-foreground">Calculated Size</p>
              <p className="mt-1 text-lg font-bold">
                {positionSizeMultiplier === null ? "â€”" : `${positionSizeMultiplier.toFixed(2)}x`}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs font-medium text-muted-foreground">Risk Level</p>
              <p className="mt-1 text-lg font-bold capitalize">{trade.risk_level}</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Autopsy Brain & Metrics */}
      {!isOpen && trade.autopsy_rationale && (
        <div className="rounded-2xl border border-violet-500/30 bg-violet-500/5 p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Brain className="h-6 w-6 text-violet-400" />
            <h2 className="text-xl font-bold text-violet-100">Automated Autopsy</h2>
          </div>
          <p className="text-sm leading-relaxed text-violet-200/90">{trade.autopsy_rationale}</p>
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid gap-6 sm:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-card p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Layers className="h-5 w-5 text-blue-400" />
            <h2 className="text-lg font-bold">Snapshot at Entry</h2>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <MetricBox label="OI Change (1H)" value={trade.oi_change_1h} format="pct" />
            <MetricBox label="Funding (1H)" value={trade.funding_level_1h} format="pct" />
            <MetricBox label="Volume Z (1H)" value={trade.volume_z_1h} format="num" />
            <MetricBox label="Market Pressure" value={trade.market_pressure_1h} format="num" />
          </div>
        </div>

        {trade.exit_features && (
          <div className="rounded-2xl border border-white/10 bg-card p-6 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <Activity className="h-5 w-5 text-rose-400" />
              <h2 className="text-lg font-bold">Snapshot at Exit</h2>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <MetricBox 
                label="OI Delta" 
                value={(() => {
                  const openInterestOpen = asNumber(trade.exit_features.open_interest_open);
                  const openInterestClose = asNumber(trade.exit_features.open_interest_close);
                  if (openInterestOpen === null || openInterestClose === null) {
                    return null;
                  }

                  return ((openInterestClose - openInterestOpen) / (openInterestOpen || 1)) * 100;
                })()} 
                format="pct" 
              />
              <MetricBox label="Funding Rate" value={trade.exit_features.funding_rate_close} format="pct" />
              <MetricBox label="Volume Delta" value={trade.exit_features.volume_delta} format="num" />
              <MetricBox label="Market Pressure" value={trade.exit_features.market_pressure} format="num" />
            </div>
          </div>
        )}
      </div>

      {/* Trade Timeline (History Logs) */}
      {historyLogs.length > 0 && (
        <div className="mt-8 rounded-2xl border border-white/10 bg-card p-6 shadow-sm">
          <div className="mb-6 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-blue-400" />
              <h2 className="text-xl font-bold">Trade Journey & Timeline</h2>
            </div>
            <span className="text-xs font-medium text-muted-foreground bg-white/5 px-2 py-1 rounded-md">
              {historyLogs.length} updates recorded
            </span>
          </div>
          
          <div className="relative space-y-0 pl-4">
            {/* Vertical timeline line */}
            <div className="absolute bottom-0 left-[23px] top-4 w-px bg-white/10" />
            
            {historyLogs.map((log: any, index: number) => {
              const isClose = log.event === "close";
              const isTp1 = log.event === "tp1_hit";
              const logPnl = asNumber(log.pnl_pct) ?? 0;
              const logVolume = asNumber(log.volume);
              const logOi = asNumber(log.oi);
              const logTakerRatio = asNumber(log.taker_ratio);
              const logLongShortRatio = asNumber(log.long_short_ratio);
              const logFunding = asNumber(log.funding);
              const pnlColor = logPnl > 0 ? "text-emerald-400" : logPnl < 0 ? "text-rose-400" : "text-foreground";
              
              let dotColor = "bg-blue-500";
              let cardBg = "bg-white/[0.02] border-white/5";
              if (isClose) {
                dotColor = logPnl > 0 ? "bg-emerald-500" : "bg-rose-500";
                cardBg = logPnl > 0 ? "bg-emerald-500/5 border-emerald-500/20" : "bg-rose-500/5 border-rose-500/20";
              } else if (isTp1) {
                dotColor = "bg-emerald-400";
                cardBg = "bg-emerald-400/5 border-emerald-400/20";
              }
              
              return (
                <div key={index} className="relative flex gap-6 pb-6 last:pb-0">
                  <div className="relative z-10 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-background shadow-[0_0_0_4px_var(--background)] mt-1.5">
                    <div className={`h-2.5 w-2.5 rounded-full ${dotColor}`} />
                  </div>
                  
                  <div className={`flex-1 rounded-xl border p-4 ${cardBg}`}>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs font-medium text-muted-foreground">
                        {new Date(log.timestamp).toLocaleString(undefined, {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit"
                        })}
                      </p>
                      {isClose && (
                        <span className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${logPnl > 0 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}`}>
                          {log.reason || "Closed"}
                        </span>
                      )}
                      {isTp1 && (
                        <span className="rounded-md bg-emerald-400/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-300">
                          🎯 Partial TP1 Hit
                        </span>
                      )}
                    </div>
                    
                    <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                      <div>
                        <p className="text-[10px] uppercase text-muted-foreground">Price</p>
                        <p className="font-mono text-sm">{formatPrice(asNumber(log.price))}</p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase text-muted-foreground">PnL</p>
                        <p className={`font-mono text-sm font-bold ${pnlColor}`}>
                          {logPnl > 0 ? "+" : ""}{logPnl}%
                        </p>
                      </div>
                      {logVolume !== null && (
                        <div>
                          <p className="text-[10px] uppercase text-muted-foreground">Volume Delta</p>
                          <p className="font-mono text-sm">{logVolume.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                        </div>
                      )}
                      {logOi !== null && (
                        <div>
                          <p className="text-[10px] uppercase text-muted-foreground">Open Interest</p>
                          <p className="font-mono text-sm">{logOi.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                        </div>
                      )}
                      {logTakerRatio !== null && (
                        <div>
                          <p className="text-[10px] uppercase text-muted-foreground">Taker Ratio</p>
                          <p className={`font-mono text-sm ${logTakerRatio > 1 ? "text-emerald-400" : logTakerRatio < 1 ? "text-rose-400" : ""}`}>
                            {logTakerRatio.toFixed(3)}
                          </p>
                        </div>
                      )}
                      {logLongShortRatio !== null && (
                        <div>
                          <p className="text-[10px] uppercase text-muted-foreground">L/S Ratio</p>
                          <p className="font-mono text-sm">{logLongShortRatio.toFixed(3)}</p>
                        </div>
                      )}
                      {logFunding !== null && (
                        <div>
                          <p className="text-[10px] uppercase text-muted-foreground">Funding Fee</p>
                          <p className="font-mono text-sm">{(logFunding * 100).toFixed(4)}%</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

    </div>
  );
}

function Badge({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5 rounded-lg bg-white/5 px-2.5 py-1 text-xs">
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-semibold text-foreground">{value}</span>
    </div>
  );
}

function ProgressBar({ label, value, color, inverse = false }: { label: string; value: number | null | undefined; color: string; inverse?: boolean }) {
  const normalizedValue = asNumber(value);
  if (normalizedValue === null) return null;
  
  const pct = Math.round(normalizedValue * 100);
  const width = Math.min(100, Math.max(0, pct));
  
  const colorMap: Record<string, string> = {
    emerald: "bg-emerald-500",
    blue: "bg-blue-500",
    violet: "bg-violet-500",
    rose: "bg-rose-500",
  };

  const bgClass = colorMap[color] || "bg-slate-500";
  
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="font-medium text-muted-foreground">{label}</span>
        <span className="font-bold">{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
        <div 
          className={`h-full rounded-full ${bgClass} transition-all duration-1000 ease-out`} 
          style={{ width: `${width}%` }} 
        />
      </div>
    </div>
  );
}

function MetricBox({ label, value, format }: { label: string; value: number | null | undefined; format: "pct" | "num" }) {
  const normalizedValue = asNumber(value);
  if (normalizedValue === null) return null;
  
  let formatted = "";
  const isPositive = normalizedValue > 0;
  
  if (format === "pct") {
    formatted = `${isPositive ? '+' : ''}${normalizedValue.toFixed(2)}%`;
  } else {
    formatted = `${isPositive ? '+' : ''}${normalizedValue.toFixed(2)}`;
  }

  return (
    <div className="rounded-xl bg-white/[0.02] p-3">
      <p className="text-[10px] font-medium uppercase text-muted-foreground">{label}</p>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${isPositive ? 'text-emerald-400' : normalizedValue < 0 ? 'text-rose-400' : 'text-foreground'}`}>
        {formatted}
      </p>
    </div>
  );
}
