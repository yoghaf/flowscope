import { useParams, Link } from "react-router";
import { ArrowLeft, TrendingUp, Activity, DollarSign, Scale, Info } from "lucide-react";
import SignalBadge from "../components/SignalBadge";
import { coinData, generatePriceOIData, generateVolumeData, generateFundingData, generateLiquidationData } from "../data/mockData";
import { LineChart, Line, BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export default function CoinDetail() {
  const { symbol } = useParams<{ symbol: string }>();
  const coin = coinData.find(c => c.symbol === symbol);

  if (!coin) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-foreground mb-2">Asset not found</h2>
          <Link to="/scanner" className="text-primary hover:underline">
            Return to Scanner
          </Link>
        </div>
      </div>
    );
  }

  const priceOIData = generatePriceOIData(symbol!);
  const volumeData = generateVolumeData(symbol!);
  const fundingData = generateFundingData(symbol!);
  const liquidationData = generateLiquidationData(symbol!);

  const getSignalExplanation = () => {
    switch (coin.signal) {
      case 'Accumulation':
        return 'Open Interest rising while price compression continues. Smart money is building positions.';
      case 'Breakout':
        return 'Strong volume spike with OI increase. Price breaking key resistance levels.';
      case 'Short Squeeze':
        return 'Negative funding rate with declining OI. Shorts potentially getting squeezed.';
      case 'Long Squeeze':
        return 'High funding rate with declining OI. Longs potentially being liquidated.';
      case 'Watch':
        return 'Moderate accumulation detected. Watch for confirmation signals.';
      default:
        return 'No significant patterns detected at this time.';
    }
  };

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <Link 
        to="/scanner" 
        className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-muted-foreground hover:text-foreground transition-all"
      >
        <ArrowLeft className="w-4 h-4" />
        <span className="font-medium">Back to Scanner</span>
      </Link>

      {/* Header with coin info */}
      <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-8 hover:border-white/20 transition-all">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 bg-primary/30 blur-2xl rounded-full"></div>
              <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/30 to-primary/10 border border-white/20 flex items-center justify-center">
                <span className="text-2xl font-bold text-primary">{coin.symbol[0]}</span>
              </div>
            </div>
            <div>
              <h1 className="text-4xl font-bold text-foreground tracking-tight">{coin.symbol}</h1>
              <p className="text-muted-foreground text-lg mt-1">{coin.name}</p>
            </div>
          </div>
          
          <div className="text-right">
            <p className="text-4xl font-bold text-foreground mb-3">
              ${coin.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
            <div className="flex items-center gap-3 justify-end">
              <SignalBadge signal={coin.signal} size="md" />
              <div className="px-4 py-2 bg-primary/10 text-primary rounded-xl border border-primary/20 font-semibold">
                Score: {coin.score}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-5 hover:border-white/20 transition-all">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20">
              <TrendingUp className="w-5 h-5 text-blue-400" />
            </div>
            <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">OI Change</span>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted-foreground font-medium">15m:</span>
              <span className={`font-semibold ${coin.oiChange15m >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {coin.oiChange15m >= 0 ? '+' : ''}{coin.oiChange15m}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted-foreground font-medium">1h:</span>
              <span className={`font-semibold ${coin.oiChange1h >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {coin.oiChange1h >= 0 ? '+' : ''}{coin.oiChange1h}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted-foreground font-medium">4h:</span>
              <span className={`font-semibold ${coin.oiChange4h >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {coin.oiChange4h >= 0 ? '+' : ''}{coin.oiChange4h}%
              </span>
            </div>
          </div>
        </div>

        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-5 hover:border-white/20 transition-all">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20">
              <Activity className="w-5 h-5 text-purple-400" />
            </div>
            <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Volume</span>
          </div>
          <p className="text-3xl font-bold text-foreground">+{coin.volumeChange}%</p>
          <p className="text-xs text-muted-foreground mt-2">vs 24h average</p>
        </div>

        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-5 hover:border-white/20 transition-all">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20">
              <DollarSign className="w-5 h-5 text-amber-400" />
            </div>
            <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Funding</span>
          </div>
          <p className={`text-3xl font-bold ${coin.fundingRate >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {(coin.fundingRate * 100).toFixed(3)}%
          </p>
          <p className="text-xs text-muted-foreground mt-2">8h rate</p>
        </div>

        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-5 hover:border-white/20 transition-all">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <Scale className="w-5 h-5 text-emerald-400" />
            </div>
            <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">L/S Ratio</span>
          </div>
          <p className="text-3xl font-bold text-foreground">{coin.longShortRatio.toFixed(2)}</p>
          <p className="text-xs text-muted-foreground mt-2">
            {coin.longShortRatio > 1 ? 'Long bias' : coin.longShortRatio < 1 ? 'Short bias' : 'Balanced'}
          </p>
        </div>
      </div>

      {/* Signal Explanation */}
      <div className="bg-gradient-to-br from-primary/5 to-purple-500/5 backdrop-blur-xl border border-primary/20 rounded-2xl p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-primary/10 border border-primary/20">
            <Info className="w-5 h-5 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-foreground mb-2 flex items-center gap-2">
              Signal Analysis
              <SignalBadge signal={coin.signal} size="md" />
            </h3>
            <p className="text-muted-foreground leading-relaxed">{getSignalExplanation()}</p>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Price vs OI */}
        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all">
          <h3 className="font-semibold text-foreground mb-5">Price vs Open Interest</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={priceOIData}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="time" stroke="#94A3B8" style={{ fontSize: 11 }} />
              <YAxis key="yaxis-price" yAxisId="left" stroke="#3B82F6" style={{ fontSize: 11 }} />
              <YAxis key="yaxis-oi" yAxisId="right" orientation="right" stroke="#10B981" style={{ fontSize: 11 }} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#0F1419', 
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  color: '#F8FAFC',
                  backdropFilter: 'blur(12px)'
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line key="line-price" yAxisId="left" type="monotone" dataKey="price" stroke="#3B82F6" strokeWidth={2.5} dot={false} name="Price" />
              <Line key="line-oi" yAxisId="right" type="monotone" dataKey="oi" stroke="#10B981" strokeWidth={2.5} dot={false} name="Open Interest" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Volume */}
        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all">
          <h3 className="font-semibold text-foreground mb-5">Volume Analysis</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={volumeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="time" stroke="#94A3B8" style={{ fontSize: 11 }} />
              <YAxis stroke="#94A3B8" style={{ fontSize: 11 }} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#0F1419', 
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  color: '#F8FAFC'
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar key="bar-spot" dataKey="spot" fill="#3B82F6" radius={[6, 6, 0, 0]} name="Spot Volume" />
              <Bar key="bar-futures" dataKey="futures" fill="#8B5CF6" radius={[6, 6, 0, 0]} name="Futures Volume" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Funding Rate */}
        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all">
          <h3 className="font-semibold text-foreground mb-5">Funding Rate Trend</h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={fundingData}>
              <defs>
                <linearGradient id="colorFunding" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#F59E0B" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="time" stroke="#94A3B8" style={{ fontSize: 11 }} />
              <YAxis stroke="#94A3B8" style={{ fontSize: 11 }} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#0F1419', 
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  color: '#F8FAFC'
                }}
              />
              <Area type="monotone" dataKey="rate" stroke="#F59E0B" strokeWidth={2.5} fill="url(#colorFunding)" name="Funding Rate %" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Liquidations */}
        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all">
          <h3 className="font-semibold text-foreground mb-5">Liquidation Events</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={liquidationData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="time" stroke="#94A3B8" style={{ fontSize: 11 }} />
              <YAxis stroke="#94A3B8" style={{ fontSize: 11 }} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#0F1419', 
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  color: '#F8FAFC'
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar key="bar-long-liq" dataKey="long" fill="#EF4444" radius={[6, 6, 0, 0]} name="Long Liquidations" />
              <Bar key="bar-short-liq" dataKey="short" fill="#10B981" radius={[6, 6, 0, 0]} name="Short Liquidations" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
