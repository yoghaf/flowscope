export type Timeframe = "15m" | "1h" | "4h" | "24h";

export type SignalType =
  | "Accumulation"
  | "Breakout Watch"
  | "Short Squeeze"
  | "Long Squeeze"
  | "Continuation"
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
  oi_alignment_status_15m?: string;
  oi_delta_reliable_15m?: boolean;
  funding_timestamp_15m?: string | null;
  funding_source_15m?: string;
  funding_age_seconds_15m?: number | null;
  funding_reliable_15m?: boolean;
  liquidation_source_15m?: string;
  liquidation_age_seconds_15m?: number | null;
  taker_ratio_source_15m?: string;
  taker_ratio_age_seconds_15m?: number | null;
  long_short_ratio_source_15m?: string;
  long_short_ratio_age_seconds_15m?: number | null;
  fallback_fields_15m?: string[];
  data_quality_status_15m?: string;
  hard_filter_reasons?: string[] | string;
  block_reasons?: string[] | string;
  scenario_label?: string;
  scenario_disposition?: string;
  final_entry_permission?: string;
  final_structural_permission?: string;
  final_structural_permission_15m?: string;
  structural_block_reason_15m?: string | null;
  structural_warning_reason_15m?: string | null;
  layer5_watch_status?: string;
  layer5_watch_reason?: string;
  layer5_candidate_tier?: string | null;
  layer5_direction_bias?: string;
  layer5_direction_reason?: string;
  v2_action_bias?: string | null;
  v2_action_status?: string | null;
  direction_alignment_status?: string;
  direction_alignment_reason?: string;
  v2balanced_candidate_stage?: string;
  v2balanced_stage_reason?: string;
  v2balanced_semantic_readiness?: string;
  v2balanced_readiness_reason?: string;
  efficient_build_quality?: string;
  efficient_build_quality_reason?: string;
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
  data_quality_score?: number;
  data_quality_status?: string;
  stale_fields?: string[];
  missing_fields?: string[];
  fallback_fields?: string[];
  funding_age_seconds?: number | null;
  funding_source?: string;
  liquidation_age_seconds?: number | null;
  liquidation_source?: string;
  final_entry_permission?: string;
  hard_filter_reasons?: string[] | string;
  block_reasons?: string[] | string;
  scenario_label?: string;
  scenario_disposition?: string;
  final_structural_permission?: string;
  structural_block_reason?: string | null;
  structural_warning_reason?: string | null;
  layer5_watch_status?: string;
  layer5_watch_reason?: string;
  layer5_candidate_tier?: string | null;
  layer5_direction_bias?: string;
  layer5_direction_reason?: string;
  v2_action_bias?: string | null;
  v2_action_status?: string | null;
  direction_alignment_status?: string;
  direction_alignment_reason?: string;
  v2balanced_candidate_stage?: string;
  v2balanced_stage_reason?: string;
  v2balanced_semantic_readiness?: string;
  v2balanced_readiness_reason?: string;
  efficient_build_quality?: string;
  efficient_build_quality_reason?: string;
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
  setup_type?:
    | "Squeeze"
    | "Trap"
    | "Accumulation"
    | "Breakout"
    | "Continuation"
    | null;
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

// Demo Trading Types
export type SetupType =
  | "Continuation"
  | "Trap"
  | "Squeeze"
  | "Breakout"
  | "Accumulation";
export type TradeSide = "Long" | "Short";
export type DemoStatusType = "running" | "stopped" | "error";

export interface DemoStatus {
  is_running: boolean;
  status: DemoStatusType;
  balance: number;
  balance_change: number;
  start_time: string | null;
  last_update: string;
  message: string;
}

export interface DemoPosition {
  id: number | string;
  symbol: string;
  side: TradeSide;
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  setup_type: SetupType;
  entry_time: string;
  age_hours: number;
  // Additional Binance position fields
  mark_price?: number;
  break_even_price?: number;
  liquidation_price?: number;
  leverage?: number;
  margin_type?: "CROSS" | "ISOLATED";
  isolated_margin?: number;
  notional?: number;
  position_amt?: number;
  // Enhanced display fields
  roe?: number;
  margin_ratio?: number;
  maintenance_margin?: number;
}

