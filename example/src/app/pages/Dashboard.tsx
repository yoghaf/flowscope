import { TrendingUp, Zap, Activity, Volume2, ArrowUpRight, ArrowDownRight, Sparkles } from "lucide-react";
import MetricCard from "../components/MetricCard";
import SignalBadge from "../components/SignalBadge";
import { coinData, generateHeatmapData } from "../data/mockData";
import { Link } from "react-router";

export default function Dashboard() {
  const accumulationSignals = coinData.filter(c => c.signal === 'Accumulation').length;
  const breakoutSignals = coinData.filter(c => c.signal === 'Breakout').length;
  const topCoins = coinData.filter(c => c.score >= 75).sort((a, b) => b.score - a.score);
  const heatmapData = generateHeatmapData();

  return (
    <div className="space-y-8">
      {/* Modern Header with gradient */}
      <div className="relative">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 via-purple-500/10 to-emerald-500/10 blur-3xl opacity-30"></div>
        <div className="relative">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-5 h-5 text-primary" />
            <span className="text-xs font-semibold text-primary uppercase tracking-wider">Live Market Data</span>
          </div>
          <h1 className="text-4xl font-bold text-foreground mb-2 tracking-tight">Market Overview</h1>
          <p className="text-muted-foreground text-lg">Real-time crypto flow analytics and accumulation signals</p>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Accumulation Signals"
          value={accumulationSignals}
          change={12.5}
          icon={TrendingUp}
          trend="up"
        />
        <MetricCard
          title="Breakout Signals"
          value={breakoutSignals}
          change={8.3}
          icon={Zap}
          trend="up"
        />
        <MetricCard
          title="OI Market Trend"
          value="Bullish"
          change={15.2}
          icon={Activity}
          trend="up"
        />
        <MetricCard
          title="Volume Spikes"
          value={24}
          change={-3.2}
          icon={Volume2}
          trend="down"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Accumulation Coins - Takes 2 columns */}
        <div className="lg:col-span-2">
          <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden hover:border-white/20 transition-all duration-300">
            <div className="px-6 py-5 border-b border-white/10">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Top Signals</h2>
                  <p className="text-sm text-muted-foreground mt-0.5">Strongest accumulation patterns detected</p>
                </div>
                <div className="px-3 py-1.5 bg-primary/10 rounded-lg border border-primary/20">
                  <span className="text-xs font-semibold text-primary">{topCoins.length} Active</span>
                </div>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Asset</th>
                    <th className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Price</th>
                    <th className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">OI Δ</th>
                    <th className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Vol Δ</th>
                    <th className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Score</th>
                    <th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {topCoins.map((coin, idx) => (
                    <tr key={coin.symbol} className="border-b border-white/5 hover:bg-white/5 transition-colors group">
                      <td className="px-6 py-4">
                        <Link to={`/coin/${coin.symbol}`} className="flex items-center gap-3">
                          <div className="relative">
                            <div className="absolute inset-0 bg-primary/20 blur-md rounded-full"></div>
                            <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 border border-white/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                              <span className="text-sm font-bold text-primary">{coin.symbol[0]}</span>
                            </div>
                          </div>
                          <div>
                            <div className="font-semibold text-foreground group-hover:text-primary transition-colors">{coin.symbol}</div>
                            <div className="text-xs text-muted-foreground">{coin.name}</div>
                          </div>
                        </Link>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="font-semibold text-foreground">
                          ${coin.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className={`font-semibold ${coin.oiChange1h >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {coin.oiChange1h >= 0 ? '+' : ''}{coin.oiChange1h}%
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className={`font-semibold ${coin.volumeChange >= 100 ? 'text-emerald-400' : 'text-muted-foreground'}`}>
                          +{coin.volumeChange}%
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-3">
                          <div className="w-16 h-2 bg-white/5 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-gradient-to-r from-primary to-primary/60 rounded-full transition-all duration-500" 
                              style={{ width: `${coin.score}%` }}
                            ></div>
                          </div>
                          <span className="font-semibold text-foreground w-8">{coin.score}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <SignalBadge signal={coin.signal} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Market Flow Widgets - Stacked */}
        <div className="space-y-6">
          {/* OI Increase Leaderboard */}
          <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all duration-300">
            <div className="flex items-center gap-2 mb-5">
              <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <ArrowUpRight className="w-4 h-4 text-emerald-400" />
              </div>
              <h3 className="font-semibold text-foreground">OI Leaders</h3>
            </div>
            <div className="space-y-2">
              {coinData
                .filter(c => c.oiChange1h > 0)
                .sort((a, b) => b.oiChange1h - a.oiChange1h)
                .slice(0, 5)
                .map((coin, idx) => (
                  <Link 
                    key={coin.symbol} 
                    to={`/coin/${coin.symbol}`}
                    className="flex items-center justify-between p-3 hover:bg-white/5 rounded-xl transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-semibold text-muted-foreground w-5 h-5 flex items-center justify-center bg-white/5 rounded-md">{idx + 1}</span>
                      <span className="font-semibold text-foreground group-hover:text-primary transition-colors">{coin.symbol}</span>
                    </div>
                    <span className="font-semibold text-emerald-400">+{coin.oiChange1h}%</span>
                  </Link>
                ))}
            </div>
          </div>

          {/* Volume Spike Leaderboard */}
          <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all duration-300">
            <div className="flex items-center gap-2 mb-5">
              <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <Volume2 className="w-4 h-4 text-blue-400" />
              </div>
              <h3 className="font-semibold text-foreground">Volume Spikes</h3>
            </div>
            <div className="space-y-2">
              {coinData
                .sort((a, b) => b.volumeChange - a.volumeChange)
                .slice(0, 5)
                .map((coin, idx) => (
                  <Link 
                    key={coin.symbol} 
                    to={`/coin/${coin.symbol}`}
                    className="flex items-center justify-between p-3 hover:bg-white/5 rounded-xl transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-semibold text-muted-foreground w-5 h-5 flex items-center justify-center bg-white/5 rounded-md">{idx + 1}</span>
                      <span className="font-semibold text-foreground group-hover:text-primary transition-colors">{coin.symbol}</span>
                    </div>
                    <span className="font-semibold text-blue-400">+{coin.volumeChange}%</span>
                  </Link>
                ))}
            </div>
          </div>

          {/* Funding Rate Extremes */}
          <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all duration-300">
            <div className="flex items-center gap-2 mb-5">
              <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <Activity className="w-4 h-4 text-amber-400" />
              </div>
              <h3 className="font-semibold text-foreground">Funding Extremes</h3>
            </div>
            <div className="space-y-2">
              {coinData
                .sort((a, b) => Math.abs(b.fundingRate) - Math.abs(a.fundingRate))
                .slice(0, 5)
                .map((coin, idx) => (
                  <Link 
                    key={coin.symbol} 
                    to={`/coin/${coin.symbol}`}
                    className="flex items-center justify-between p-3 hover:bg-white/5 rounded-xl transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-semibold text-muted-foreground w-5 h-5 flex items-center justify-center bg-white/5 rounded-md">{idx + 1}</span>
                      <span className="font-semibold text-foreground group-hover:text-primary transition-colors">{coin.symbol}</span>
                    </div>
                    <span className={`font-semibold ${coin.fundingRate >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {(coin.fundingRate * 100).toFixed(3)}%
                    </span>
                  </Link>
                ))}
            </div>
          </div>
        </div>
      </div>

      {/* Market Heatmap */}
      <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden hover:border-white/20 transition-all duration-300">
        <div className="px-6 py-5 border-b border-white/10">
          <h2 className="text-xl font-semibold text-foreground">Flow Activity Heatmap</h2>
          <p className="text-sm text-muted-foreground mt-0.5">Real-time signal strength visualization</p>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-5 gap-3">
            {heatmapData.map((item) => {
              const intensity = item.value / 100;
              const getColor = () => {
                if (item.signal === 'Breakout') return { bg: `rgba(16, 185, 129, ${intensity * 0.3})`, border: 'border-emerald-500/20', text: 'text-emerald-400' };
                if (item.signal === 'Accumulation') return { bg: `rgba(59, 130, 246, ${intensity * 0.3})`, border: 'border-blue-500/20', text: 'text-blue-400' };
                if (item.signal === 'Short Squeeze') return { bg: `rgba(245, 158, 11, ${intensity * 0.3})`, border: 'border-amber-500/20', text: 'text-amber-400' };
                if (item.signal === 'Long Squeeze') return { bg: `rgba(239, 68, 68, ${intensity * 0.3})`, border: 'border-red-500/20', text: 'text-red-400' };
                return { bg: `rgba(148, 163, 184, ${intensity * 0.2})`, border: 'border-slate-500/20', text: 'text-slate-400' };
              };

              const colorScheme = getColor();

              return (
                <Link
                  key={item.symbol}
                  to={`/coin/${item.symbol}`}
                  className={`group relative aspect-square rounded-xl border ${colorScheme.border} flex flex-col items-center justify-center p-4 hover:scale-105 transition-all duration-300 overflow-hidden`}
                  style={{ backgroundColor: colorScheme.bg }}
                >
                  <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                  <span className={`relative font-bold ${colorScheme.text} text-base mb-1`}>{item.symbol}</span>
                  <span className="relative text-xs text-muted-foreground font-semibold">{item.value}</span>
                  <div className={`absolute bottom-2 left-2 right-2 h-1 bg-white/10 rounded-full overflow-hidden`}>
                    <div className={`h-full ${colorScheme.text.replace('text-', 'bg-')} rounded-full`} style={{ width: `${intensity * 100}%` }}></div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
