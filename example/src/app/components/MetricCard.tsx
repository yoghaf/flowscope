import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
}

export default function MetricCard({ title, value, change, icon: Icon, trend = 'neutral' }: MetricCardProps) {
  const trendColor = trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-slate-400';
  const bgGradient = trend === 'up' 
    ? 'from-emerald-500/10 to-emerald-500/5' 
    : trend === 'down' 
    ? 'from-red-500/10 to-red-500/5' 
    : 'from-blue-500/10 to-blue-500/5';
  
  return (
    <div className="group relative">
      {/* Subtle glow effect */}
      <div className={`absolute -inset-px bg-gradient-to-br ${bgGradient} rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur`}></div>
      
      <div className="relative bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all duration-300">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">{title}</p>
            <p className="text-3xl font-semibold text-foreground tracking-tight">{value}</p>
          </div>
          <div className={`p-3 rounded-xl bg-gradient-to-br ${bgGradient} border border-white/10`}>
            <Icon className={`w-5 h-5 ${trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-blue-400'}`} />
          </div>
        </div>
        {change !== undefined && (
          <div className="flex items-center gap-1.5">
            <span className={`text-sm font-medium ${trendColor}`}>
              {change > 0 ? '+' : ''}{change}%
            </span>
            <span className="text-xs text-muted-foreground">vs yesterday</span>
          </div>
        )}
      </div>
    </div>
  );
}
