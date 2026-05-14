import Link from "next/link";

import SignalBadge from "@/app/components/SignalBadge";
import {
  formatFundingRate,
  formatPercent,
  formatPrice,
  formatRatio,
  getDqStatus,
  getFallbackFields,
  getOiChange,
  getProvenanceValue,
  getVolumeChange,
  isReliable,
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

function dqTone(status: string): string {
  const normalized = status.toUpperCase();
  if (["FRESH", "ALIGNED", "OK", "RELIABLE"].includes(normalized)) {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";
  }
  if (["PARTIAL", "STALE", "FALLBACK_ONLY", "UNRELIABLE"].includes(normalized)) {
    return "border-amber-500/20 bg-amber-500/10 text-amber-300";
  }
  if (["MISSING", "NO_DATA", "INVALID"].includes(normalized)) {
    return "border-red-500/20 bg-red-500/10 text-red-300";
  }
  return "border-white/10 bg-white/5 text-slate-300";
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
            const dqStatus = getDqStatus(coin, timeframe);
            const fallbackFields = getFallbackFields(coin, timeframe);
            const oiReliable = isReliable(getProvenanceValue(coin, "oi_delta_reliable", timeframe));
            const fundingReliable = isReliable(getProvenanceValue(coin, "funding_reliable", timeframe));

            return (
              <tr key={coin.symbol} className="group border-b border-white/5 transition-colors hover:bg-white/5">
                <td className="px-6 py-4">
                  <Link
                    href={`/coin/${coin.symbol}?timeframe=${coinTimeframe}&snapshot_id=latest`}
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
                  {volumeChange === null ? "--" : Math.abs(volumeChange) >= 10 ? `${volumeChange >= 0 ? "+" : ""}${(volumeChange + 1).toFixed(0)}x` : `${volumeChange >= 0 ? "+" : ""}${(volumeChange * 100).toFixed(1)}%`}
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
                  <div className="flex flex-col items-start gap-1.5">
                    <SignalBadge signal={coin.signal} status={coin.signal_status} dataStatus={coin.data_status} />
                    <div className="flex flex-wrap gap-1.5">
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${dqTone(dqStatus)}`}>
                        DQ {dqStatus}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${dqTone(oiReliable ? "RELIABLE" : "UNRELIABLE")}`}>
                        OI {oiReliable ? "OK" : "UNREL"}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${dqTone(fundingReliable ? "RELIABLE" : "UNRELIABLE")}`}>
                        FUND {fundingReliable ? "OK" : "UNREL"}
                      </span>
                      {fallbackFields.length > 0 ? (
                        <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                          FB {fallbackFields.length}
                        </span>
                      ) : null}
                    </div>
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
