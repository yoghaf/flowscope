import { useState } from "react";
import { ArrowUpDown, SlidersHorizontal, Search as SearchIcon } from "lucide-react";
import SignalBadge from "../components/SignalBadge";
import { coinData, SignalType } from "../data/mockData";
import { Link } from "react-router";

type SortField = 'symbol' | 'price' | 'oiChange15m' | 'oiChange1h' | 'volumeChange' | 'fundingRate' | 'score';

export default function FlowScanner() {
  const [timeframe, setTimeframe] = useState<'15m' | '1h' | '4h'>('1h');
  const [signalFilter, setSignalFilter] = useState<SignalType | 'All'>('All');
  const [scoreRange, setScoreRange] = useState([0, 100]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const filteredData = coinData
    .filter(coin => {
      if (signalFilter !== 'All' && coin.signal !== signalFilter) return false;
      if (coin.score < scoreRange[0] || coin.score > scoreRange[1]) return false;
      if (searchTerm && !coin.symbol.toLowerCase().includes(searchTerm.toLowerCase()) && 
          !coin.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      const multiplier = sortDirection === 'asc' ? 1 : -1;
      if (sortField === 'symbol') return multiplier * a.symbol.localeCompare(b.symbol);
      return multiplier * (a[sortField] - b[sortField]);
    });

  const getOIChange = (coin: typeof coinData[0]) => {
    if (timeframe === '15m') return coin.oiChange15m;
    if (timeframe === '1h') return coin.oiChange1h;
    return coin.oiChange4h;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-foreground mb-2 tracking-tight">Flow Scanner</h1>
        <p className="text-muted-foreground text-lg">Advanced signal detection with real-time filtering</p>
      </div>

      {/* Filters Panel */}
      <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all">
        <div className="flex items-center gap-2 mb-6">
          <SlidersHorizontal className="w-5 h-5 text-primary" />
          <h3 className="font-semibold text-foreground">Filters & Controls</h3>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {/* Timeframe */}
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Timeframe</label>
            <div className="flex gap-2">
              {(['15m', '1h', '4h'] as const).map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`flex-1 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 ${
                    timeframe === tf
                      ? 'bg-primary text-white shadow-lg shadow-primary/30'
                      : 'bg-white/5 text-muted-foreground border border-white/10 hover:bg-white/10 hover:border-white/20'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* Signal Filter */}
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Signal Type</label>
            <select
              value={signalFilter}
              onChange={(e) => setSignalFilter(e.target.value as SignalType | 'All')}
              className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-foreground font-medium focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
            >
              <option value="All">All Signals</option>
              <option value="Accumulation">Accumulation</option>
              <option value="Breakout">Breakout</option>
              <option value="Short Squeeze">Short Squeeze</option>
              <option value="Long Squeeze">Long Squeeze</option>
              <option value="Watch">Watch</option>
              <option value="Neutral">Neutral</option>
            </select>
          </div>

          {/* Score Range */}
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Score Range: {scoreRange[0]} - {scoreRange[1]}
            </label>
            <div className="space-y-3">
              <input
                type="range"
                min="0"
                max="100"
                value={scoreRange[0]}
                onChange={(e) => setScoreRange([parseInt(e.target.value), scoreRange[1]])}
                className="w-full h-2 bg-white/5 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer"
              />
              <input
                type="range"
                min="0"
                max="100"
                value={scoreRange[1]}
                onChange={(e) => setScoreRange([scoreRange[0], parseInt(e.target.value)])}
                className="w-full h-2 bg-white/5 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer"
              />
            </div>
          </div>

          {/* Search */}
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Search Asset</label>
            <div className="relative">
              <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="BTC, ETH..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-11 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-foreground font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Results Count */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Showing <span className="text-foreground font-semibold">{filteredData.length}</span> of {coinData.length} assets
        </p>
      </div>

      {/* Scanner Table */}
      <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden hover:border-white/20 transition-all">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th 
                  className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-white/5 transition-colors"
                  onClick={() => handleSort('symbol')}
                >
                  <div className="flex items-center gap-2">
                    Asset
                    <ArrowUpDown className="w-3.5 h-3.5" />
                  </div>
                </th>
                <th 
                  className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-white/5 transition-colors"
                  onClick={() => handleSort('price')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Price
                    <ArrowUpDown className="w-3.5 h-3.5" />
                  </div>
                </th>
                <th 
                  className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-white/5 transition-colors"
                  onClick={() => handleSort(`oiChange${timeframe === '15m' ? '15m' : timeframe === '1h' ? '1h' : '4h'}` as SortField)}
                >
                  <div className="flex items-center justify-end gap-2">
                    OI Δ ({timeframe})
                    <ArrowUpDown className="w-3.5 h-3.5" />
                  </div>
                </th>
                <th 
                  className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-white/5 transition-colors"
                  onClick={() => handleSort('volumeChange')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Volume Δ
                    <ArrowUpDown className="w-3.5 h-3.5" />
                  </div>
                </th>
                <th 
                  className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-white/5 transition-colors"
                  onClick={() => handleSort('fundingRate')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Funding
                    <ArrowUpDown className="w-3.5 h-3.5" />
                  </div>
                </th>
                <th className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  L/S Ratio
                </th>
                <th 
                  className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-white/5 transition-colors"
                  onClick={() => handleSort('score')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Score
                    <ArrowUpDown className="w-3.5 h-3.5" />
                  </div>
                </th>
                <th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Signal
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredData.map((coin) => (
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
                    <span className={`font-semibold ${getOIChange(coin) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {getOIChange(coin) >= 0 ? '+' : ''}{getOIChange(coin)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className={`font-semibold ${coin.volumeChange >= 100 ? 'text-emerald-400' : 'text-muted-foreground'}`}>
                      +{coin.volumeChange}%
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className={`font-semibold ${coin.fundingRate >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {(coin.fundingRate * 100).toFixed(3)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className="font-medium text-foreground">{coin.longShortRatio.toFixed(2)}</span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <div className="w-20 h-2 bg-white/5 rounded-full overflow-hidden">
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
  );
}
