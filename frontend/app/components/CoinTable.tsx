import Link from "next/link";

import SignalBadge from "@/app/components/SignalBadge";
import {
  formatFundingRate,
  formatPercent,
  formatPrice,
  formatRatio,
  getOiChange,
  getVolumeChange,
  scoreToPercent,
  shortSymbol,
  toNumberOrNull,
} from "@/lib/formatters";
import type { AssetSnapshot, Timeframe } from "@/lib/types";

interface CoinTableProps {
  rows: AssetSnapshot[];
  timeframe: Timeframe;
  variant?: "dashboard" | "scanner";
}

export default function CoinTable({
  rows,
  timeframe,
  variant = "dashboard",
}: CoinTableProps) {
  const isScanner = variant === "scanner";

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-white/10">
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Asset
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Price
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              OI Delta ({timeframe})
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Volume Delta
            </th>
            {isScanner ? (
              <>
                <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Funding
                </th>
                <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  L/S Ratio
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Phase
                </th>
              </>
            ) : null}
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Score
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Signal
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((coin) => {
            const oiChange = getOiChange(coin, timeframe);
            const volumeChange = getVolumeChange(coin, timeframe);
            const score = scoreToPercent(coin.score);
            const fundingRate = toNumberOrNull(coin.funding_rate);
            const coinTimeframe = coin.timeframe ?? timeframe;

            return (
              <tr key={coin.symbol} className="group border-b border-white/5 transition-colors hover:bg-white/5">
                <td className="px-6 py-4">
                  <Link
                    href={`/coin/${coin.symbol}?timeframe=${coinTimeframe}&snapshot_id=${coin.snapshot_id}`}
                    className="flex items-center gap-3"
                  >
                    <div className="relative">
                      <div className="absolute inset-0 rounded-full bg-primary/20 blur-md" />
                      <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-primary/20 to-primary/10 transition-transform group-hover:scale-110">
                        <span className="text-sm font-bold text-primary">{shortSymbol(coin.symbol).charAt(0)}</span>
                      </div>
                    </div>
                    <div>
                      <div className="font-semibold text-foreground transition-colors group-hover:text-primary">
                        {shortSymbol(coin.symbol)}
                      </div>
                      <div className="text-xs text-muted-foreground">{coin.name}</div>
                    </div>
                  </Link>
                </td>
                <td className="px-6 py-4 text-right font-semibold text-foreground">{formatPrice(coin.price)}</td>
                <td className={`px-6 py-4 text-right font-semibold ${oiChange === null ? "text-muted-foreground" : oiChange >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {formatPercent(oiChange)}
                </td>
                <td className={`px-6 py-4 text-right font-semibold ${volumeChange === null ? "text-muted-foreground" : volumeChange >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {formatPercent(volumeChange)}
                </td>
                {isScanner ? (
                  <>
                    <td
                      className={`px-6 py-4 text-right font-semibold ${
                        fundingRate === null
                          ? "text-muted-foreground"
                          : fundingRate >= 0
                            ? "text-emerald-400"
                            : "text-red-400"
                      }`}
                    >
                      {formatFundingRate(fundingRate)}
                    </td>
                    <td className="px-6 py-4 text-right font-medium text-foreground">
                      {formatRatio(coin.long_short_ratio)}
                    </td>
                    <td className="px-6 py-4 text-left">
                      {coin.phase && coin.phase !== "Neutral" ? (
                        <div className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary shadow-sm shadow-primary/10">
                          <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                          {coin.phase}
                        </div>
                      ) : (
                        <span className="text-sm font-medium text-muted-foreground">Neutral</span>
                      )}
                    </td>
                  </>
                ) : null}
                <td className="px-6 py-4 text-right">
                  <div className="flex items-center justify-end gap-3">
                    <div className="h-2 w-20 overflow-hidden rounded-full bg-white/5">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-primary to-primary/60 transition-all duration-500"
                        style={{ width: `${score}%` }}
                      />
                    </div>
                    <span className="w-8 font-semibold text-foreground">{score}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <SignalBadge signal={coin.signal} status={coin.signal_status} dataStatus={coin.data_status} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
