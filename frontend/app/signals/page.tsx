"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  Archive,
  BarChart3,
  Brain,
  CalendarDays,
  CheckCircle2,
  Clock,
  Loader2,
  RefreshCw,
  Search,
  Shield,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api";

type StatusFilter = "all" | "open" | "closed";
type ResultFilter = "all" | "win" | "loss" | "breakeven" | "timeout";
type RegimeFilter = "all" | "Balanced" | "Trending" | "Ranging";
type OutcomeTone = "blue" | "emerald" | "amber" | "rose" | "slate";

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
  trailing_stop_price: number | null;
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
  strategy_version: string;
  position_size_multiplier: number;
  confidence_score: number;
  opened_at: string | null;
  cohort_month: string;
  created_at: string | null;
  closed_at: string | null;
  close_reason: string | null;
  monitor_price?: number | null;
  monitor_price_at?: string | null;
  monitor_source?: string | null;
  monitor_pnl_pct?: number | null;
  monitor_r?: number | null;
  distance_to_stop_pct?: number | null;
  distance_to_tp1_pct?: number | null;
  distance_to_tp2_pct?: number | null;
}

interface SignalSummary {
  total_signals: number;
  total_closed: number;
  closed_trades: number;
  wins: number;
  losses: number;
  breakevens: number;
  timeouts: number;
  winrate: number;
  open_trades: number;
  realized_pnl_pct: number;
  avg_realized_pnl_pct: number;
  report_status: "Live" | "Final" | string;
}

interface MonthOption {
  value: string;
  label: string;
  total_signals: number;
  open_trades: number;
  closed_trades: number;
  report_status: "Live" | "Final" | string;
}

interface SignalsData {
  generated_at: string;
  selected_month: string;
  selected_month_label: string;
  available_months: MonthOption[];
  monthly_summary: SignalSummary;
  active_open_signals: Signal[];
  monthly_signals: Signal[];
  signals: Signal[];
}

function currentMonthKey() {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  return `${now.getFullYear()}-${month}`;
}

function monthLabel(month: string) {
  const [year, rawMonth] = month.split("-");
  const monthIndex = Number(rawMonth) - 1;
  if (!year || !Number.isFinite(monthIndex)) return month;
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    year: "numeric",
  }).format(new Date(Number(year), monthIndex, 1));
}

