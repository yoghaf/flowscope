"use client";

interface OpenOrder {
  orderId: number;
  symbol: string;
  side: string;
  type: string;
  price: number;
  origQty?: number;
  qty?: number;
  executedQty: number;
  status: string;
  timeInForce?: string;
  time?: number;
  createTime?: number;
}

interface OpenOrdersTableProps {
  orders: OpenOrder[];
  isLoading: boolean;
  onCancelOrder: (symbol: string, orderId: number) => void;
}

function baseCoin(symbol: string) {
  return symbol.replace(/USDT$/i, "");
}

export default function OpenOrdersTable({
  orders,
  isLoading,
  onCancelOrder,
}: OpenOrdersTableProps) {
  if (isLoading) {
    return (
      <div className="flex h-[300px] items-center justify-center text-muted-foreground">
        Loading open orders...
      </div>
    );
  }

  if (!orders || orders.length === 0) {
    return (
      <div className="flex h-[300px] flex-col items-center justify-center text-center">
        <div className="mb-2 text-4xl">📋</div>
        <p className="text-lg font-medium text-foreground">No Open Orders</p>
        <p className="text-sm text-muted-foreground">
          Open orders will appear here when placed
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-white/10 text-left text-[11px] text-slate-500">
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Time</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Symbol</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Type</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Side</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Price</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Amount</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Filled</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Status</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => {
            const isBuy = order.side === "BUY";
            const orderQty = order.origQty ?? order.qty ?? 0;
            const orderTime = order.time ?? order.createTime ?? 0;
            const fillPct =
              orderQty > 0
                ? ((order.executedQty / orderQty) * 100).toFixed(0)
                : "0";

            return (
              <tr
                key={order.orderId}
                className="border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors"
              >
                {/* Time */}
                <td className="px-3 py-2.5 text-slate-400 whitespace-nowrap">
                  {orderTime
                    ? new Date(orderTime).toLocaleString(undefined, {
                        month: "short",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "—"}
                </td>

                {/* Symbol */}
                <td className="px-3 py-2.5 font-medium text-slate-100">
                  {order.symbol}
                </td>

                {/* Type */}
                <td className="px-3 py-2.5 text-slate-400">{order.type}</td>

                {/* Side */}
                <td
                  className={`px-3 py-2.5 font-medium ${
                    isBuy ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {order.side}
                </td>

                {/* Price */}
                <td className="px-3 py-2.5 text-slate-300 font-mono">
                  {order.price > 0
                    ? order.price.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                      })
                    : "Market"}
                </td>

                {/* Amount */}
                <td className="px-3 py-2.5 text-slate-300 font-mono">
                  {orderQty.toLocaleString(undefined, {
                    minimumFractionDigits: 1,
                  })}{" "}
                  <span className="text-slate-500">
                    {baseCoin(order.symbol)}
                  </span>
                </td>

                {/* Filled */}
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-300 font-mono">
                      {order.executedQty.toLocaleString(undefined, {
                        minimumFractionDigits: 1,
                      })}
                    </span>
                    <span className="text-slate-500 text-[10px]">
                      ({fillPct}%)
                    </span>
                  </div>
                </td>

                {/* Status */}
                <td className="px-3 py-2.5">
                  <span className="inline-block rounded px-2 py-0.5 text-[10px] font-medium text-blue-400 bg-blue-500/10">
                    {order.status}
                  </span>
                </td>

                {/* Action */}
                <td className="px-3 py-2.5 text-right">
                  <button
                    onClick={() => onCancelOrder(order.symbol, order.orderId)}
                    className="rounded px-2.5 py-1 text-[11px] font-medium bg-slate-700/60 text-slate-200 hover:bg-orange-500/30 hover:text-orange-300 transition-colors"
                  >
                    Cancel
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
