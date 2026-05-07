"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowDownToLine,
  BarChart3,
  DollarSign,
  Filter,
  LineChart,
  Percent,
  RotateCcw,
  Search,
  Settings2,
  ShieldCheck,
  Table2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { api } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/formatters";
import type {
  PerformanceBreakdownItem,
  PerformanceEquityPoint,
  PerformanceTradeRow,
  PerformanceTradeTableResponse,
  Timeframe,
} from "@/lib/types";

type SimulationMode = "fixed_size" | "fixed_risk" | "equity_risk_pct";
type RegimeFilter = "ALL" | "Trending" | "Ranging" | "Balanced";
type ResultFilter = "ALL" | "closed" | "open" | "win" | "loss" | "breakeven" | "timeout";

const TIMEFRAME_OPTIONS: Array<{ value: Timeframe | "ALL"; label: string }> = [
  { value: "ALL", label: "All TF" },
  { value: "15m", label: "15m" },
  { value: "1h", label: "1h" },
  { value: "4h", label: "4h" },
  { value: "24h", label: "24h" },
];

const REGIME_OPTIONS: Array<{ value: RegimeFilter; label: string }> = [
  { value: "ALL", label: "All Regimes" },
  { value: "Trending", label: "Trending" },
  { value: "Ranging", label: "Ranging" },
  { value: "Balanced", label: "Balanced" },
];

const RESULT_OPTIONS: Array<{ value: ResultFilter; label: string }> = [
  { value: "ALL", label: "All Results" },
  { value: "closed", label: "Closed" },
  { value: "open", label: "Open" },
  { value: "win", label: "Win" },
  { value: "loss", label: "Loss" },
  { value: "breakeven", label: "BE" },
  { value: "timeout", label: "Timeout" },
];

const SETUP_OPTIONS = ["ALL", "Continuation", "Trap", "Squeeze", "Breakout", "Accumulation"];

const MODE_OPTIONS: Array<{
  value: SimulationMode;
  label: string;
  icon: typeof DollarSign;
}> = [
  { value: "fixed_risk", label: "Fixed Risk", icon: ShieldCheck },
  { value: "fixed_size", label: "Fixed Size", icon: DollarSign },
  { value: "equity_risk_pct", label: "Equity Risk %", icon: Percent },
];