function formatPrice(price: number | null) {
  if (price === null || price === undefined) return "--";
  return price < 1
    ? price.toPrecision(4)
    : price.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function formatPercent(value: number | null | undefined, suffix = "%") {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}${suffix}`;
}

function formatDateTime(dateStr: string | null) {
  if (!dateStr) return "--";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(dateStr));
}

function timeAgo(dateStr: string | null) {
  if (!dateStr) return "--";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function isClosedResult(result: string) {
  return result === "win" || result === "loss" || result === "breakeven" || result === "timeout";
}

const outcomeToneClasses: Record<OutcomeTone, string> = {
  blue: "border-blue-500/20 bg-blue-500/10 text-blue-300",
  emerald: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  amber: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  rose: "border-rose-500/20 bg-rose-500/10 text-rose-300",
  slate: "border-white/10 bg-white/5 text-muted-foreground",
};

function closeReason(signal: Pick<Signal, "close_reason">) {
  return (signal.close_reason ?? "").toLowerCase();
}

function hitTp2(signal: Pick<Signal, "result" | "close_reason">) {
  const reason = closeReason(signal);
  return signal.result !== "open" && (reason.includes("target 2") || reason.includes("tp2"));
}

function hitInvalidation(signal: Pick<Signal, "result" | "close_reason">) {
  return signal.result !== "open" && closeReason(signal).includes("invalidation");
}

function hitBreakevenStop(signal: Pick<Signal, "result" | "close_reason">) {
  return signal.result !== "open" && closeReason(signal).includes("breakeven sl");
}

function hitTrailStop(signal: Pick<Signal, "result" | "close_reason">) {
  return signal.result !== "open" && closeReason(signal).includes("trail stop");
}

function signalOutcome(signal: Signal): { label: string; detail: string; tone: OutcomeTone } {
  if (signal.result === "open") {
    return signal.tp1_hit
      ? { label: "TP1 Hit", detail: "SL moved to entry, watching TP2", tone: "emerald" }
      : { label: "Watching", detail: "Waiting for TP1 or SL", tone: "blue" };
  }

  if (hitTp2(signal)) {
    return { label: "TP2 Hit", detail: "Final target reached", tone: "emerald" };
  }

  if (hitInvalidation(signal)) {
    return { label: "SL Hit", detail: signal.close_reason ?? "Invalidation", tone: "rose" };
  }

  if (hitBreakevenStop(signal)) {
    return { label: "BE Stop", detail: "TP1 hit, rest stopped at entry", tone: "amber" };
  }

  if (hitTrailStop(signal)) {
    return { label: "Trail Stop", detail: "TP1 hit, trailing stop closed", tone: "amber" };
  }

  if (signal.result === "timeout") {
    return { label: "Timeout", detail: signal.close_reason ?? "Entry never touched", tone: "slate" };
  }

  if (signal.result === "win" && signal.tp1_hit) {
    return { label: "TP Win", detail: "TP1/TP exit recorded, close reason missing", tone: "emerald" };
  }

  if (signal.result === "breakeven") {
    return { label: "Breakeven", detail: signal.close_reason ?? "Position closed flat", tone: "amber" };
  }

  if (signal.result === "loss") {
    return { label: "Risk Exit", detail: signal.close_reason ?? "Closed loss", tone: "rose" };
  }

  return { label: signal.result, detail: signal.close_reason ?? "Closed", tone: signal.pnl_pct >= 0 ? "emerald" : "rose" };
}

function signalMarkers(signal: Signal): Array<{ label: string; detail: string; tone: OutcomeTone; icon: ReactNode }> {
  const markers: Array<{ label: string; detail: string; tone: OutcomeTone; icon: ReactNode }> = [];
  const tp2Done = hitTp2(signal);
  const slDone = hitInvalidation(signal);
  const beStopDone = hitBreakevenStop(signal);
  const trailStopDone = hitTrailStop(signal);

  if (signal.tp1_hit) {
    markers.push({
      label: "TP1 Hit",
      detail: "Stop moved to entry",
      tone: "emerald",
      icon: <CheckCircle2 className="h-3 w-3" />,
    });
  } else if (signal.result === "open") {
    markers.push({
      label: "TP1 Pending",
      detail: signal.distance_to_tp1_pct !== null && signal.distance_to_tp1_pct !== undefined
        ? `${formatPercent(signal.distance_to_tp1_pct)} away`
        : "Waiting",
      tone: "blue",
      icon: <Target className="h-3 w-3" />,
    });
  }

  if (tp2Done) {
    markers.push({
      label: "TP2 Hit",
      detail: "Position completed",
      tone: "emerald",
      icon: <Target className="h-3 w-3" />,
    });
  } else if (slDone) {
    markers.push({
      label: "SL Hit",
      detail: signal.close_reason ?? "Invalidation",
      tone: "rose",
      icon: <Shield className="h-3 w-3" />,
    });
  } else if (beStopDone) {
    markers.push({
      label: "BE Stop",
      detail: "Closed after TP1",
      tone: "amber",
      icon: <Shield className="h-3 w-3" />,
    });
  } else if (trailStopDone) {
    markers.push({
      label: "Trail Stop",
      detail: "Closed after TP1",
      tone: "amber",
      icon: <Shield className="h-3 w-3" />,
    });
  } else if (signal.result === "open" && signal.tp1_hit) {
    markers.push({
      label: "TP2 Armed",
      detail: signal.distance_to_tp2_pct !== null && signal.distance_to_tp2_pct !== undefined
        ? `${formatPercent(signal.distance_to_tp2_pct)} away`
        : "Watching",
      tone: "amber",
      icon: <Target className="h-3 w-3" />,
    });
  } else if (signal.result === "open") {
    markers.push({
      label: "SL Armed",
      detail: signal.distance_to_stop_pct !== null && signal.distance_to_stop_pct !== undefined
        ? `${formatPercent(signal.distance_to_stop_pct)} buffer`
        : "Protected",
      tone: "rose",
      icon: <Shield className="h-3 w-3" />,
    });
  }

  return markers;
}

export default function SignalsPage() {
  const [data, setData] = useState<SignalsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMonth, setSelectedMonth] = useState(currentMonthKey);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [resultFilter, setResultFilter] = useState<ResultFilter>("all");
  const [regimeFilter, setRegimeFilter] = useState<RegimeFilter>("all");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const fetchSignals = useCallback(async () => {
    try {
      setLoading(true);
      const json = await api.getLiveSignals({
        status: "all",
        scope: "active",
        strategy: "v2_balanced",
        regime: regimeFilter,
        month: selectedMonth,
        limit: 200,
      });
      setData(json);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch signals");
    } finally {
      setLoading(false);
    }
  }, [regimeFilter, selectedMonth]);

  useEffect(() => {
    void fetchSignals();
    const interval = setInterval(fetchSignals, 30000);
    return () => clearInterval(interval);
  }, [fetchSignals]);

  const monthlySignals = useMemo(() => data?.monthly_signals ?? data?.signals ?? [], [data]);
  const activeOpenSignals = useMemo(() => data?.active_open_signals ?? [], [data]);

  const filteredMonthlySignals = useMemo(() => {
    const term = search.trim().toUpperCase();
    return monthlySignals.filter((signal) => {
      if (statusFilter === "open" && signal.result !== "open") return false;
      if (statusFilter === "closed" && !isClosedResult(signal.result)) return false;
      if (statusFilter === "closed" && resultFilter !== "all" && signal.result !== resultFilter) return false;
      if (term && !signal.symbol.toUpperCase().includes(term)) return false;
      return true;
    });
  }, [monthlySignals, resultFilter, search, statusFilter]);

  const summary = data?.monthly_summary;
  const months =
    data?.available_months?.length
      ? data.available_months
      : [
          {
            value: selectedMonth,
            label: monthLabel(selectedMonth),
            total_signals: 0,
            open_trades: 0,
            closed_trades: 0,
            report_status: "Live",
          },
        ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-violet-500/20 bg-violet-500/10 text-violet-300">
            <Brain className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">AI Signals</h1>
            <p className="text-sm text-muted-foreground">
              {data?.selected_month_label ?? monthLabel(selectedMonth)} cohort
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedMonth}
            onChange={(event) => setSelectedMonth(event.target.value)}
            className="h-10 rounded-lg border border-white/10 bg-card px-3 text-sm text-foreground outline-none transition focus:border-violet-500/50"
          >
            {months.map((month) => (
              <option key={month.value} value={month.value}>
                {month.label} ({month.total_signals})
              </option>
            ))}
          </select>

          <select
            value={regimeFilter}
            onChange={(event) => setRegimeFilter(event.target.value as RegimeFilter)}
            className="h-10 rounded-lg border border-white/10 bg-card px-3 text-sm text-foreground outline-none transition focus:border-violet-500/50"
          >
            <option value="all">All Regimes</option>
            <option value="Balanced">Balanced</option>
            <option value="Trending">Trending</option>
            <option value="Ranging">Ranging</option>
          </select>

          <button
            id="refresh-signals"
            onClick={fetchSignals}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 text-muted-foreground transition hover:bg-white/5 hover:text-foreground"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <StatCard icon={<CalendarDays className="h-4 w-4" />} label="Opened" value={summary?.total_signals ?? 0} />
        <StatCard icon={<CheckCircle2 className="h-4 w-4" />} label="Closed" value={summary?.closed_trades ?? 0} tone="emerald" />
        <StatCard icon={<Activity className="h-4 w-4" />} label="Still Open" value={summary?.open_trades ?? 0} tone="blue" />
        <StatCard icon={<Target className="h-4 w-4" />} label="Win Rate" value={`${summary?.winrate ?? 0}%`} tone={summary && summary.winrate >= 55 ? "emerald" : "amber"} />
        <StatCard icon={<BarChart3 className="h-4 w-4" />} label="Realized" value={formatPercent(summary?.realized_pnl_pct)} tone={(summary?.realized_pnl_pct ?? 0) >= 0 ? "emerald" : "rose"} />
        <StatCard icon={<Archive className="h-4 w-4" />} label="Report" value={summary?.report_status ?? "Live"} tone={summary?.report_status === "Final" ? "slate" : "violet"} />
      </div>

      <div className="flex flex-col gap-3 border-y border-white/10 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {(["all", "open", "closed"] as const).map((status) => (
            <button
              key={status}
              onClick={() => {
                setStatusFilter(status);
                if (status !== "closed") setResultFilter("all");
              }}
              className={`h-9 rounded-lg px-3 text-sm font-medium capitalize transition ${
                statusFilter === status
                  ? "bg-violet-500/15 text-violet-300 ring-1 ring-violet-500/30"
                  : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
              }`}
            >
              {status}
            </button>
          ))}

          {statusFilter === "closed" && (
            <>
              <div className="mx-1 h-6 w-px bg-white/10" />
              {(["all", "win", "loss", "breakeven", "timeout"] as const).map((result) => (
                <button
                  key={result}
                  onClick={() => setResultFilter(result)}
                  className={`h-9 rounded-lg px-3 text-xs font-semibold uppercase transition ${
                    resultFilter === result
                      ? "bg-white/10 text-foreground ring-1 ring-white/15"
                      : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
                  }`}
                >
                  {result === "all" ? "All Results" : result}
                </button>
              ))}
            </>
          )}
        </div>

        <label className="relative block w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search symbol"
            className="h-10 w-full rounded-lg border border-white/10 bg-card pl-9 pr-3 text-sm outline-none transition placeholder:text-muted-foreground focus:border-violet-500/50"
          />
        </label>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-4 text-sm text-rose-300">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-violet-300" />
          <p className="mt-3 text-sm">Loading signals...</p>
        </div>
      ) : (
        <>
          <section className="space-y-3">
            <SectionHeader
              title="Open Signals"
              meta={`${activeOpenSignals.length} active`}
              icon={<Activity className="h-4 w-4" />}
            />
            {activeOpenSignals.length === 0 ? (
              <EmptyState text="No open signals" />
            ) : (
              <div className="space-y-2">
                {activeOpenSignals.map((signal) => (
                  <SignalRow
                    key={`active-${signal.id}`}
                    signal={signal}
                    livePrice={signal.monitor_price ?? null}
                    selectedMonth={selectedMonth}
                    showCohort
                  />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <SectionHeader
              title={`Signals Opened In ${data?.selected_month_label ?? monthLabel(selectedMonth)}`}
              meta={`${filteredMonthlySignals.length} shown`}
              icon={<CalendarDays className="h-4 w-4" />}
            />
            {filteredMonthlySignals.length === 0 ? (
              <EmptyState text="No signals for this view" />
            ) : (
              <div className="space-y-2">
                {filteredMonthlySignals.map((signal) => (
                  <SignalRow
                    key={`monthly-${signal.id}`}
                    signal={signal}
                    livePrice={signal.monitor_price ?? null}
                    selectedMonth={selectedMonth}
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  tone = "slate",
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  tone?: "slate" | "blue" | "emerald" | "rose" | "amber" | "violet";
}) {
  const toneMap: Record<string, string> = {
    slate: "border-white/10 bg-card text-foreground",
    blue: "border-blue-500/20 bg-blue-500/5 text-blue-300",
    emerald: "border-emerald-500/20 bg-emerald-500/5 text-emerald-300",
    rose: "border-rose-500/20 bg-rose-500/5 text-rose-300",
    amber: "border-amber-500/20 bg-amber-500/5 text-amber-300",
    violet: "border-violet-500/20 bg-violet-500/5 text-violet-300",
  };

  return (
    <div className={`rounded-lg border p-4 ${toneMap[tone]}`}>
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className="mt-2 text-2xl font-bold tabular-nums">{value}</p>
    </div>
  );
}

function SectionHeader({
  title,
  meta,
  icon,
}: {
  title: string;
  meta: string;
  icon: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <span className="text-violet-300">{icon}</span>
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      <span className="rounded-lg border border-white/10 px-2 py-1 text-xs font-medium text-muted-foreground">
        {meta}
      </span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-card/50 px-4 py-10 text-center text-sm text-muted-foreground">
      {text}
    </div>
  );
}

function SignalRow({
  signal,
  livePrice,
  selectedMonth,
  showCohort = false,
}: {
  signal: Signal;
  livePrice: number | null;
  selectedMonth: string;
  showCohort?: boolean;
}) {
  const isBullish = signal.bias === "Bullish";
  const isOpen = signal.result === "open";
  const isWin = signal.result === "win";
  const outcome = signalOutcome(signal);
  const markers = signalMarkers(signal);
  const tp2Done = hitTp2(signal);
  const stopDone = hitInvalidation(signal) || hitBreakevenStop(signal) || hitTrailStop(signal);
  const stopLabel = hitInvalidation(signal)
    ? "SL Hit"
    : hitBreakevenStop(signal)
      ? "BE Stop"
      : hitTrailStop(signal)
        ? "Trail Stop"
        : signal.tp1_hit && signal.trailing_stop_price
          ? "Trail"
          : "Stop";
  const livePnl =
    isOpen && signal.monitor_pnl_pct !== undefined
      ? signal.monitor_pnl_pct
      : isOpen && livePrice !== null && signal.entry_price
        ? ((livePrice - signal.entry_price) / signal.entry_price) * 100 * (isBullish ? 1 : -1)
        : null;

  const outcomeToneClass = outcomeToneClasses[outcome.tone];

  return (
    <Link
      href={`/signals/${signal.id}`}
      id={`signal-${signal.id}`}
      className="grid gap-4 rounded-lg border border-white/10 bg-card/70 p-4 transition hover:border-violet-500/35 hover:bg-card lg:grid-cols-[minmax(220px,1.2fr)_minmax(260px,1.4fr)_minmax(180px,0.9fr)_minmax(140px,0.7fr)]"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${
              isBullish ? "bg-emerald-500/10 text-emerald-300" : "bg-rose-500/10 text-rose-300"
            }`}
          >
            {isBullish ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
          </span>
          <span className="truncate text-base font-bold">{signal.symbol}</span>
          <span className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase ${outcomeToneClass}`}>
            {outcome.label}
          </span>
          <span className="rounded-md border border-white/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-muted-foreground">
            {signal.quality_score}
          </span>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {signal.setup_type} / {signal.timeframe} / {signal.market_regime}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          <Clock className="h-3 w-3" />
          <span>{timeAgo(signal.opened_at ?? signal.created_at)}</span>
          <span>{formatDateTime(signal.opened_at ?? signal.created_at)}</span>
          {showCohort && signal.cohort_month !== selectedMonth ? (
            <span className="rounded-md bg-white/5 px-2 py-0.5">
              Opened {monthLabel(signal.cohort_month)}
            </span>
          ) : null}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {markers.map((marker) => (
            <OutcomeBadge key={`${signal.id}-${marker.label}`} {...marker} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="Entry" value={formatPrice(signal.entry_price)} />
        <Metric
          label={stopLabel}
          value={formatPrice(signal.tp1_hit && signal.trailing_stop_price ? signal.trailing_stop_price : signal.invalidation_price)}
          tone="rose"
          icon={<Shield className="h-3 w-3" />}
          highlight={stopDone}
        />
        <Metric
          label={signal.tp1_hit ? "TP1 Hit" : "TP1"}
          value={formatPrice(signal.target_price_1)}
          tone="emerald"
          icon={signal.tp1_hit ? <CheckCircle2 className="h-3 w-3" /> : <Target className="h-3 w-3" />}
          highlight={signal.tp1_hit}
        />
        <Metric
          label={tp2Done ? "TP2 Hit" : "TP2"}
          value={formatPrice(signal.target_price_2)}
          tone="emerald"
          icon={tp2Done ? <CheckCircle2 className="h-3 w-3" /> : <Target className="h-3 w-3" />}
          highlight={tp2Done}
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
            <Metric label="Confidence" value={`${signal.confidence}%`} tone="violet" />
            <Metric label="Size" value={`${signal.position_size_multiplier.toFixed(2)}x`} />
        {isOpen ? (
          <>
            <Metric label="Backend Price" value={livePrice !== null ? formatPrice(livePrice) : "Waiting"} tone="blue" />
            <Metric label="Live PnL" value={livePnl === null ? "--" : formatPercent(livePnl)} tone={livePnl !== null && livePnl < 0 ? "rose" : "emerald"} />
          </>
        ) : (
          <>
            <Metric label="Closed" value={formatDateTime(signal.closed_at)} />
            <Metric label="PnL" value={formatPercent(signal.pnl_pct)} tone={isWin ? "emerald" : "rose"} />
          </>
        )}
      </div>

      <div className="flex flex-col justify-between gap-3 lg:text-right">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Result</p>
          <p className={`mt-1 text-lg font-bold ${signal.pnl_pct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
            {isOpen ? outcome.label : formatPercent(signal.pnl_pct)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{outcome.detail}</p>
        </div>
        <div className="text-xs text-muted-foreground">
          <p>Max profit {formatPercent(signal.max_profit_pct)}</p>
          <p>Max DD {formatPercent(signal.max_drawdown_pct)}</p>
          {signal.close_reason ? <p>{signal.close_reason}</p> : null}
        </div>
      </div>
    </Link>
  );
}

function Metric({
  label,
  value,
  tone = "slate",
  icon,
  highlight = false,
}: {
  label: string;
  value: string;
  tone?: "slate" | "blue" | "emerald" | "rose" | "violet";
  icon?: ReactNode;
  highlight?: boolean;
}) {
  const toneMap: Record<string, string> = {
    slate: "text-foreground",
    blue: "text-blue-300",
    emerald: "text-emerald-300",
    rose: "text-rose-300",
    violet: "text-violet-300",
  };

  return (
    <div
      className={`min-w-0 rounded-lg px-3 py-2 ${
        highlight ? "bg-white/[0.07] ring-1 ring-white/15" : "bg-white/[0.03]"
      }`}
    >
      <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className={`mt-1 truncate text-sm font-semibold tabular-nums ${toneMap[tone]}`}>{value}</p>
    </div>
  );
}

function OutcomeBadge({
  label,
  detail,
  tone,
  icon,
}: {
  label: string;
  detail: string;
  tone: OutcomeTone;
  icon: ReactNode;
}) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold ${outcomeToneClasses[tone]}`}>
      {icon}
      <span>{label}</span>
      <span className="font-medium opacity-70">{detail}</span>
    </span>
  );
}
