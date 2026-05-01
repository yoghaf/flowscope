export type Timeframe = "15m" | "1h" | "4h" | "24h";

export type SignalType =
  | "Accumulation"
  | "Breakout Watch"
  | "Short Squeeze"
  | "Long Squeeze"
  | "Neutral";
export type DataStatus = "VALID" | "NO_DATA" | "INSUFFICIENT_HISTORY";
export type SignalStatus = "VALID_SIGNAL" | "NO_SIGNAL" | "NO_DATA";
export type TrendDirection = "Bullish" | "Bearish" | "Neutral";
export type MarketControl = "Buyer Dominant" | "Seller Dominant" | "Neutral";
export type OiIntentLabel = "Position Building" | "Position Closing" | "Flat";
export type ActionDirective = "ENTER" | "WAIT" | "NO TRADE";

export type MarketState =
  | "Long Build-up"
  | "Short Build-up"
  | "Absorption"
  | "Trap"
  | "Pre-Squeeze"
  | "Expansion"
  | "Neutral";

export type PositionIntent =
  | "Long Build-up"
  | "Short Build-up"
  | "Absorption"
  | "Pre-Squeeze"
  | "None";

export type OiIntensity = "Low" | "Mid" | "High";

export type PositionQuality =
  | "Strong Longs"
  | "Building Longs"
  | "Weak Longs"
  | "Trapped Longs"
  | "Strong Shorts"
  | "Building Shorts"
  | "Weak Shorts"
  | "Trapped Shorts"
  | "Absorption-High"
  | "Absorption-Mid"
  | "Pre-Squeeze-Ready"
  | "Pre-Squeeze-Building"
  | "Neutral";

export type DecisionType =
  | "Continuation-Long"
  | "Continuation-Short"
  | "Trap-Long"
  | "Trap-Short"
  | "Watchlist-Long"
  | "Watchlist-Short"
  | "Squeeze-Setup"
  | "Squeeze-Immediate"
  | "Watchlist-Squeeze"
  | "No-Trade";

