"use client";

import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowDownToLine, ArrowUpRight, Filter, ShieldCheck, ShieldX } from "lucide-react";

import { api } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/formatters";
import type { PerformanceTradeRow, SetupPerformance } from "@/lib/types";

type TableFilterKey = "symbol" | "timeframe" | "setup_type" | "state" | "bias" | "status" | "result";
type TableFilters = Record<TableFilterKey, string>;
type FilterOption = { value: string; label: string };

const INITIAL_FILTERS: TableFilters = {
  symbol: "",
  timeframe: "",
  setup_type: "",
  state: "",
  bias: "",
  status: "",
  result: "",
};

const FILTER_LABELS: Record<TableFilterKey, string> = {
  symbol: "Symbol",
  timeframe: "TF",
  setup_type: "Setup",
  state: "State",
  bias: "Bias",
  status: "Status",
  result: "Result",
};

const FILTER_KEYS = Object.keys(INITIAL_FILTERS) as TableFilterKey[];
const ALL_TIMEFRAME_OPTIONS = ["15m", "1h", "4h", "24h"];

function formatTradeSample(item: { closed_trades?: number; open_trades?: number; trades: number }) {
  const closedTrades = item.closed_trades ?? item.trades;
  const openTrades = item.open_trades ?? 0;
  return {
    closedTrades,
    openTrades,
    totalTrades: item.trades,
  };
}

function formatRrValue(item: { rr_ratio: number; winrate: number; closed_trades?: number; trades: number }) {
  const closedTrades = item.closed_trades ?? item.trades;
  if (closedTrades === 0) {
    return "--";
  }
  if (item.winrate >= 1 && item.rr_ratio === 0) {
    return "--";
  }
  return item.rr_ratio.toFixed(2);
}

function formatWinrateValue(item: { winrate: number; closed_trades?: number; trades: number }) {
  const closedTrades = item.closed_trades ?? item.trades;
  if (closedTrades === 0) {
    return "--";
  }
  return `${Math.round(item.winrate * 100)}%`;
}

function formatExpectancyValue(item: { expectancy: number; closed_trades?: number; trades: number }) {
  const closedTrades = item.closed_trades ?? item.trades;
  if (closedTrades === 0) {
    return "--";
  }
  return `${item.expectancy.toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(digits);
}

function formatPercent(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(digits)}%`;
}

function formatTimestampCell(value: string | null | undefined) {
  if (!value) {
    return (
      <div className="flex flex-col">
        <span>--</span>
      </div>
    );
  }

  return (
    <div className="flex min-w-[120px] flex-col leading-tight">
      <span>{formatDate(value)}</span>
      <span className="text-xs text-muted-foreground">{formatTime(value)}</span>
    </div>
  );
}

function formatClosedTimestamp(row: PerformanceTradeRow) {
  if (row.result === "open") {
    return (
      <div className="flex min-w-[120px] flex-col leading-tight">
        <span>--</span>
        <span className="text-xs text-muted-foreground">Still open</span>
      </div>
    );
  }
  return formatTimestampCell(row.updated_at);
}

function normalizeFilterValue(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim().toLowerCase();
}

function displayFilterValue(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}

function SetupSummaryCard({
  title,
  icon,
  setup,
  emptyText,
}: {
  title: string;
  icon: ReactNode;
  setup?: SetupPerformance;
  emptyText: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
      <div className="mb-4 flex items-center gap-2">
        {icon}
        <h3 className="font-semibold text-foreground">{title}</h3>
      </div>
      {setup ? (
        <div className="space-y-2 text-sm text-muted-foreground">
          <p className="text-lg font-semibold text-foreground">{setup.setup_type}</p>
          <p>Closed trades: {formatTradeSample(setup).closedTrades}</p>
          <p>Open trades: {formatTradeSample(setup).openTrades}</p>
          <p>Wins / Losses: {setup.wins ?? 0} / {setup.losses ?? 0}</p>
          <p>Breakevens: {setup.breakevens ?? 0}</p>
          <p>Winrate: {formatWinrateValue(setup)}</p>
          <p>Expectancy: {formatExpectancyValue(setup)}</p>
        </div>
      ) : (
        <p className="text-muted-foreground">{emptyText}</p>
      )}
    </div>
  );
}

