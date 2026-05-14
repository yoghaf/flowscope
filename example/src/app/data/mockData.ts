export type SignalType = 'Accumulation' | 'Breakout' | 'Short Squeeze' | 'Long Squeeze' | 'Neutral' | 'Watch';

export interface CoinData {
  symbol: string;
  name: string;
  price: number;
  oiChange15m: number;
  oiChange1h: number;
  oiChange4h: number;
  volumeChange: number;
  fundingRate: number;
  longShortRatio: number;
  score: number;
  signal: SignalType;
  bias?: 'Long' | 'Short' | 'Neutral' | 'Mixed';
  setup?: string;
  action?: string;
  final_entry_permission?: 'ALLOW' | 'BLOCK' | 'WAIT';
  scenario_disposition?: 'allow' | 'wait' | 'observe' | 'mixed_context';
  dqStatus?: 'FRESH' | 'STALE' | 'FALLBACK' | 'DEGRADED';
  dqCritical?: boolean;
  requiredReliability?: boolean;
  hard_filter_reasons?: string[];
  structure?: string;
  classifierTrace?: string[];
  provenance?: string[];
  interpretation?: string;
  execution?: string;
}

export const coinData: CoinData[] = [
  {
    symbol: 'BTC',
    name: 'Bitcoin',
    price: 68420.50,
    oiChange15m: 2.4,
    oiChange1h: 5.8,
    oiChange4h: 12.3,
    volumeChange: 145,
    fundingRate: 0.01,
    longShortRatio: 1.2,
    score: 87,
    signal: 'Accumulation', bias: 'Long', setup: 'Efficient build continuation', action: 'Prepare entry', final_entry_permission: 'ALLOW', scenario_disposition: 'allow', dqStatus: 'FRESH', requiredReliability: true, hard_filter_reasons: [], structure: 'Higher low with OI build', classifierTrace: ['Trend aligned', 'Flow supportive'], provenance: ['OI OK', 'Funding OK', 'Liq OK'], interpretation: 'Constructive long setup with acceptable execution conditions.', execution: 'Trade only on planned pullback/trigger.'
  },
  {
    symbol: 'ETH',
    name: 'Ethereum',
    price: 3245.80,
    oiChange15m: 3.1,
    oiChange1h: 7.2,
    oiChange4h: 15.6,
    volumeChange: 178,
    fundingRate: 0.015,
    longShortRatio: 1.4,
    score: 92,
    signal: 'Breakout', bias: 'Long', setup: 'Breakout continuation', action: 'Prepare entry', final_entry_permission: 'ALLOW', scenario_disposition: 'allow', dqStatus: 'FRESH', requiredReliability: true, hard_filter_reasons: [], structure: 'Range break with follow-through', classifierTrace: ['Breakout confirmed', 'Volume expansion'], provenance: ['OI OK', 'Funding OK', 'Ratio OK'], interpretation: 'Breakout is actionable while structure remains intact.', execution: 'Avoid chasing extended candle; use invalidation.'
  },
  {
    symbol: 'SOL',
    name: 'Solana',
    price: 142.35,
    oiChange15m: -1.2,
    oiChange1h: -2.8,
    oiChange4h: -5.4,
    volumeChange: 65,
    fundingRate: -0.02,
    longShortRatio: 0.75,
    score: 68,
    signal: 'Short Squeeze', bias: 'Mixed', setup: 'Mixed context squeeze', action: 'Wait', final_entry_permission: 'ALLOW', scenario_disposition: 'observe', dqStatus: 'FRESH', requiredReliability: true, hard_filter_reasons: ['mixed_context_blocked'], structure: 'Compression without clean direction', classifierTrace: ['Squeeze detected', 'Context mixed'], provenance: ['OI OK', 'Funding OK'], interpretation: 'Potential squeeze, but context is mixed.', execution: 'Wait for directional confirmation.'
  },
  {
    symbol: 'ARB',
    name: 'Arbitrum',
    price: 1.24,
    oiChange15m: 1.8,
    oiChange1h: 4.5,
    oiChange4h: 9.2,
    volumeChange: 112,
    fundingRate: 0.008,
    longShortRatio: 1.1,
    score: 78,
    signal: 'Accumulation', bias: 'Long', setup: 'Structural watchlist', action: 'Watchlist', final_entry_permission: 'WAIT', scenario_disposition: 'wait', dqStatus: 'FRESH', requiredReliability: true, hard_filter_reasons: [], structure: 'Base forming', classifierTrace: ['Accumulation present', 'Trigger incomplete'], provenance: ['OI OK', 'Volume OK'], interpretation: 'Interesting structure but no entry trigger yet.', execution: 'Set alert near confirmation level.'
  },
  {
    symbol: 'AVAX',
    name: 'Avalanche',
    price: 38.92,
    oiChange15m: 0.5,
    oiChange1h: 1.2,
    oiChange4h: 2.8,
    volumeChange: 42,
    fundingRate: 0.005,
    longShortRatio: 1.0,
    score: 52,
    signal: 'Neutral', bias: 'Neutral', setup: 'No clear edge', action: 'Ignore', final_entry_permission: 'ALLOW', scenario_disposition: 'allow', dqStatus: 'FRESH', requiredReliability: true, hard_filter_reasons: [], structure: 'Choppy range', classifierTrace: ['No setup detected'], provenance: ['Market data OK'], interpretation: 'No tradable edge is present.', execution: 'Ignore until structure changes.'
  },
  {
    symbol: 'MATIC',
    name: 'Polygon',
    price: 0.89,
    oiChange15m: 2.2,
    oiChange1h: 5.1,
    oiChange4h: 10.8,
    volumeChange: 98,
    fundingRate: 0.012,
    longShortRatio: 1.3,
    score: 81,
    signal: 'Watch', bias: 'Long', setup: 'Watchlist continuation', action: 'Watchlist', final_entry_permission: 'WAIT', scenario_disposition: 'wait', dqStatus: 'FRESH', requiredReliability: true, hard_filter_reasons: [], structure: 'Constructive but early', classifierTrace: ['Flow building', 'Trigger missing'], provenance: ['OI OK', 'Funding OK'], interpretation: 'Candidate for later, not tradable now.', execution: 'Wait for trigger.'
  },
  {
    symbol: 'LINK',
    name: 'Chainlink',
    price: 14.56,
    oiChange15m: -0.8,
    oiChange1h: -1.9,
    oiChange4h: -4.2,
    volumeChange: 35,
    fundingRate: -0.015,
    longShortRatio: 0.85,
    score: 45,
    signal: 'Neutral', bias: 'Neutral', setup: 'No-Trade', action: 'Ignore', final_entry_permission: 'BLOCK', scenario_disposition: 'wait', dqStatus: 'STALE', dqCritical: true, requiredReliability: false, hard_filter_reasons: ['oi_delta_unreliable'], structure: 'No structure', classifierTrace: ['Data stale', 'No edge'], provenance: ['OI degraded'], interpretation: 'Data quality prevents a reliable decision.', execution: 'Do not trade.'
  },
  {
    symbol: 'UNI',
    name: 'Uniswap',
    price: 8.34,
    oiChange15m: 3.5,
    oiChange1h: 8.2,
    oiChange4h: 18.4,
    volumeChange: 156,
    fundingRate: 0.018,
    longShortRatio: 1.6,
    score: 88,
    signal: 'Breakout', bias: 'Long', setup: 'Continuation pullback', action: 'Wait', final_entry_permission: 'BLOCK', scenario_disposition: 'wait', dqStatus: 'FRESH', requiredReliability: true, hard_filter_reasons: ['chasing_pump_candle'], structure: 'Extended impulse', classifierTrace: ['Breakout late', 'Pump risk'], provenance: ['OI OK', 'Liq OK'], interpretation: 'Move is extended; entry would be chasing.', execution: 'Wait for reset.'
  },
  {
    symbol: 'DOGE',
    name: 'Dogecoin',
    price: 0.15,
    oiChange15m: 1.1,
    oiChange1h: 2.8,
    oiChange4h: 6.5,
    volumeChange: 78,
    fundingRate: 0.007,
    longShortRatio: 1.15,
    score: 64,
    signal: 'Watch', bias: 'Mixed', setup: 'Structural watchlist', action: 'Watchlist', final_entry_permission: 'WAIT', scenario_disposition: 'observe', dqStatus: 'DEGRADED', requiredReliability: true, hard_filter_reasons: [], structure: 'Meme flow unstable', classifierTrace: ['Watch only', 'Confirmation missing'], provenance: ['Funding degraded'], interpretation: 'Watch only because confirmation is incomplete.', execution: 'No entry until confirmation.'
  },
  {
    symbol: 'ADA',
    name: 'Cardano',
    price: 0.62,
    oiChange15m: -2.1,
    oiChange1h: -4.8,
    oiChange4h: -9.6,
    volumeChange: 52,
    fundingRate: -0.025,
    longShortRatio: 0.68,
    score: 72,
    signal: 'Long Squeeze', bias: 'Short', setup: 'Squeeze reversal candidate', action: 'Wait', final_entry_permission: 'BLOCK', scenario_disposition: 'observe', dqStatus: 'FRESH', requiredReliability: true, hard_filter_reasons: ['exhaustion_oi_climax'], structure: 'Crowded downside risk', classifierTrace: ['Squeeze risk', 'OI climax'], provenance: ['OI OK', 'Funding extreme'], interpretation: 'Reversal risk is elevated, but exhaustion makes entry unsafe.', execution: 'Avoid until risk cools.'
  }
];