export interface FlowMetrics {
  data_valid: boolean;
  data_status_15m: DataStatus;
  data_status_1h: DataStatus;
  data_status_4h: DataStatus;
  data_status_24h: DataStatus;
  history_length_15m: number;
  history_length_1h: number;
  history_length_4h: number;
  history_length_24h: number;
  price_change_15m: number | null;
  price_change_1h: number | null;
  price_change_4h: number | null;
  price_change_24h: number | null;
  oi_change_15m: number | null;
  oi_change_1h: number | null;
  oi_change_4h: number | null;
  oi_change_24h: number | null;
  volume_change_15m: number | null;
  volume_change_1h: number | null;
  volume_change_4h: number | null;
  volume_change_24h: number | null;
  compression_score: number | null;
  compression_score_15m: number | null;
  compression_score_1h: number | null;
  compression_score_4h: number | null;
  compression_score_24h: number | null;
  oi_delta_15m: number | null;
  oi_delta_1h: number | null;
  oi_delta_4h: number | null;
  oi_delta_24h: number | null;
  oi_delta_z_15m: number | null;
  oi_delta_z_1h: number | null;
  oi_delta_z_4h: number | null;
  oi_delta_z_24h: number | null;
  funding_trend_15m: number | null;
  funding_trend_1h: number | null;
  funding_trend_4h: number | null;
  funding_trend_24h: number | null;
  funding_level_15m: number | null;
  funding_level_1h: number | null;
  funding_level_4h: number | null;
  funding_level_24h: number | null;
  funding_extreme_15m: boolean | null;
  funding_extreme_1h: boolean | null;
  funding_extreme_4h: boolean | null;
  funding_extreme_24h: boolean | null;
  oi_percentile_15m: number | null;
  oi_percentile_1h: number | null;
  oi_percentile_4h: number | null;
  oi_percentile_24h: number | null;
  long_short_ratio_level_15m: number | null;
  long_short_ratio_level_1h: number | null;
  long_short_ratio_level_4h: number | null;
  long_short_ratio_level_24h: number | null;
  long_short_ratio_delta_15m: number | null;
  long_short_ratio_delta_1h: number | null;
  long_short_ratio_delta_4h: number | null;
  long_short_ratio_delta_24h: number | null;
  taker_buy_sell_ratio_level_15m: number | null;
  taker_buy_sell_ratio_level_1h: number | null;
  taker_buy_sell_ratio_level_4h: number | null;
  taker_buy_sell_ratio_level_24h: number | null;
  taker_buy_sell_ratio_delta_15m: number | null;
  taker_buy_sell_ratio_delta_1h: number | null;
  taker_buy_sell_ratio_delta_4h: number | null;
  taker_buy_sell_ratio_delta_24h: number | null;
  liq_delta_15m: number | null;
  liq_delta_1h: number | null;
  liq_delta_4h: number | null;
  liq_delta_24h: number | null;
  liq_z_score_15m: number | null;
  liq_z_score_1h: number | null;
  liq_z_score_4h: number | null;
  liq_z_score_24h: number | null;
  liq_pressure_15m: number | null;
  liq_pressure_1h: number | null;
  liq_pressure_4h: number | null;
  liq_pressure_24h: number | null;
  atr_15m: number | null;
  atr_1h: number | null;
  atr_4h: number | null;
  atr_24h: number | null;
  volume_z_15m: number | null;
  volume_z_1h: number | null;
  volume_z_4h: number | null;
  volume_z_24h: number | null;
  recent_high_15m: number | null;
  recent_high_1h: number | null;
  recent_high_4h: number | null;
  recent_high_24h: number | null;
  recent_low_15m: number | null;
  recent_low_1h: number | null;
  recent_low_4h: number | null;
  recent_low_24h: number | null;
  range_mid_15m: number | null;
  range_mid_1h: number | null;
  range_mid_4h: number | null;
  range_mid_24h: number | null;
  wick_ratio_15m: number | null;
  wick_ratio_1h: number | null;
  wick_ratio_4h: number | null;
  wick_ratio_24h: number | null;
  high_wick_candle_15m: boolean | null;
  high_wick_candle_1h: boolean | null;
  high_wick_candle_4h: boolean | null;
  high_wick_candle_24h: boolean | null;
  market_pressure_15m: number | null;
  market_pressure_1h: number | null;
  market_pressure_4h: number | null;
  market_pressure_24h: number | null;
}

export interface ScoreBreakdown {
  open_interest: number;
  volume: number;
  compression: number;
  funding: number;
}

export interface DebugTrace {
  raw_inputs: Record<string, number>;
  features: Record<string, number>;
  intent_logic: Record<string, any>;
  oi_intensity: Record<string, any>;
  position_quality_checks: Record<string, any>;
  reliability_breakdown: Record<string, any>;
}

export interface ExecutionSnapshot {
  entry_type: string;
  entry_range: number[] | null;
  entry_min: number | null;
  entry_max: number | null;
  invalidation: number | null;
  target: number | null;
  target_1: number | null;
  target_2: number | null;
  initial_stop: number | null;
  risk_level: "Low" | "Medium" | "High";
  quality_score: "A" | "B" | "C";
  breakout_valid: boolean;
}

export interface MarketInterpretationSnapshot {
  trend: TrendDirection;
  control: MarketControl;
  state: string;
  oi_intent: OiIntentLabel;
  structure_label: string;
  structure_shift: string;
  recent_high: number | null;
  recent_low: number | null;
  range_mid: number | null;
  higher_timeframe_trend: TrendDirection;
  higher_timeframe_alignment: string;
  counter_trend: boolean;
  action: ActionDirective;
  action_rationale: string;
  interpretation: string;
  trap_risk: number;
  conflict_score: number;
  structure_strength: number;
  flow_alignment: number;
  trend_alignment: number;
  clarity_confidence: number;
  risk_notes: string[];
  warnings: string[];
  self_critique: string;
}