export default function PerformancePage() {
  const [capitalPerTrade, setCapitalPerTrade] = useState("100");
  const [isDownloading, setIsDownloading] = useState(false);
  const [tableFilters, setTableFilters] = useState<TableFilters>(INITIAL_FILTERS);

  const parsedCapital = useMemo(() => {
    const value = Number(capitalPerTrade);
    return Number.isFinite(value) && value > 0 ? value : 100;
  }, [capitalPerTrade]);

  const { data, isLoading } = useQuery({
    queryKey: ["performance", "1h"],
    queryFn: () => api.getPerformance({ symbol: "ALL", timeframe: "1h", snapshotId: "latest" }),
    staleTime: 60_000,
  });

  const { data: tableData, isLoading: isTableLoading } = useQuery({
    queryKey: ["performance-report-data", parsedCapital],
    queryFn: () =>
      api.getPerformanceReportData({
        symbol: "ALL",
        timeframe: "ALL",
        capitalPerTrade: parsedCapital,
      }),
    staleTime: 60_000,
  });

  const filterOptions = useMemo(() => {
    const rows = tableData?.rows ?? [];
    return FILTER_KEYS.reduce<Record<TableFilterKey, FilterOption[]>>(
      (acc, key) => {
        if (key === "timeframe") {
          acc[key] = ALL_TIMEFRAME_OPTIONS.map((option) => ({ value: option.toLowerCase(), label: option }));
          return acc;
        }
        const seen = new Map<string, string>();
        rows.forEach((row) => {
          const normalized = normalizeFilterValue(row[key]);
          const label = displayFilterValue(row[key]);
          if (!normalized || !label || seen.has(normalized)) {
            return;
          }
          seen.set(normalized, label);
        });
        acc[key] = Array.from(seen.entries())
          .map(([value, label]) => ({ value, label }))
          .sort((a, b) => a.label.localeCompare(b.label));
        return acc;
      },
      {
        symbol: [],
        timeframe: [],
        setup_type: [],
        state: [],
        bias: [],
        status: [],
        result: [],
      },
    );
  }, [tableData?.rows]);

  const filteredRows = useMemo(() => {
    const rows = tableData?.rows ?? [];
    return rows.filter((row) =>
      FILTER_KEYS.every((key) => {
        const selected = tableFilters[key];
        if (!selected) {
          return true;
        }
        return normalizeFilterValue(row[key]) === selected;
      }),
    );
  }, [tableData?.rows, tableFilters]);

  const bestSetup = data?.setups.find((item) => item.setup_type === data.best_setup);
  const worstSetup = data?.setups.find((item) => item.setup_type === data.worst_setup);

  async function handleDownloadReport(format: "html" | "csv") {
    try {
      setIsDownloading(true);
      const blob = await api.downloadPerformanceReport({
        symbol: "ALL",
        timeframe: "ALL",
        capitalPerTrade: parsedCapital,
        format,
      });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `flowscope-performance-report-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setIsDownloading(false);
    }
  }

  function updateFilter(key: TableFilterKey, value: string) {
    setTableFilters((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function resetFilters() {
    setTableFilters(INITIAL_FILTERS);
  }

  if (isLoading || !data) {
    return (
      <div className="rounded-2xl border border-white/10 bg-card/50 p-10 text-muted-foreground">
        Loading performance...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-2 text-4xl font-bold tracking-tight text-foreground">Performance</h1>
        <p className="text-lg text-muted-foreground">How FlowScope setups are performing over time</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Winrate and expectancy only use closed `win/loss` trades. Open trades and breakevens are shown separately.
        </p>
      </div>

      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-foreground">Download Performance Report</h2>
            <p className="text-sm text-muted-foreground">
              Export every token position with RR, planned target profile, assumed modal per trade, quantity, and realized USD PnL.
            </p>
            <p className="text-xs text-muted-foreground">
              Download `HTML Table` kalau ingin laporan yang langsung rapi dibaca. Download `CSV` kalau ingin olah data lebih lanjut di Excel atau Google Sheets.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex flex-col gap-2 text-sm text-muted-foreground">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Modal / Trade (USDT)</span>
              <input
                type="number"
                min="1"
                step="1"
                value={capitalPerTrade}
                onChange={(event) => setCapitalPerTrade(event.target.value)}
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary/40 focus:bg-white/10 sm:w-48"
              />
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={() => handleDownloadReport("html")}
                disabled={isDownloading}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm font-semibold text-primary transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <ArrowDownToLine className="h-4 w-4" />
                {isDownloading ? "Preparing..." : "Download HTML Table"}
              </button>
              <button
                type="button"
                onClick={() => handleDownloadReport("csv")}
                disabled={isDownloading}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-semibold text-foreground transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <ArrowDownToLine className="h-4 w-4" />
                {isDownloading ? "Preparing..." : "Download CSV"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Closed Trades</p>
          <p className="text-3xl font-bold text-foreground">{data.total_trades}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Winrate</p>
          <p className="text-3xl font-bold text-emerald-400">{Math.round(data.winrate * 100)}%</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Expectancy</p>
          <p className={`text-3xl font-bold ${data.expectancy >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {data.expectancy.toFixed(2)}%
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Best Setup</p>
          <p className="text-3xl font-bold text-foreground">{data.best_setup ?? "--"}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SetupSummaryCard
          title="Best Setup"
          icon={<ArrowUpRight className="h-5 w-5 text-emerald-400" />}
          setup={bestSetup}
          emptyText="No closed setup data yet."
        />
        <SetupSummaryCard
          title="Worst Setup"
          icon={<ShieldX className="h-5 w-5 text-red-400" />}
          setup={worstSetup}
          emptyText="Need at least two distinct setups with closed trades."
        />
      </div>

      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
        <div className="mb-4 flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <h3 className="font-semibold text-foreground">Setup Breakdown</h3>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.setups.map((setup) => (
            <div key={setup.setup_type} className="rounded-xl border border-white/10 bg-white/5 p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">{setup.setup_type}</p>
                {setup.validated ? (
                  <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                    <ShieldCheck className="h-3 w-3" /> Validated
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
                    Experimental
                  </span>
                )}
              </div>
              <div className="space-y-1 text-xs text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>Closed</span>
                  <span className="text-foreground">{formatTradeSample(setup).closedTrades}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Open</span>
                  <span className="text-foreground">{formatTradeSample(setup).openTrades}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Winrate</span>
                  <span className="text-foreground">{formatWinrateValue(setup)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Expectancy</span>
                  <span className={setup.expectancy >= 0 ? "text-emerald-300" : "text-red-300"}>
                    {formatExpectancyValue(setup)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Wins / Losses</span>
                  <span className="text-foreground">{setup.wins ?? 0} / {setup.losses ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Breakevens</span>
                  <span className="text-foreground">{setup.breakevens ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>RR</span>
                  <span className="text-foreground">{formatRrValue(setup)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {data.regimes && data.regimes.length > 0 ? (
        <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
          <div className="mb-4 flex items-center gap-2">
            <Activity className="h-5 w-5 text-amber-400" />
            <h3 className="font-semibold text-foreground">Regime Split</h3>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data.regimes.map((regime) => (
              <div key={regime.regime} className="rounded-xl border border-white/10 bg-white/5 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold text-foreground">{regime.regime}</p>
                  {regime.validated ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                      <ShieldCheck className="h-3 w-3" /> Validated
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
                      Experimental
                    </span>
                  )}
                </div>
                <div className="space-y-1 text-xs text-muted-foreground">
                  <div className="flex items-center justify-between">
                    <span>Trades</span>
                    <span className="text-foreground">{regime.trades}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Winrate</span>
                    <span className="text-foreground">{formatWinrateValue(regime)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Expectancy</span>
                    <span className={regime.expectancy >= 0 ? "text-emerald-300" : "text-red-300"}>
                      {formatExpectancyValue(regime)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Wins / Losses</span>
                    <span className="text-foreground">{regime.wins ?? 0} / {regime.losses ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Breakevens</span>
                    <span className="text-foreground">{regime.breakevens ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>RR</span>
                    <span className="text-foreground">{formatRrValue(regime)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-primary" />
            <div>
              <h3 className="font-semibold text-foreground">Performance Trade Table</h3>
              <p className="text-sm text-muted-foreground">Filter posisi berdasarkan kolom utama supaya audit performa per token lebih mudah dibaca.</p>
            </div>
          </div>
          <div className="text-sm text-muted-foreground">
            {filteredRows.length} / {tableData?.total_rows ?? 0} rows visible
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
          {FILTER_KEYS.map((key) => (
            <label key={key} className="flex flex-col gap-2 text-sm text-muted-foreground">
              <span className="text-xs font-semibold uppercase tracking-wider">{FILTER_LABELS[key]}</span>
              <select
                value={tableFilters[key]}
                onChange={(event) => updateFilter(key, event.target.value)}
                className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary/40 focus:bg-white/10"
              >
                <option value="">All</option>
                {filterOptions[key].map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-foreground transition hover:bg-white/10"
          >
            Reset Filters
          </button>
        </div>

        <div className="mt-6 overflow-x-auto rounded-2xl border border-white/10">
          {isTableLoading ? (
            <div className="p-6 text-sm text-muted-foreground">Loading trade table...</div>
          ) : (
            <table className="min-w-[2400px] w-full border-collapse">
              <thead className="bg-primary/10">
                <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3">Symbol</th>
                  <th className="px-4 py-3">TF</th>
                  <th className="px-4 py-3">Setup</th>
                  <th className="px-4 py-3">State</th>
                  <th className="px-4 py-3">Bias</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Result</th>
                  <th className="px-4 py-3">Signal Time</th>
                  <th className="px-4 py-3">Opened</th>
                  <th className="px-4 py-3">Closed / Updated</th>
                  <th className="px-4 py-3">Entry</th>
                  <th className="px-4 py-3">Stop</th>
                  <th className="px-4 py-3">TP1</th>
                  <th className="px-4 py-3">TP2</th>
                  <th className="px-4 py-3">RR TP1</th>
                  <th className="px-4 py-3">RR TP2</th>
                  <th className="px-4 py-3">Conf %</th>
                  <th className="px-4 py-3">Quality</th>
                  <th className="px-4 py-3">Risk</th>
                  <th className="px-4 py-3">Regime</th>
                  <th className="px-4 py-3">Vol</th>
                  <th className="px-4 py-3">Modal</th>
                  <th className="px-4 py-3">Qty</th>
                  <th className="px-4 py-3">Risk $</th>
                  <th className="px-4 py-3">Realized $</th>
                  <th className="px-4 py-3">R-Multiple</th>
                  <th className="px-4 py-3">PnL %</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.length === 0 ? (
                  <tr>
                    <td colSpan={27} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      Tidak ada trade yang cocok dengan filter aktif.
                    </td>
                  </tr>
                ) : (
                  filteredRows.map((row: PerformanceTradeRow) => (
                    <tr key={`${row.trade_id}-${row.created_at}`} className="border-t border-white/5 text-sm text-foreground">
                      <td className="px-4 py-3 font-semibold">{row.symbol}</td>
                      <td className="px-4 py-3">{row.timeframe}</td>
                      <td className="px-4 py-3">{row.setup_type}</td>
                      <td className="px-4 py-3">{row.state}</td>
                      <td className="px-4 py-3">{row.bias}</td>
                      <td className="px-4 py-3">{row.status}</td>
                      <td className="px-4 py-3">{row.result}</td>
                      <td className="px-4 py-3">{formatTimestampCell(row.signal_timestamp)}</td>
                      <td className="px-4 py-3">{formatTimestampCell(row.created_at)}</td>
                      <td className="px-4 py-3">{formatClosedTimestamp(row)}</td>
                      <td className="px-4 py-3">{formatNumber(row.entry_price, 4)}</td>
                      <td className="px-4 py-3">{formatNumber(row.invalidation_price, 4)}</td>
                      <td className="px-4 py-3">{formatNumber(row.target_price_1, 4)}</td>
                      <td className="px-4 py-3">{formatNumber(row.target_price_2, 4)}</td>
                      <td className="px-4 py-3">{formatNumber(row.planned_rr_tp1, 2)}</td>
                      <td className="px-4 py-3">{formatNumber(row.planned_rr_tp2, 2)}</td>
                      <td className="px-4 py-3">{formatPercent(row.confidence_pct, 2)}</td>
                      <td className="px-4 py-3">{row.quality_score ?? "--"}</td>
                      <td className="px-4 py-3">{row.risk_level ?? "--"}</td>
                      <td className="px-4 py-3">{row.market_regime}</td>
                      <td className="px-4 py-3">{row.volatility_regime}</td>
                      <td className="px-4 py-3">{formatNumber(row.capital_per_trade, 4)}</td>
                      <td className="px-4 py-3">{formatNumber(row.estimated_quantity, 6)}</td>
                      <td className="px-4 py-3">{formatNumber(row.risk_amount_usd, 4)}</td>
                      <td className="px-4 py-3">{formatNumber(row.realized_pnl_usd, 4)}</td>
                      <td className="px-4 py-3">{formatNumber(row.realized_r_multiple, 2)}</td>
                      <td className="px-4 py-3">{formatPercent(row.pnl_pct, 2)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
