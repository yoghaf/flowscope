import { useState } from "react";
import { ArrowUpDown, ChevronDown, Search as SearchIcon, SlidersHorizontal } from "lucide-react";
import { coinData, CoinData, SignalType } from "../data/mockData";
import { Link } from "react-router";
import { getDecisionStyle, getDisplayDecision, getHumanReason, getReasonLabel } from "../utils/decision";

type SortField = 'symbol' | 'score';

const badge = (text: string, className = 'bg-white/5 text-muted-foreground border-white/10') => (
  <span className={`px-2.5 py-1 rounded-lg border text-xs font-semibold whitespace-nowrap ${className}`}>{text}</span>
);

export default function FlowScanner() {
  const [timeframe, setTimeframe] = useState<'15m' | '1h' | '4h'>('1h');
  const [signalFilter, setSignalFilter] = useState<SignalType | 'All'>('All');
  const [scoreRange, setScoreRange] = useState([0, 100]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [expanded, setExpanded] = useState<string | null>(null);

  const handleSort = (field: SortField) => {
    if (sortField === field) setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDirection('desc'); }
  };

  const filteredData = coinData
    .filter(coin => {
      if (signalFilter !== 'All' && coin.signal !== signalFilter) return false;
      if (coin.score < scoreRange[0] || coin.score > scoreRange[1]) return false;
      if (searchTerm && !coin.symbol.toLowerCase().includes(searchTerm.toLowerCase()) && !coin.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      const multiplier = sortDirection === 'asc' ? 1 : -1;
      if (sortField === 'symbol') return multiplier * a.symbol.localeCompare(b.symbol);
      return multiplier * (a.score - b.score);
    });

  const getOIChange = (coin: CoinData) => timeframe === '15m' ? coin.oiChange15m : timeframe === '1h' ? coin.oiChange1h : coin.oiChange4h;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-bold text-foreground mb-2 tracking-tight">Flow Scanner</h1>
        <p className="text-muted-foreground text-lg">Human decision states: trade ready, watch, wait, blocked, no setup, or data issue.</p>
      </div>

      <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-5"><SlidersHorizontal className="w-5 h-5 text-primary" /><h3 className="font-semibold text-foreground">Filters</h3></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          <div><label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Timeframe</label><div className="flex gap-2">{(['15m', '1h', '4h'] as const).map(tf => <button key={tf} onClick={() => setTimeframe(tf)} className={`flex-1 px-4 py-2.5 rounded-xl font-semibold text-sm ${timeframe === tf ? 'bg-primary text-white' : 'bg-white/5 text-muted-foreground border border-white/10'}`}>{tf}</button>)}</div></div>
          <div><label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Backend Signal</label><select value={signalFilter} onChange={(e) => setSignalFilter(e.target.value as SignalType | 'All')} className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-foreground font-medium"><option value="All">All Signals</option><option value="Accumulation">Accumulation</option><option value="Breakout">Breakout</option><option value="Short Squeeze">Short Squeeze</option><option value="Long Squeeze">Long Squeeze</option><option value="Watch">Watch</option><option value="Neutral">Neutral</option></select></div>
          <div><label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Confidence: {scoreRange[0]} - {scoreRange[1]}</label><input type="range" min="0" max="100" value={scoreRange[0]} onChange={(e) => setScoreRange([parseInt(e.target.value), scoreRange[1]])} className="w-full" /><input type="range" min="0" max="100" value={scoreRange[1]} onChange={(e) => setScoreRange([scoreRange[0], parseInt(e.target.value)])} className="w-full" /></div>
          <div><label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Search Asset</label><div className="relative"><SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" /><input placeholder="BTC, ETH..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="w-full pl-11 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-foreground" /></div></div>
        </div>
      </div>

      <div className="flex items-center justify-between"><p className="text-sm text-muted-foreground">Showing <span className="text-foreground font-semibold">{filteredData.length}</span> of {coinData.length} assets</p></div>

      <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-white/10">
              {['Symbol','Bias','Setup','Decision State','DQ','Scenario','Structure','Main Reason','Confidence',''].map((h) => <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">{h}</th>)}
            </tr></thead>
            <tbody>{filteredData.map(coin => {
              const decision = getDisplayDecision(coin);
              const reason = getHumanReason(coin);
              const degraded = coin.dqStatus !== 'FRESH' || coin.requiredReliability === false;
              return <>
                <tr key={coin.symbol} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3"><Link to={`/coin/${coin.symbol}`} className="font-semibold text-foreground hover:text-primary">{coin.symbol}</Link><div className="text-xs text-muted-foreground">{coin.name}</div></td>
                  <td className="px-4 py-3">{coin.bias || 'Neutral'}</td>
                  <td className="px-4 py-3 max-w-[180px] text-foreground">{coin.setup || coin.signal}</td>
                  <td className="px-4 py-3">{badge(decision, getDecisionStyle(decision))}</td>
                  <td className="px-4 py-3">{badge(coin.dqStatus || 'FRESH', coin.dqStatus === 'FRESH' ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20' : 'bg-orange-500/10 text-orange-300 border-orange-500/20')}</td>
                  <td className="px-4 py-3 capitalize">{(coin.scenario_disposition || 'wait').replace('_', ' ')}</td>
                  <td className="px-4 py-3 max-w-[190px] text-muted-foreground">{coin.structure || 'Not available'}</td>
                  <td className="px-4 py-3 text-foreground">{reason}{degraded && <div className="mt-1 flex gap-1 flex-wrap">{badge(`OI ${coin.oiChange1h}%`)}{badge(`Funding ${(coin.fundingRate * 100).toFixed(3)}%`)}{badge(`Ratio ${coin.longShortRatio.toFixed(2)}`)}</div>}</td>
                  <td className="px-4 py-3"><div className="flex items-center gap-2"><div className="w-16 h-2 bg-white/5 rounded-full"><div className="h-full bg-primary rounded-full" style={{ width: `${coin.score}%` }} /></div><span className="font-semibold">{coin.score}</span></div></td>
                  <td className="px-4 py-3"><button onClick={() => setExpanded(expanded === coin.symbol ? null : coin.symbol)} className="p-2 rounded-lg hover:bg-white/10"><ChevronDown className={`w-4 h-4 transition ${expanded === coin.symbol ? 'rotate-180' : ''}`} /></button></td>
                </tr>
                {expanded === coin.symbol && <tr className="border-b border-white/10 bg-white/[0.02]"><td colSpan={10} className="px-6 py-5"><div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
                  <Detail title="Interpretation / risk / execution" items={[coin.interpretation || 'No interpretation available', coin.execution || 'No execution guidance available']} />
                  <Detail title="Classifier trace" items={coin.classifierTrace || []} />
                  <Detail title="Data provenance" items={coin.provenance || [`OI ${getOIChange(coin)}%`, `Funding ${(coin.fundingRate * 100).toFixed(3)}%`, `L/S ${coin.longShortRatio.toFixed(2)}`]} />
                  <Detail title="Raw backend reasons" items={(coin.hard_filter_reasons?.length ? coin.hard_filter_reasons.map(r => `${r} — ${getReasonLabel(r)}`) : [`final_entry_permission=${coin.final_entry_permission}`, `scenario_disposition=${coin.scenario_disposition}`])} />
                </div></td></tr>}
              </>;
            })}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Detail({ title, items }: { title: string; items: string[] }) {
  return <div><h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">{title}</h4><ul className="space-y-1">{items.length ? items.map(item => <li key={item} className="text-sm text-foreground bg-white/5 rounded-lg px-3 py-2">{item}</li>) : <li className="text-sm text-muted-foreground">None</li>}</ul></div>;
}
