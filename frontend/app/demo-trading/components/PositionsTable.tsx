"use client";

import type { DemoPosition } from "@/lib/types";

interface PositionsTableProps {
  positions: DemoPosition[];
  isLoading: boolean;
  onClosePosition: (symbol: string) => void;
  onReversePosition: (symbol: string) => void;
  onCloseAll?: () => void;
  protection?: Array<Record<string, any>>;
}

/** Extract base coin from a USDT pair, e.g. "ETCUSDT" → "ETC" */
function baseCoin(symbol: string) {
  return symbol.replace(/USDT$/i, "");
}

/** Format a number with smart decimal places */
function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null || n === 0) return "—";
  // For very small numbers use more decimals
  if (Math.abs(n) < 0.01) return n.toFixed(8);
  if (Math.abs(n) < 1) return n.toFixed(6);
  return n.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Normalize side: backend sends LONG/SHORT, we display Long/Short */
function normSide(side: string): "Long" | "Short" {
  return side.toUpperCase() === "LONG" ? "Long" : "Short";
}

export default function PositionsTable({
  positions,
  isLoading,
  onClosePosition,
  onReversePosition,
  onCloseAll,
  protection = [],
}: PositionsTableProps) {
  if (isLoading) {
    return (
      <div className="flex h-[300px] items-center justify-center text-slate-400">
        Loading positions...
      </div>
    );
  }

  if (!positions || positions.length === 0) {
    return (
      <div className="flex h-[300px] flex-col items-center justify-center text-center">
        <div className="mb-2 text-4xl">📊</div>
        <p className="text-lg font-medium text-foreground">No Open Positions</p>
        <p className="text-sm text-muted-foreground">
          Open positions will appear here when trades are executed
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-white/10 text-left text-[11px] text-slate-500">
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Symbol</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Size</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Entry Price</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Break Even Price</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Mark Price</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Liq. Price</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Margin Ratio</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Margin</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">PNL(ROE %)</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium text-right">
              {positions.length > 1 && onCloseAll ? (
                <button
                  onClick={onCloseAll}
                  className="text-yellow-400 hover:text-yellow-300 font-medium"
                >
                  Close All Positions
                </button>
              ) : (
                "Actions"
              )}
            </th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos, index) => {
            const protectionMeta = protection.find(
              (item) => String(item.symbol || "").toUpperCase() === pos.symbol.toUpperCase(),
            );
            const protectionLabel = protectionMeta?.tp1_hit
              ? "SL BE"
              : protectionMeta?.sl_order_id
                ? "Protected"
                : protectionMeta
                  ? "Unprotected"
                  : "Manual";
            const protectionClass = protectionMeta?.tp1_hit
              ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
              : protectionMeta?.sl_order_id
                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                : protectionMeta
                  ? "border-red-500/20 bg-red-500/10 text-red-300"
                  : "border-white/10 bg-white/5 text-slate-400";
            const side = normSide(pos.side);
            const isLong = side === "Long";
            const sideColor = isLong ? "text-green-400" : "text-red-400";
            const pnl = pos.unrealized_pnl ?? 0;
            const roe = pos.roe ?? 0;
            const pnlColor =
              pnl > 0
                ? "text-green-400"
                : pnl < 0
                  ? "text-red-400"
                  : "text-slate-400";

            const coin = baseCoin(pos.symbol);
            const leverage = pos.leverage ?? 20;
            const marginType = (pos.margin_type ?? "CROSS").toUpperCase();
            const marginLabel = marginType === "CROSS" ? "Cross" : "Isolated";

            return (
              <tr
                key={pos.id || `${pos.symbol}-${index}`}
                className="border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors"
              >
                {/* Symbol + Perp Leverage */}
                <td className="px-3 py-2.5">
                  <div className="flex flex-col">
                    <span className="font-medium text-slate-100 text-[13px]">
                      {pos.symbol}
                    </span>
                    <span className="text-[10px] text-slate-500 mt-0.5">
                      Perp{" "}
                      <span className={`${sideColor} font-medium`}>
                        {leverage}x
                      </span>
                    </span>
                    <span className={`mt-1 inline-flex w-fit rounded border px-1.5 py-0.5 text-[10px] font-semibold ${protectionClass}`}>
                      {protectionLabel}
                    </span>
                  </div>
                </td>

                {/* Size + Coin name */}
                <td className="px-3 py-2.5">
                  <div className="flex flex-col">
                    <span className={`font-medium ${sideColor}`}>
                      {pos.size.toLocaleString(undefined, {
                        minimumFractionDigits: 1,
                      })}{" "}
                      <span className="text-slate-400 font-normal">{coin}</span>
                    </span>
                  </div>
                </td>

                {/* Entry Price */}
                <td className="px-3 py-2.5 text-slate-300 font-mono">
                  {fmt(pos.entry_price)}
                </td>

                {/* Break Even Price */}
                <td className="px-3 py-2.5 text-slate-300 font-mono">
                  {fmt((pos as any).break_even_price)}
                </td>

                {/* Mark Price */}
                <td className="px-3 py-2.5 text-slate-300 font-mono">
                  {fmt(pos.mark_price ?? pos.current_price)}
                </td>

                {/* Liquidation Price */}
                <td className="px-3 py-2.5 text-slate-300 font-mono">
                  {(pos.liquidation_price ?? 0) > 0
                    ? fmt(pos.liquidation_price)
                    : "—"}
                </td>

                {/* Margin Ratio */}
                <td className="px-3 py-2.5 text-slate-300">
                  {((pos as any).margin_ratio ?? 0).toFixed(2)}%
                </td>

                {/* Margin + Cross/Isolated */}
                <td className="px-3 py-2.5">
                  <div className="flex flex-col">
                    <span className="text-slate-200 font-medium">
                      {fmt(pos.isolated_margin ?? 0)} USDT
                    </span>
                    <span className="text-[10px] text-slate-500 mt-0.5">
                      ({marginLabel})
                    </span>
                  </div>
                </td>

                {/* PNL (ROE %) - Combined like Binance */}
                <td className="px-3 py-2.5">
                  <div className="flex flex-col">
                    <span className={`font-medium ${pnlColor}`}>
                      {pnl >= 0 ? "+" : ""}
                      {fmt(pnl)} USDT
                    </span>
                    <span className={`text-[10px] mt-0.5 ${pnlColor}`}>
                      {roe >= 0 ? "+" : ""}
                      {roe.toFixed(2)}%
                    </span>
                  </div>
                </td>

                {/* Actions: Market Close / Reverse */}
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1.5 justify-end">
                    <button
                      onClick={() => onClosePosition(pos.symbol)}
                      className="rounded px-2.5 py-1 text-[11px] font-medium bg-slate-700/60 text-slate-200 hover:bg-red-500/30 hover:text-red-300 transition-colors"
                    >
                      Market
                    </button>
                    <button
                      onClick={() => onReversePosition(pos.symbol)}
                      className="rounded px-2.5 py-1 text-[11px] font-medium bg-slate-700/60 text-slate-200 hover:bg-blue-500/30 hover:text-blue-300 transition-colors"
                    >
                      Reverse
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