export interface AssetSnapshot {
  symbol: string;
  name: string;
  timeframe: Timeframe;
  snapshot_id: string;
  timestamp: string;
  price: number | null;
  spot_volume: number | null;
  futures_volume: number | null;
  volume: number | null;
  open_interest: number | null;
  funding_rate: number | null;
  long_short_ratio: number | null;
  taker_buy_sell_ratio: number | null;
  long_liquidations: number | null;
  short_liquidations: number | null;
  flow_metrics: FlowMetrics;
  score: number;
  signal: SignalType;
  signal_status: SignalStatus;
  data_status: DataStatus;
  market_state: MarketState;
  state_confidence: number;
  state_probabilities: Record<string, number>;
  position_intent?: PositionIntent;
  oi_intensity?: OiIntensity;
  position_quality?: PositionQuality;
  decision_type?: DecisionType;
  reliability_score?: number;
  priority_multiplier?: number;
  action_bias?: "Bullish" | "Bearish" | "Neutral" | null;
  action_status?: "Building" | "Ready" | "Triggered" | null;
  action_confidence_label?: "High" | "Medium" | "Low" | null;
  action_opportunity_score?: number | null;
  setup_type?: "Squeeze" | "Trap" | "Accumulation" | "Breakout" | "Continuation" | null;
  tf_conflict?: boolean;
  breakdown: ScoreBreakdown;
  exchange_count: number;
  execution?: ExecutionSnapshot | null;
  debug_trace?: DebugTrace | null;
  phase?: string;
  phase_score?: number;
  phase_confidence?: number;
  market_interpretation?: MarketInterpretationSnapshot | null;
}

export interface DashboardMetrics {
  accumulation_signals: number;
  breakout_watch_signals: number;
  oi_market_trend: string;
  volume_spikes: number;
}

export interface HeatmapItem {
  symbol: string;
  timeframe: Timeframe;
  snapshot_id: string;
  value: number;
  signal: SignalType;
  change: number;
}

export interface DashboardResponse {
  generated_at: string;
  market_overview: DashboardMetrics;
  top_signals: AssetSnapshot[];
  oi_leaders: AssetSnapshot[];
  volume_leaders: AssetSnapshot[];
  funding_extremes: AssetSnapshot[];
  heatmap: HeatmapItem[];
}

export interface ScannerResponse {
  generated_at: string;
  timeframe: Timeframe;
  items: AssetSnapshot[];
}

export interface PriceOpenInterestPoint {
  timestamp: string;
  price: number | null;
  open_interest: number | null;
}

export interface VolumePoint {
  timestamp: string;
  spot_volume: number | null;
  futures_volume: number | null;
}

export interface FundingPoint {
  timestamp: string;
  funding_rate: number | null;
}

export interface LiquidationPoint {
  timestamp: string;
  long_liquidations: number | null;
  short_liquidations: number | null;
}

export interface AlertEntry {
  timestamp: string;
  symbol: string;
  timeframe: Timeframe;
  snapshot_id: string;
  signal: SignalType;
  score: number;
}

export interface AlertsResponse {
  generated_at: string;
  items: AlertEntry[];
}

export type MarketRegime = "Trending" | "Ranging" | "Balanced";

export interface TelegramDestination {
  chat_id: string;
  topic_id?: number | null;
  label?: string;
}

export interface AlertPreferences {
  user_id: string;
  timeframes: Timeframe[];
  signal_types: SignalType[];
  market_regimes: MarketRegime[];
  watchlist: string[];
  min_score: number;
  debounce_minutes: number;
  enabled: boolean;
  telegram_enabled?: boolean;
  telegram_chat_id?: string | null;
  telegram_destinations?: TelegramDestination[];
  telegram_configured?: boolean;
  updated_at?: string | null;
}

