"use client";

interface Trade {
  id: number;
  orderId: number;
  symbol: string;
  side: string;
  price: number;
  qty: number;
  realizedPnl: number;
  commission: number;
  commissionAsset: string;
  time: number;
  isMaker?: boolean;
}

interface TradeHistoryTableProps {
  trades: Trade[];
  isLoading: boolean;
}

function baseCoin(symbol: string) {
  return symbol.replace(/USDT$/i, "");
}

export default function TradeHistoryTable({
  trades,
  isLoading,
}: TradeHistoryTableProps) {
  if (isLoading) {
    return (
      <div className="flex h-[300px] items-center justify-center text-slate-400">
        Loading trade history...
      </div>
    );
  }

  if (!trades || trades.length === 0) {
    return (
      <div className="flex h-[300px] flex-col items-center justify-center text-center">
        <div className="mb-2 text-4xl">📊</div>
        <p className="text-lg font-medium text-foreground">No Trade History</p>
        <p className="text-sm text-muted-foreground">
          Executed trades will appear here after orders are filled
        </p>
      </div>
    );
  }

  // Calculate total realized PnL
  const totalPnl = trades.reduce((sum, t) => sum + (t.realizedPnl ?? 0), 0);
  const totalCommission = trades.reduce(
    (sum, t) => sum + (t.commission ?? 0),
    0
  );

  return (
    <div>
      {/* Summary bar */}
      <div className="mb-3 flex items-center gap-6 px-3 text-xs">
        <span className="text-slate-500">
          Total Trades:{" "}
          <span className="text-slate-200 font-medium">{trades.length}</span>
        </span>
        <span className="text-slate-500">
          Realized PnL:{" "}
          <span
            className={`font-medium ${
              totalPnl >= 0 ? "text-green-400" : "text-red-400"
            }`}
          >
            {totalPnl >= 0 ? "+" : ""}
            {totalPnl.toFixed(4)} USDT
          </span>
        </span>
        <span className="text-slate-500">
          Commission:{" "}
          <span className="text-orange-400 font-medium">
            {totalCommission.toFixed(4)} USDT
          </span>
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/10 text-left text-[11px] text-slate-500">
              <th className="whitespace-nowrap px-3 py-2.5 font-medium">
                Time
              </th>
              <th className="whitespace-nowrap px-3 py-2.5 font-medium">
                Symbol
              </th>
              <th className="whitespace-nowrap px-3 py-2.5 font-medium">
                Side
              </th>
              <th className="whitespace-nowrap px-3 py-2.5 font-medium">
                Price
              </th>
              <th className="whitespace-nowrap px-3 py-2.5 font-medium">
                Qty
              </th>
              <th className="whitespace-nowrap px-3 py-2.5 font-medium">
                Realized PnL
              </th>
              <th className="whitespace-nowrap px-3 py-2.5 font-medium">
                Commission
              </th>
              <th className="whitespace-nowrap px-3 py-2.5 font-medium">
                Role
              </th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade) => {
              const isBuy = trade.side === "BUY";
              const pnl = trade.realizedPnl ?? 0;
              const pnlColor =
                pnl > 0
                  ? "text-green-400"
                  : pnl < 0
                    ? "text-red-400"
                    : "text-slate-400";

              return (
                <tr
                  key={`${trade.id}-${trade.time}`}
                  className="border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors"
                >
                  {/* Time */}
                  <td className="px-3 py-2.5 text-slate-400 whitespace-nowrap">
                    {trade.time > 0
                      ? new Date(trade.time).toLocaleString(undefined, {
                          month: "short",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })
                      : "—"}
                  </td>

                  {/* Symbol */}
                  <td className="px-3 py-2.5 font-medium text-slate-100">
                    {trade.symbol}
                  </td>

                  {/* Side */}
                  <td
                    className={`px-3 py-2.5 font-medium ${
                      isBuy ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {trade.side}
                  </td>

                  {/* Price */}
                  <td className="px-3 py-2.5 text-slate-300 font-mono">
                    {trade.price > 0
                      ? trade.price.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                        })
                      : "—"}
                  </td>

                  {/* Qty */}
                  <td className="px-3 py-2.5 text-slate-300 font-mono">
                    {trade.qty.toLocaleString(undefined, {
                      minimumFractionDigits: 1,
                    })}{" "}
                    <span className="text-slate-500">
                      {baseCoin(trade.symbol)}
                    </span>
                  </td>

                  {/* Realized PnL */}
                  <td className={`px-3 py-2.5 font-medium font-mono ${pnlColor}`}>
                    {pnl !== 0 ? (
                      <>
                        {pnl > 0 ? "+" : ""}
                        {pnl.toFixed(4)}{" "}
                        <span className="text-slate-500 font-normal">USDT</span>
                      </>
                    ) : (
                      <span className="text-slate-500">0</span>
                    )}
                  </td>

                  {/* Commission */}
                  <td className="px-3 py-2.5 text-slate-400 font-mono">
                    {trade.commission.toFixed(4)}{" "}
                    <span className="text-slate-500">
                      {trade.commissionAsset}
                    </span>
                  </td>

                  {/* Role */}
                  <td className="px-3 py-2.5 text-slate-400">
                    {trade.isMaker ? "Maker" : "Taker"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
