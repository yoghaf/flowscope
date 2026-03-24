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
    signal: 'Accumulation'
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
    signal: 'Breakout'
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
    signal: 'Short Squeeze'
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
    signal: 'Accumulation'
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
    signal: 'Neutral'
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
    signal: 'Watch'
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
    signal: 'Neutral'
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
    signal: 'Breakout'
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
    signal: 'Watch'
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
    signal: 'Long Squeeze'
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
