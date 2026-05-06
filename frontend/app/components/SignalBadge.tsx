import type { DataStatus, SignalStatus, SignalType } from "@/lib/types";

interface SignalBadgeProps {
  signal: SignalType | string;
  status?: SignalStatus;
  dataStatus?: DataStatus;
  size?: "sm" | "md";
}

export default function SignalBadge({
  signal,
  status = "VALID_SIGNAL",
  dataStatus = "VALID",
  size = "sm",
}: SignalBadgeProps) {
  const label =
    status === "NO_DATA"
      ? dataStatus === "INSUFFICIENT_HISTORY"
        ? "Insufficient Data"
        : "No Data"
      : status === "NO_SIGNAL"
        ? "No Signal"
        : signal;
  const classes = (() => {
    if (status === "NO_DATA") {
      return "border-red-500/20 bg-red-500/10 text-red-300 shadow-red-500/10";
    }
    if (status === "NO_SIGNAL") {
      return "border-amber-500/20 bg-amber-500/10 text-amber-300 shadow-amber-500/10";
    }
    switch (signal) {
      case "Accumulation":
        return "border-blue-500/20 bg-blue-500/10 text-blue-400 shadow-blue-500/10";
      case "Breakout Watch":
        return "border-emerald-500/20 bg-emerald-500/10 text-emerald-400 shadow-emerald-500/10";
      case "Continuation":
        return "border-cyan-500/20 bg-cyan-500/10 text-cyan-300 shadow-cyan-500/10";
      case "Short Squeeze":
        return "border-amber-500/20 bg-amber-500/10 text-amber-400 shadow-amber-500/10";
      case "Long Squeeze":
        return "border-red-500/20 bg-red-500/10 text-red-400 shadow-red-500/10";
      default:
        return "border-slate-500/20 bg-slate-500/10 text-slate-400 shadow-slate-500/10";
    }
  })();

  const sizeClasses = size === "sm" ? "px-3 py-1 text-xs" : "px-4 py-1.5 text-sm";

  return (
    <span className={`${classes} ${sizeClasses} inline-flex items-center gap-1.5 rounded-lg border font-semibold shadow-lg backdrop-blur-sm`}>
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      {label}
    </span>
  );
}
