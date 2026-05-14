import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, CheckCircle2, Clock, Eye, ShieldX, Sparkles, Volume2 } from "lucide-react";
import MetricCard from "../components/MetricCard";
import { coinData, generateHeatmapData } from "../data/mockData";
import { Link } from "react-router";
import { getDecisionStyle, getDisplayDecision, getHumanReason } from "../utils/decision";

const count = (label: string) => coinData.filter(c => getDisplayDecision(c) === label).length;
const pipeline = [
  { label: 'Trade Ready', value: count('TRADE READY'), icon: CheckCircle2, trend: 'up' as const },
  { label: 'Watchlist', value: count('WATCHLIST'), icon: Eye, trend: 'up' as const },
  { label: 'Waiting', value: count('WAIT'), icon: Clock, trend: 'down' as const },
  { label: 'Blocked', value: count('BLOCKED'), icon: ShieldX, trend: 'down' as const },
  { label: 'Data Issues', value: count('DATA ISSUE'), icon: AlertTriangle, trend: 'down' as const },
  { label: 'No Setup', value: count('NO SETUP'), icon: Activity, trend: 'down' as const },
];

export default function Dashboard() {
  const heatmapData = generateHeatmapData();
  const topRows = [...coinData].sort((a, b) => b.score - a.score).slice(0, 8);
  const blockers = coinData.reduce<Record<string, number>>((acc, coin) => {
    const decision = getDisplayDecision(coin);
    if (decision !== 'TRADE READY') acc[getHumanReason(coin)] = (acc[getHumanReason(coin)] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-8">
      <div className="relative">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 via-purple-500/10 to-emerald-500/10 blur-3xl opacity-30"></div>
        <div className="relative">
          <div className="flex items-center gap-2 mb-3"><Sparkles className="w-5 h-5 text-primary" /><span className="text-xs font-semibold text-primary uppercase tracking-wider">Live Decision Pipeline</span></div>
          <h1 className="text-4xl font-bold text-foreground mb-2 tracking-tight">Market Overview</h1>
          <p className="text-muted-foreground text-lg">Scanner status organized around human trading decisions, not raw backend labels.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {pipeline.map(item => <MetricCard key={item.label} title={item.label} value={item.value} change={0} icon={item.icon} trend={item.trend} />)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden hover:border-white/20 transition-all duration-300">
            <div className="px-6 py-5 border-b border-white/10">
              <div className="flex items-center justify-between"><div><h2 className="text-xl font-semibold text-foreground">Decision Pipeline</h2><p className="text-sm text-muted-foreground mt-0.5">Every asset shows what to do and why.</p></div><div className="px-3 py-1.5 bg-primary/10 rounded-lg border border-primary/20"><span className="text-xs font-semibold text-primary">{count('TRADE READY')} Trade Ready</span></div></div>
            </div>
            <div className="overflow-x-auto"><table className="w-full"><thead><tr className="border-b border-white/5"><th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Asset</th><th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Setup</th><th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Decision</th><th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Main Reason</th><th className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Confidence</th></tr></thead>
              <tbody>{topRows.map(coin => { const decision = getDisplayDecision(coin); return <tr key={coin.symbol} className="border-b border-white/5 hover:bg-white/5 transition-colors group"><td className="px-6 py-4"><Link to={`/coin/${coin.symbol}`} className="font-semibold text-foreground group-hover:text-primary">{coin.symbol}</Link><div className="text-xs text-muted-foreground">{coin.name}</div></td><td className="px-6 py-4 text-sm text-foreground">{coin.setup}</td><td className="px-6 py-4"><span className={`px-3 py-1 rounded-lg border text-xs font-semibold ${getDecisionStyle(decision)}`}>{decision}</span></td><td className="px-6 py-4 text-sm text-foreground">{getHumanReason(coin)}</td><td className="px-6 py-4 text-right font-semibold">{coin.score}</td></tr>; })}</tbody>
            </table></div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all duration-300">
            <div className="flex items-center gap-2 mb-5"><div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20"><ShieldX className="w-4 h-4 text-red-400" /></div><h3 className="font-semibold text-foreground">Top Blockers</h3></div>
            <div className="space-y-2">{Object.entries(blockers).sort((a,b) => b[1] - a[1]).slice(0, 6).map(([reason, qty], idx) => <div key={reason} className="flex items-center justify-between p-3 bg-white/5 rounded-xl"><div className="flex items-center gap-3"><span className="text-xs font-semibold text-muted-foreground w-5 h-5 flex items-center justify-center bg-white/5 rounded-md">{idx + 1}</span><span className="font-semibold text-foreground">{reason}</span></div><span className="font-semibold text-red-300">{qty}</span></div>)}</div>
          </div>

          <Widget title="OI Leaders" icon={<ArrowUpRight className="w-4 h-4 text-emerald-400" />} rows={coinData.filter(c => c.oiChange1h > 0).sort((a, b) => b.oiChange1h - a.oiChange1h).slice(0, 5).map(c => [c.symbol, `+${c.oiChange1h}%`])} />
          <Widget title="Volume Spikes" icon={<Volume2 className="w-4 h-4 text-blue-400" />} rows={coinData.sort((a, b) => b.volumeChange - a.volumeChange).slice(0, 5).map(c => [c.symbol, `+${c.volumeChange}%`])} />
        </div>
      </div>

      <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden hover:border-white/20 transition-all duration-300">
        <div className="px-6 py-5 border-b border-white/10"><h2 className="text-xl font-semibold text-foreground">Flow Activity Heatmap</h2><p className="text-sm text-muted-foreground mt-0.5">Real-time signal strength visualization</p></div>
        <div className="p-6"><div className="grid grid-cols-5 gap-3">{heatmapData.slice(0, 25).map((item, idx) => <div key={idx} className="aspect-square rounded-xl border border-white/10 flex items-center justify-center text-xs font-semibold text-white" style={{ backgroundColor: `rgba(0, 200, 120, ${Math.max(0.12, item.value / 100)})` }}>{item.symbol}</div>)}</div></div>
      </div>
    </div>
  );
}

function Widget({ title, icon, rows }: { title: string; icon: JSX.Element; rows: string[][] }) {
  return <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all duration-300"><div className="flex items-center gap-2 mb-5"><div className="p-2 rounded-lg bg-white/5 border border-white/10">{icon}</div><h3 className="font-semibold text-foreground">{title}</h3></div><div className="space-y-2">{rows.map(([symbol, value], idx) => <Link key={symbol} to={`/coin/${symbol}`} className="flex items-center justify-between p-3 hover:bg-white/5 rounded-xl transition-all group"><div className="flex items-center gap-3"><span className="text-xs font-semibold text-muted-foreground w-5 h-5 flex items-center justify-center bg-white/5 rounded-md">{idx + 1}</span><span className="font-semibold text-foreground group-hover:text-primary">{symbol}</span></div><span className="font-semibold text-emerald-400">{value}</span></Link>)}</div></div>;
}
