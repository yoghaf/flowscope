"use client";

interface Assets {
  wallet_balance: number;
  available_balance: number;
  unrealized_pnl: number;
  margin_balance: number;
  initial_margin: number;
  maintenance_margin: number;
  withdrawable_balance?: number;
}

interface AssetsPanelProps {
  assets?: Partial<Assets> | null;
  isLoading: boolean;
}

export default function AssetsPanel({ assets, isLoading }: AssetsPanelProps) {
  if (isLoading) {
    return (
      <div className="flex h-[300px] items-center justify-center text-slate-400">
        Loading assets...
      </div>
    );
  }

  if (!assets || assets.wallet_balance === undefined) {
    return (
      <div className="flex h-[300px] flex-col items-center justify-center text-center">
        <div className="mb-2 text-4xl">💰</div>
        <p className="text-lg font-medium text-foreground">No Assets Data</p>
        <p className="text-sm text-muted-foreground">
          Account assets will appear here when session is running
        </p>
      </div>
    );
  }

  const marginRatio =
    (assets.margin_balance ?? 0) > 0
      ? ((assets.maintenance_margin ?? 0) / (assets.margin_balance ?? 1)) * 100
      : 0;

  const assetItems = [
    {
      label: "USDT Cross Margin",
      sublabel: "Wallet Balance",
      value: assets.wallet_balance ?? 0,
      color: "text-slate-100",
      large: true,
    },
    {
      label: "Available Balance",
      value: assets.available_balance ?? 0,
      color: "text-green-400",
    },
    {
      label: "Unrealized PnL",
      value: assets.unrealized_pnl ?? 0,
      color:
        (assets.unrealized_pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400",
    },
    {
      label: "Margin Balance",
      value: assets.margin_balance ?? 0,
      color: "text-slate-100",
    },
    {
      label: "Initial Margin",
      value: assets.initial_margin ?? 0,
      color: "text-orange-400",
    },
    {
      label: "Maintenance Margin",
      value: assets.maintenance_margin ?? 0,
      color: "text-orange-400",
    },
    {
      label: "Margin Ratio",
      value: marginRatio,
      color:
        marginRatio < 50
          ? "text-green-400"
          : marginRatio < 80
            ? "text-yellow-400"
            : "text-red-400",
      suffix: "%",
    },
    {
      label: "Withdrawable Balance",
      value: assets.withdrawable_balance ?? 0,
      color: "text-blue-400",
    },
  ];

  return (
    <div className="p-4">
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {assetItems.map((item) => (
          <div
            key={item.label}
            className={`rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 ${
              (item as any).large
                ? "md:col-span-2 lg:col-span-2"
                : ""
            }`}
          >
            <div className="text-[11px] text-slate-500 uppercase tracking-wider">
              {item.label}
            </div>
            {(item as any).sublabel && (
              <div className="text-[10px] text-slate-600 mt-0.5">
                {(item as any).sublabel}
              </div>
            )}
            <div
              className={`mt-1.5 font-semibold font-mono ${item.color} ${
                (item as any).large ? "text-2xl" : "text-lg"
              }`}
            >
              {(item as any).suffix === "%"
                ? `${item.value.toFixed(2)}%`
                : `${item.value.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })} USDT`}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