export interface AlertData {
  id: string;
  timestamp: Date;
  symbol: string;
  signal: SignalType;
  score: number;
}

export const alertData: AlertData[] = [
  {
    id: '1',
    timestamp: new Date('2026-03-15T14:23:00'),
    symbol: 'ETH',
    signal: 'Breakout',
    score: 92
  },
  {
    id: '2',
    timestamp: new Date('2026-03-15T14:15:00'),
    symbol: 'UNI',
    signal: 'Breakout',
    score: 88
  },
  {
    id: '3',
    timestamp: new Date('2026-03-15T14:05:00'),
    symbol: 'BTC',
    signal: 'Accumulation',
    score: 87
  },
  {
    id: '4',
    timestamp: new Date('2026-03-15T13:58:00'),
    symbol: 'MATIC',
    signal: 'Watch',
    score: 81
  },
  {
    id: '5',
    timestamp: new Date('2026-03-15T13:42:00'),
    symbol: 'ARB',
    signal: 'Accumulation',
    score: 78
  },
  {
    id: '6',
    timestamp: new Date('2026-03-15T13:30:00'),
    symbol: 'ADA',
    signal: 'Long Squeeze',
    score: 72
  },
  {
    id: '7',
    timestamp: new Date('2026-03-15T13:15:00'),
    symbol: 'SOL',
    signal: 'Short Squeeze',
    score: 68
  },
  {
    id: '8',
    timestamp: new Date('2026-03-15T13:02:00'),
    symbol: 'DOGE',
    signal: 'Watch',
    score: 64
  }
];

