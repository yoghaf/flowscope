import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
}

export default function MetricCard({
  title,
  value,
  change,
  icon: Icon,
  trend = "neutral",
}: MetricCardProps) {
  const trendColor =
    trend === "up" ? "text-emerald-400" : trend === "down" ? "text-red-400" : "text-slate-400";
  const bgGradient =
    trend === "up"
      ? "from-emerald-500/10 to-emerald-500/5"
      : trend === "down"
        ? "from-red-500/10 to-red-500/5"
        : "from-blue-500/10 to-blue-500/5";

  return (
    <div className="group relative">
      <div
        className={`absolute -inset-px rounded-2xl bg-gradient-to-br ${bgGradient} opacity-0 blur transition-opacity duration-500 group-hover:opacity-100`}
      />
      <div className="relative rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all duration-300 hover:border-white/20">
        <div className="mb-4 flex items-start justify-between">
          <div className="flex-1">
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
            <p className="text-3xl font-semibold tracking-tight text-foreground">{value}</p>
          </div>
          <div className={`rounded-xl border border-white/10 bg-gradient-to-br p-3 ${bgGradient}`}>
            <Icon
              className={`h-5 w-5 ${
                trend === "up" ? "text-emerald-400" : trend === "down" ? "text-red-400" : "text-blue-400"
              }`}
            />
          </div>
        </div>
        {change ? (
          <div className="flex items-center gap-1.5">
            <span className={`text-sm font-medium ${trendColor}`}>{change}</span>
            <span className="text-xs text-muted-foreground">vs baseline</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
