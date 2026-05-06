"use client";

interface Order {
  orderId: number;
  symbol: string;
  side: string;
  type: string;
  status: string;
  price: number;
  qty: number;
  origQty?: number;
  executedQty: number;
  avgPrice?: number;
  timeInForce?: string;
  createTime?: number;
  updateTime?: number;
  time?: number;
}

interface OrderHistoryTableProps {
  orders: Order[];
  isLoading: boolean;
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    FILLED: "text-green-400 bg-green-500/10",
    NEW: "text-blue-400 bg-blue-500/10",
    CANCELED: "text-slate-400 bg-slate-500/10",
    EXPIRED: "text-orange-400 bg-orange-500/10",
    PARTIALLY_FILLED: "text-yellow-400 bg-yellow-500/10",
    REJECTED: "text-red-400 bg-red-500/10",
  };
  return colors[status] ?? "text-slate-400 bg-slate-500/10";
}

export default function OrderHistoryTable({
  orders,
  isLoading,
}: OrderHistoryTableProps) {
  if (isLoading) {
    return (
      <div className="flex h-[300px] items-center justify-center text-muted-foreground">
        Loading order history...
      </div>
    );
  }

  if (!orders || orders.length === 0) {
    return (
      <div className="flex h-[300px] flex-col items-center justify-center text-center">
        <div className="mb-2 text-4xl">📜</div>
        <p className="text-lg font-medium text-foreground">No Order History</p>
        <p className="text-sm text-muted-foreground">
          Order history will appear here after orders are placed
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
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Avg Price</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Qty</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Filled</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => {
            const orderTime = order.createTime || order.time || 0;
            const isBuy = order.side === "BUY";

            return (
              <tr
                key={`${order.orderId}-${orderTime}`}
                className="border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors"
              >
                {/* Time */}
                <td className="px-3 py-2.5 text-slate-400 whitespace-nowrap">
                  {orderTime > 0
                    ? new Date(orderTime).toLocaleString(undefined, {
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
                  {order.price > 0 ? order.price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : "Market"}
                </td>

                {/* Avg Price */}
                <td className="px-3 py-2.5 text-slate-300 font-mono">
                  {(order.avgPrice ?? 0) > 0
                    ? (order.avgPrice ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })
                    : "—"}
                </td>

                {/* Quantity */}
                <td className="px-3 py-2.5 text-slate-300 font-mono">
                  {(order.origQty ?? order.qty ?? 0).toLocaleString(undefined, { minimumFractionDigits: 1 })}
                </td>

                {/* Executed */}
                <td className="px-3 py-2.5 text-slate-300 font-mono">
                  {(order.executedQty ?? 0).toLocaleString(undefined, { minimumFractionDigits: 1 })}
                </td>

                {/* Status */}
                <td className="px-3 py-2.5">
                  <span
                    className={`inline-block rounded px-2 py-0.5 text-[10px] font-medium ${statusBadge(
                      order.status
                    )}`}
                  >
                    {order.status}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