function parsePositive(value: string, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function parseNonNegative(value: string, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function formatMoney(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function formatSignedMoney(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const formatted = formatMoney(Math.abs(value), digits);
  return `${value >= 0 ? "+" : "-"}${formatted}`;
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(digits);
}

function formatPercentPoint(value: number | null | undefined, digits = 1, signed = false) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${signed && value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

function formatPrice(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  if (Math.abs(value) >= 1) {
    return value.toFixed(4);
  }
  return value.toFixed(8).replace(/0+$/, "").replace(/\.$/, "");
}

function formatProfitFactor(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(2);
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return "--";
  }
  return `${formatDate(value)} ${formatTime(value)}`;
}

function pnlTextClass(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "text-muted-foreground";
  }
  if (value > 0) {
    return "text-emerald-300";
  }
  if (value < 0) {
    return "text-red-300";
  }
  return "text-slate-300";
}

function Panel({
  title,
  icon,
  actions,
  children,
}: {
  title: string;
  icon: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl">
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

function StatCard({
  label,
  value,
  tone = "default",
  sub,
}: {
  label: string;
  value: string | number;
  tone?: "default" | "good" | "bad" | "warn";
  sub?: string;
}) {
  const toneClass =
    tone === "good"
      ? "text-emerald-300"
      : tone === "bad"
        ? "text-red-300"
        : tone === "warn"
          ? "text-amber-300"
          : "text-foreground";

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${toneClass}`}>{value}</p>
      {sub ? <p className="mt-1 text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-2 text-sm text-muted-foreground">
      <span className="text-[11px] font-semibold uppercase tracking-wider">{label}</span>
      {children}
    </label>
  );
}

function NumberInput({
  value,
  onChange,
  min = "0",
  step = "1",
}: {
  value: string;
  onChange: (value: string) => void;
  min?: string;
  step?: string;
}) {
  return (
    <input
      type="number"
      min={min}
      step={step}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm font-semibold text-foreground outline-none transition focus:border-primary/50 focus:bg-white/10"
    />
  );
}

function SelectField({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm font-semibold text-foreground outline-none transition focus:border-primary/50 focus:bg-white/10"
    >
      {children}
    </select>
  );
}

function SegmentButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-semibold transition ${
        active
          ? "border-primary/40 bg-primary/15 text-primary"
          : "border-white/10 bg-white/5 text-muted-foreground hover:border-white/20 hover:bg-white/10 hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function EquityCurve({ points }: { points: PerformanceEquityPoint[] }) {
  const closedPoints = points.filter((point) => point.equity !== null && point.equity !== undefined);
  if (closedPoints.length < 2) {
    return (
      <div className="flex h-[260px] items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-sm text-muted-foreground">
        No closed trade curve yet.
      </div>
    );
  }

  const width = 720;
  const height = 260;
  const padX = 32;
  const padY = 28;
  const values = closedPoints.map((point) => Number(point.equity ?? 0));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const span = Math.max(maxValue - minValue, 1);
  const linePoints = closedPoints
    .map((point, index) => {
      const x = padX + (index / Math.max(closedPoints.length - 1, 1)) * (width - padX * 2);
      const y = height - padY - ((Number(point.equity ?? 0) - minValue) / span) * (height - padY * 2);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const latest = closedPoints[closedPoints.length - 1];
  const first = closedPoints[0];
  const change = Number(latest.equity ?? 0) - Number(first.equity ?? 0);

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-3 flex items-center justify-between gap-3 text-sm">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Equity</p>
          <p className="mt-1 text-xl font-bold text-foreground">{formatMoney(Number(latest.equity ?? 0), 2)}</p>
        </div>
        <p className={`text-sm font-semibold ${pnlTextClass(change)}`}>{formatSignedMoney(change, 2)}</p>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-[220px] w-full overflow-visible">
        {[0.25, 0.5, 0.75].map((ratio) => (
          <line
            key={ratio}
            x1={padX}
            x2={width - padX}
            y1={padY + ratio * (height - padY * 2)}
            y2={padY + ratio * (height - padY * 2)}
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="1"
          />
        ))}
        <polyline points={linePoints} fill="none" stroke="rgb(52, 211, 153)" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
        {closedPoints.map((point, index) => {
          const x = padX + (index / Math.max(closedPoints.length - 1, 1)) * (width - padX * 2);
          const y = height - padY - ((Number(point.equity ?? 0) - minValue) / span) * (height - padY * 2);
          return (
            <circle
              key={`${point.timestamp}-${index}`}
              cx={x}
              cy={y}
              r={index === closedPoints.length - 1 ? 4 : 2.5}
              fill={index === closedPoints.length - 1 ? "rgb(96, 165, 250)" : "rgb(52, 211, 153)"}
            />
          );
        })}
      </svg>
    </div>
  );
}

function BreakdownTable({
  title,
  items,
}: {
  title: string;
  items: PerformanceBreakdownItem[];
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-white/10">
      <div className="border-b border-white/10 bg-white/[0.04] px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[620px] border-collapse text-sm">
          <thead className="bg-white/[0.03] text-left text-[11px] uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Group</th>
              <th className="px-4 py-3 text-right">WR</th>
              <th className="px-4 py-3 text-right">W/L/BE</th>
              <th className="px-4 py-3 text-right">Open</th>
              <th className="px-4 py-3 text-right">Net</th>
              <th className="px-4 py-3 text-right">Exp</th>
              <th className="px-4 py-3 text-right">PF</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                  No breakdown data.
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.key} className="border-t border-white/5">
                  <td className="px-4 py-3 font-semibold text-foreground">{item.key}</td>
                  <td className="px-4 py-3 text-right text-foreground">{formatPercentPoint(item.winrate, 1)}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {item.wins}/{item.losses}/{item.breakevens}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">{item.open_trades}</td>
                  <td className={`px-4 py-3 text-right font-semibold ${pnlTextClass(item.net_pnl_usd)}`}>
                    {formatSignedMoney(item.net_pnl_usd, 2)}
                  </td>
                  <td className={`px-4 py-3 text-right ${pnlTextClass(item.expectancy_usd)}`}>
                    {formatSignedMoney(item.expectancy_usd, 2)}
                  </td>
                  <td className="px-4 py-3 text-right text-foreground">{formatProfitFactor(item.profit_factor)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TradeAuditTable({ rows }: { rows: PerformanceTradeRow[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-white/10">
      <table className="w-full min-w-[1680px] border-collapse text-sm">
        <thead className="bg-primary/10 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="sticky left-0 z-20 min-w-[140px] bg-primary/10 px-4 py-3">Symbol</th>
            <th className="px-4 py-3">TF</th>
            <th className="px-4 py-3">Regime</th>
            <th className="px-4 py-3">Setup</th>
            <th className="px-4 py-3">Result</th>
            <th className="px-4 py-3">Close Reason</th>
            <th className="px-4 py-3 text-right">Entry</th>
            <th className="px-4 py-3 text-right">Stop</th>
            <th className="px-4 py-3 text-right">TP1</th>
            <th className="px-4 py-3 text-right">TP2</th>
            <th className="px-4 py-3 text-right">Notional</th>
            <th className="px-4 py-3 text-right">Risk $</th>
            <th className="px-4 py-3 text-right">Fee</th>
            <th className="px-4 py-3 text-right">PnL $</th>
            <th className="px-4 py-3 text-right">R</th>
            <th className="px-4 py-3 text-right">PnL %</th>
            <th className="px-4 py-3">Opened</th>
            <th className="px-4 py-3">Closed</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={18} className="px-4 py-8 text-center text-muted-foreground">
                No trades match the active filters.
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={`${row.trade_id}-${row.created_at}`} className="border-t border-white/5 transition hover:bg-white/[0.03]">
                <td className="sticky left-0 z-10 bg-card/95 px-4 py-3 font-semibold text-foreground">{row.symbol}</td>
                <td className="px-4 py-3 text-foreground">{row.timeframe}</td>
                <td className="px-4 py-3 text-muted-foreground">{row.market_regime}</td>
                <td className="px-4 py-3 text-muted-foreground">{row.setup_type}</td>
                <td className="px-4 py-3">
                  <span className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-xs font-semibold uppercase text-foreground">
                    {row.result}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{row.close_reason ?? (row.result === "open" ? "Still open" : "--")}</td>
                <td className="px-4 py-3 text-right text-foreground">{formatPrice(row.entry_price)}</td>
                <td className="px-4 py-3 text-right text-red-200">{formatPrice(row.invalidation_price)}</td>
                <td className="px-4 py-3 text-right text-emerald-200">{formatPrice(row.target_price_1)}</td>
                <td className="px-4 py-3 text-right text-emerald-200">{formatPrice(row.target_price_2)}</td>
                <td className="px-4 py-3 text-right text-foreground">{formatMoney(row.capital_per_trade, 2)}</td>
                <td className="px-4 py-3 text-right text-amber-200">{formatMoney(row.risk_amount_usd, 2)}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{formatMoney(row.fee_usd, 2)}</td>
                <td className={`px-4 py-3 text-right font-semibold ${pnlTextClass(row.realized_pnl_usd)}`}>
                  {formatSignedMoney(row.realized_pnl_usd, 2)}
                </td>
                <td className={`px-4 py-3 text-right ${pnlTextClass(row.realized_r_multiple)}`}>
                  {formatNumber(row.realized_r_multiple, 2)}
                </td>
                <td className={`px-4 py-3 text-right ${pnlTextClass(row.pnl_pct)}`}>{formatPercentPoint(row.pnl_pct, 2, true)}</td>
                <td className="px-4 py-3 text-muted-foreground">{formatTimestamp(row.created_at)}</td>
                <td className="px-4 py-3 text-muted-foreground">{formatTimestamp(row.closed_at ?? row.updated_at)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function PerformancePage() {
  const [simulationMode, setSimulationMode] = useState<SimulationMode>("fixed_risk");
  const [startingCapital, setStartingCapital] = useState("1000");
  const [capitalPerTrade, setCapitalPerTrade] = useState("100");
  const [riskPerTrade, setRiskPerTrade] = useState("10");
  const [riskPctPerTrade, setRiskPctPerTrade] = useState("1");
  const [feePct, setFeePct] = useState("0");
  const [usePositionMultiplier, setUsePositionMultiplier] = useState(true);
  const [timeframe, setTimeframe] = useState<Timeframe | "ALL">("ALL");
  const [regime, setRegime] = useState<RegimeFilter>("ALL");
  const [result, setResult] = useState<ResultFilter>("ALL");
  const [setupType, setSetupType] = useState("ALL");
  const [month, setMonth] = useState("");
  const [scope, setScope] = useState<"active" | "all">("active");
  const [strategy, setStrategy] = useState("v2_balanced");
  const [search, setSearch] = useState("");
  const [isDownloading, setIsDownloading] = useState(false);

  const parsedSettings = useMemo(
    () => ({
      startingCapital: parsePositive(startingCapital, 1000),
      capitalPerTrade: parsePositive(capitalPerTrade, 100),
      riskPerTrade: parsePositive(riskPerTrade, 10),
      riskPctPerTrade: parsePositive(riskPctPerTrade, 1),
      feePct: parseNonNegative(feePct, 0),
    }),
    [capitalPerTrade, feePct, riskPctPerTrade, riskPerTrade, startingCapital],
  );

  const reportQuery = useMemo(
    () => ({
      symbol: "ALL",
      timeframe,
      setupType: setupType === "ALL" ? undefined : setupType,
      regime,
      result,
      month: month || undefined,
      search: search.trim() || undefined,
      scope,
      strategy: strategy.trim() || "ALL",
      simulationMode,
      startingCapital: parsedSettings.startingCapital,
      capitalPerTrade: parsedSettings.capitalPerTrade,
      riskPerTrade: parsedSettings.riskPerTrade,
      riskPctPerTrade: parsedSettings.riskPctPerTrade,
      feePct: parsedSettings.feePct,
      usePositionMultiplier,
    }),
    [month, parsedSettings, regime, result, scope, search, setupType, simulationMode, strategy, timeframe, usePositionMultiplier],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["performance-report-data", reportQuery],
    queryFn: () => api.getPerformanceReportData(reportQuery),
    staleTime: 30_000,
  });

  const summary = data ?? emptyReport(reportQuery);
  const activeMode = MODE_OPTIONS.find((option) => option.value === simulationMode) ?? MODE_OPTIONS[0];

  async function handleDownloadReport(format: "html" | "csv") {
    try {
      setIsDownloading(true);
      const blob = await api.downloadPerformanceReport({
        ...reportQuery,
        format,
      });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `flowscope-performance-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setIsDownloading(false);
    }
  }

  function resetFilters() {
    setTimeframe("ALL");
    setRegime("ALL");
    setResult("ALL");
    setSetupType("ALL");
    setMonth("");
    setScope("active");
    setStrategy("v2_balanced");
    setSearch("");
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Performance Lab</h1>
          <p className="mt-1 text-sm text-muted-foreground">Simulation, filters, and trade audit in one place.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => handleDownloadReport("html")}
            disabled={isDownloading}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 text-sm font-semibold text-primary transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <ArrowDownToLine className="h-4 w-4" />
            HTML
          </button>
          <button
            type="button"
            onClick={() => handleDownloadReport("csv")}
            disabled={isDownloading}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 text-sm font-semibold text-foreground transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <ArrowDownToLine className="h-4 w-4" />
            CSV
          </button>
        </div>
      </div>

      <Panel title="Simulation Settings" icon={<Settings2 className="h-5 w-5 text-primary" />}>
        <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr_1fr]">
          <div className="flex flex-wrap gap-2">
            {MODE_OPTIONS.map((option) => {
              const Icon = option.icon;
              return (
                <SegmentButton key={option.value} active={simulationMode === option.value} onClick={() => setSimulationMode(option.value)}>
                  <Icon className="h-4 w-4" />
                  {option.label}
                </SegmentButton>
              );
            })}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:col-span-2">
            <Field label="Starting Capital">
              <NumberInput value={startingCapital} onChange={setStartingCapital} min="1" step="10" />
            </Field>
            <Field label={simulationMode === "fixed_size" ? "Capital / Trade" : "Risk / Trade"}>
              {simulationMode === "equity_risk_pct" ? (
                <NumberInput value={riskPctPerTrade} onChange={setRiskPctPerTrade} min="0.1" step="0.1" />
              ) : simulationMode === "fixed_size" ? (
                <NumberInput value={capitalPerTrade} onChange={setCapitalPerTrade} min="1" step="10" />
              ) : (
                <NumberInput value={riskPerTrade} onChange={setRiskPerTrade} min="0.1" step="0.1" />
              )}
            </Field>
            <Field label="Fee / Slip %">
              <NumberInput value={feePct} onChange={setFeePct} min="0" step="0.01" />
            </Field>
            <div className="flex flex-col gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Multiplier</span>
              <button
                type="button"
                onClick={() => setUsePositionMultiplier((current) => !current)}
                className={`h-11 rounded-xl border px-3 text-sm font-semibold transition ${
                  usePositionMultiplier
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                    : "border-white/10 bg-white/5 text-muted-foreground hover:bg-white/10"
                }`}
              >
                {usePositionMultiplier ? "Applied" : "Ignored"}
              </button>
            </div>
          </div>
        </div>
      </Panel>

      <Panel
        title="Filters"
        icon={<Filter className="h-5 w-5 text-sky-300" />}
        actions={
          <button
            type="button"
            onClick={resetFilters}
            className="inline-flex h-9 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 text-sm font-semibold text-foreground transition hover:bg-white/10"
          >
            <RotateCcw className="h-4 w-4" />
            Reset
          </button>
        }
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {TIMEFRAME_OPTIONS.map((option) => (
                <SegmentButton key={option.value} active={timeframe === option.value} onClick={() => setTimeframe(option.value)}>
                  {option.label}
                </SegmentButton>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {REGIME_OPTIONS.map((option) => (
                <SegmentButton key={option.value} active={regime === option.value} onClick={() => setRegime(option.value)}>
                  {option.label}
                </SegmentButton>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {RESULT_OPTIONS.map((option) => (
                <SegmentButton key={option.value} active={result === option.value} onClick={() => setResult(option.value)}>
                  {option.label}
                </SegmentButton>
              ))}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Setup">
              <SelectField value={setupType} onChange={setSetupType}>
                {SETUP_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </SelectField>
            </Field>
            <Field label="Scope">
              <SelectField value={scope} onChange={(value) => setScope(value as "active" | "all")}>
                <option value="active">Active</option>
                <option value="all">All History</option>
              </SelectField>
            </Field>
            <Field label="Month">
              <div className="flex gap-2">
                <input
                  type="month"
                  value={month}
                  onChange={(event) => setMonth(event.target.value)}
                  className="h-11 min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 text-sm font-semibold text-foreground outline-none transition focus:border-primary/50 focus:bg-white/10"
                />
                <button
                  type="button"
                  onClick={() => setMonth("")}
                  className="h-11 rounded-xl border border-white/10 bg-white/5 px-3 text-sm font-semibold text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
                >
                  All
                </button>
              </div>
            </Field>
            <Field label="Strategy">
              <input
                value={strategy}
                onChange={(event) => setStrategy(event.target.value)}
                className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm font-semibold text-foreground outline-none transition focus:border-primary/50 focus:bg-white/10"
              />
            </Field>
            <Field label="Search">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Symbol, setup, reason"
                  className="h-11 w-full rounded-xl border border-white/10 bg-white/5 pl-10 pr-3 text-sm font-semibold text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/50 focus:bg-white/10"
                />
              </div>
            </Field>
          </div>
        </div>
      </Panel>

      {isError ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-5 text-sm font-semibold text-red-200">
          Performance report failed to load.
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Trades" value={summary.total_rows} sub={`${summary.closed_trades} closed, ${summary.open_trades} open`} />
        <StatCard label="Winrate" value={formatPercentPoint(summary.winrate, 1)} sub={`${summary.wins}W / ${summary.losses}L`} tone="good" />
        <StatCard
          label="Net PnL"
          value={formatSignedMoney(summary.net_pnl_usd, 2)}
          sub={`${formatPercentPoint(summary.roi_pct, 2, true)} ROI`}
          tone={summary.net_pnl_usd >= 0 ? "good" : "bad"}
        />
        <StatCard
          label="Expectancy"
          value={formatSignedMoney(summary.expectancy_usd, 2)}
          sub={`${formatProfitFactor(summary.profit_factor)} PF`}
          tone={summary.expectancy_usd >= 0 ? "good" : "bad"}
        />
        <StatCard label="Max DD" value={formatSignedMoney(summary.max_drawdown_usd, 2)} sub={formatPercentPoint(summary.max_drawdown_pct, 2, true)} tone="bad" />
        <StatCard label="Avg Win" value={formatSignedMoney(summary.avg_win_usd, 2)} sub="Closed winners" tone="good" />
        <StatCard label="Avg Loss" value={formatSignedMoney(summary.avg_loss_usd, 2)} sub="Closed losers" tone="bad" />
        <StatCard label="Mode" value={activeMode.label} sub={usePositionMultiplier ? "Multiplier on" : "Multiplier off"} tone="warn" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
        <Panel title="Equity Curve" icon={<LineChart className="h-5 w-5 text-emerald-300" />}>
          {isLoading ? (
            <div className="h-[260px] rounded-xl border border-white/10 bg-white/[0.03] p-6 text-sm text-muted-foreground">Loading curve...</div>
          ) : (
            <EquityCurve points={summary.equity_curve} />
          )}
        </Panel>
        <Panel title="Result Mix" icon={<Activity className="h-5 w-5 text-amber-300" />}>
          <div className="grid grid-cols-2 gap-3">
            <StatCard label="Wins" value={summary.wins} tone="good" />
            <StatCard label="Losses" value={summary.losses} tone="bad" />
            <StatCard label="Breakeven" value={summary.breakevens} tone="warn" />
            <StatCard label="Timeout" value={summary.timeouts} />
          </div>
        </Panel>
      </div>

      <Panel title="Performance Breakdown" icon={<BarChart3 className="h-5 w-5 text-fuchsia-300" />}>
        <div className="grid gap-4 xl:grid-cols-3">
          <BreakdownTable title="By Timeframe" items={summary.by_timeframe} />
          <BreakdownTable title="By Regime" items={summary.by_regime} />
          <BreakdownTable title="By Setup" items={summary.by_setup} />
        </div>
      </Panel>

      <Panel title="Close Reason Report" icon={<TrendingDown className="h-5 w-5 text-red-300" />}>
        <BreakdownTable title="Close Reasons" items={summary.by_close_reason} />
      </Panel>

      <Panel
        title="Trade Audit"
        icon={<Table2 className="h-5 w-5 text-primary" />}
        actions={
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {summary.total_rows} rows
            {summary.net_pnl_usd >= 0 ? <TrendingUp className="h-4 w-4 text-emerald-300" /> : <TrendingDown className="h-4 w-4 text-red-300" />}
          </div>
        }
      >
        {isLoading ? (
          <div className="rounded-xl border border-white/10 bg-white/[0.03] p-6 text-sm text-muted-foreground">Loading trade audit...</div>
        ) : (
          <TradeAuditTable rows={summary.rows} />
        )}
      </Panel>
    </div>
  );
}

function emptyReport(query: {
  timeframe: Timeframe | "ALL";
  setupType?: string;
  regime: RegimeFilter;
  result: ResultFilter;
  search?: string;
  month?: string;
  scope: "active" | "all";
  strategy: string;
  simulationMode: SimulationMode;
  startingCapital: number;
  capitalPerTrade: number;
  riskPerTrade: number;
  riskPctPerTrade: number;
  feePct: number;
  usePositionMultiplier: boolean;
}): PerformanceTradeTableResponse {
  return {
    generated_at: new Date().toISOString(),
    symbol: "ALL",
    timeframe: query.timeframe,
    setup_type: query.setupType ?? null,
    regime: query.regime,
    result_filter: query.result,
    month: query.month ?? null,
    search: query.search ?? null,
    scope: query.scope,
    strategy: query.strategy,
    simulation_mode: query.simulationMode,
    starting_capital: query.startingCapital,
    capital_per_trade: query.capitalPerTrade,
    risk_per_trade: query.riskPerTrade,
    risk_pct_per_trade: query.riskPctPerTrade,
    fee_pct: query.feePct,
    use_position_multiplier: query.usePositionMultiplier,
    total_rows: 0,
    closed_trades: 0,
    open_trades: 0,
    wins: 0,
    losses: 0,
    breakevens: 0,
    timeouts: 0,
    winrate: 0,
    net_pnl_usd: 0,
    roi_pct: 0,
    expectancy_usd: 0,
    profit_factor: null,
    max_drawdown_usd: 0,
    max_drawdown_pct: 0,
    avg_win_usd: 0,
    avg_loss_usd: 0,
    avg_r_multiple: null,
    equity_curve: [],
    by_timeframe: [],
    by_regime: [],
    by_setup: [],
    by_close_reason: [],
    rows: [],
  };
}