export const generatePriceOIData = (symbol: string) => {
  const basePrice = coinData.find(c => c.symbol === symbol)?.price || 1000;
  const data = [];
  
  for (let i = 0; i < 24; i++) {
    const variance = (Math.random() - 0.5) * 0.1;
    data.push({
      time: `${i}:00`,
      price: basePrice * (1 + variance),
      oi: 1000000000 * (1 + i * 0.05 + variance * 0.5)
    });
  }
  
  return data;
};

export const generateVolumeData = (symbol: string) => {
  const data = [];
  
  for (let i = 0; i < 24; i++) {
    data.push({
      time: `${i}:00`,
      spot: Math.random() * 500000000 + 200000000,
      futures: Math.random() * 800000000 + 300000000
    });
  }
  
  return data;
};

export const generateFundingData = (symbol: string) => {
  const data = [];
  
  for (let i = 0; i < 24; i++) {
    data.push({
      time: `${i}:00`,
      rate: (Math.random() - 0.5) * 0.05
    });
  }
  
  return data;
};

export const generateLiquidationData = (symbol: string) => {
  const data = [];
  
  for (let i = 0; i < 24; i++) {
    data.push({
      time: `${i}:00`,
      long: Math.random() * 20000000,
      short: Math.random() * 20000000
    });
  }
  
  return data;
};

export const generateHeatmapData = () => {
  return coinData.map(coin => ({
    symbol: coin.symbol,
    value: coin.score,
    signal: coin.signal,
    change: coin.oiChange1h
  }));
};