export interface DemoTrade {
  id: number;
  symbol: string;
  side: TradeSide;
  size: number;
  entry_price: number;
  exit_price: number | null;
  pnl: number | null;
  r_multiple: number | null;
  setup_type: SetupType;
  entry_time: string;
  exit_time: string | null;
  exit_reason: string | null;
}

export interface SignalEvent {
  id?: number;
  symbol: string;
  side: TradeSide;
  setup_type: SetupType;
  message: string;
  timestamp: string;
  status: "open" | "closed";
  entry_price?: number;
  size?: number;
  pnl?: number | null;
  clarity?: number | null;
}

// Binance Open Order interface
export interface BinanceOpenOrder {
  orderId: number;
  symbol: string;
  side: "BUY" | "SELL";
  type: "LIMIT" | "MARKET" | "STOP" | "TAKE_PROFIT" | "STOP_MARKET" | "TAKE_PROFIT_MARKET";
  status: "NEW" | "PARTIALLY_FILLED" | "FILLED" | "CANCELED" | "EXPIRED" | "REJECTED";
  price: number;
  qty: number;
  executedQty: number;
  timeInForce?: string;
  createTime?: number;
  updateTime?: number;
}

// Binance Order History interface
export interface BinanceOrderHistory {
  orderId: number;
  symbol: string;
  side: "BUY" | "SELL";
  type: string;
  status: string;
  price: number;
  qty: number;
  executedQty: number;
  avgPrice?: number;
  timeInForce?: string;
  createTime?: number;
  updateTime?: number;
}

// Binance User Trade interface (filled orders with PnL)
export interface BinanceUserTrade {
  id: number;
  orderId: number;
  symbol: string;
  side: "BUY" | "SELL";
  price: number;
  qty: number;
  realizedPnl: number;
  commission: number;
  commissionAsset: string;
  time: number;
  buyer: boolean;
  maker: boolean;
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
  simulation_mode?: string | null;
  starting_capital?: number | null;
  base_capital_per_trade?: number | null;
  capital_per_trade?: number | null;
  estimated_quantity?: number | null;
  risk_amount_usd?: number | null;
  fee_usd?: number | null;
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
  equity_after_trade?: number | null;
  engine_tag?: string | null;
  strategy_version?: string | null;
  position_size_multiplier?: number | null;
}

export interface PerformanceBreakdownItem {
  key: string;
  total_trades: number;
  closed_trades: number;
  open_trades: number;
  wins: number;
  losses: number;
  breakevens: number;
  timeouts: number;
  winrate: number;
  net_pnl_usd: number;
  expectancy_usd: number;
  profit_factor?: number | null;
  avg_r_multiple?: number | null;
}

export interface PerformanceEquityPoint {
  timestamp: string;
  equity?: number | null;
  pnl_usd?: number | null;
  symbol: string;
  result: string;
}

export interface PerformanceTradeTableResponse {
  generated_at: string;
  symbol: string;
  timeframe: string;
  setup_type?: string | null;
  regime: string;
  result_filter: string;
  month?: string | null;
  search?: string | null;
  scope: string;
  active_tag?: string | null;
  active_since?: string | null;
  strategy: string;
  simulation_mode: "fixed_size" | "fixed_risk" | "equity_risk_pct" | string;
  starting_capital: number;
  capital_per_trade: number;
  risk_per_trade?: number | null;
  risk_pct_per_trade: number;
  fee_pct: number;
  use_position_multiplier: boolean;
  total_rows: number;
  closed_trades: number;
  open_trades: number;
  wins: number;
  losses: number;
  breakevens: number;
  timeouts: number;
  winrate: number;
  net_pnl_usd: number;
  roi_pct: number;
  expectancy_usd: number;
  profit_factor?: number | null;
  max_drawdown_usd: number;
  max_drawdown_pct: number;
  avg_win_usd: number;
  avg_loss_usd: number;
  avg_r_multiple?: number | null;
  equity_curve: PerformanceEquityPoint[];
  by_timeframe: PerformanceBreakdownItem[];
  by_regime: PerformanceBreakdownItem[];
  by_setup: PerformanceBreakdownItem[];
  by_close_reason: PerformanceBreakdownItem[];
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