export interface AlertPreferencesUpdate {
  timeframes?: Timeframe[];
  signal_types?: SignalType[];
  market_regimes?: MarketRegime[];
  watchlist?: string[];
  min_score?: number;
  debounce_minutes?: number;
  enabled?: boolean;
  telegram_enabled?: boolean;
  telegram_chat_id?: string | null;
  telegram_destinations?: TelegramDestination[];
}

export interface TelegramTestResponse {
  ok: boolean;
  message: string;
}

export interface CoinDetailResponse {
  generated_at: string;
  asset: AssetSnapshot;
  price_open_interest: PriceOpenInterestPoint[];
  volume_history: VolumePoint[];
  funding_history: FundingPoint[];
  liquidation_history: LiquidationPoint[];
  alerts: AlertEntry[];
}

export interface SetupPerformance {
  setup_type: string;
  state?: MarketState | null;
  trades: number;
  open_trades?: number;
  closed_trades?: number;
  wins?: number;
  losses?: number;
  breakevens?: number;
  winrate: number;
  avg_win: number;
  avg_loss: number;
  rr_ratio: number;
  expectancy: number;
  validated: boolean;
}

export interface ConditionPerformance {
  setup_type: string;
  regime: string;
  volatility: string;
  trades: number;
  wins?: number;
  losses?: number;
  breakevens?: number;
  winrate: number;
  avg_win: number;
  avg_loss: number;
  rr_ratio: number;
  expectancy: number;
  validated: boolean;
}

export interface PerformanceTradeRow {
  trade_id: number;
  symbol: string;
  timeframe: string;
  setup_type: string;
  state: string;
  bias: string;
  status: string;
  result: string;
  market_regime: string;
  volatility_regime: string;
  confidence_pct?: number | null;
  quality_score?: string | null;
  risk_level?: string | null;
  signal_timestamp: string;
  created_at: string;
  entry_touched_at?: string | null;
  fill_count: number;
  last_scale_in_at?: string | null;
  closed_at?: string | null;
  close_reason?: string | null;
  updated_at: string;
  entry_price?: number | null;
  invalidation_price?: number | null;
  target_price_1?: number | null;
  target_price_2?: number | null;
  risk_per_unit?: number | null;
  reward_tp1_per_unit?: number | null;
  reward_tp2_per_unit?: number | null;
  planned_rr_tp1?: number | null;
  planned_rr_tp2?: number | null;
  capital_per_trade?: number | null;
  estimated_quantity?: number | null;
  risk_amount_usd?: number | null;
  tp1_reward_usd?: number | null;
  tp2_reward_usd?: number | null;
  risk_pct_of_capital?: number | null;
  pnl_pct?: number | null;
  realized_pnl_usd?: number | null;
  realized_r_multiple?: number | null;
  max_profit_pct?: number | null;
  max_profit_usd?: number | null;
  max_drawdown_pct?: number | null;
  max_drawdown_usd?: number | null;
  strategy_version?: string | null;
  position_size_multiplier?: number | null;
}

export interface PerformanceTradeTableResponse {
  generated_at: string;
  symbol: string;
  timeframe: string;
  setup_type?: string | null;
  capital_per_trade: number;
  total_rows: number;
  rows: PerformanceTradeRow[];
}

export interface PerformanceResponse {
  generated_at: string;
  total_trades: number;
  winrate: number;
  expectancy: number;
  best_setup?: string | null;
  worst_setup?: string | null;
  setups: SetupPerformance[];
  regimes?: RegimePerformance[];
  conditions?: ConditionPerformance[];
}

export interface RegimePerformance {
  regime: string;
  trades: number;
  wins?: number;
  losses?: number;
  breakevens?: number;
  winrate: number;
  avg_win: number;
  avg_loss: number;
  rr_ratio: number;
  expectancy: number;
  validated: boolean;
}

export interface RealtimeEvent {
  type: "market_update" | "signal" | "snapshot" | "ping";
  timestamp: string;
  symbols: string[];
  signal?: AlertEntry | null;
}
