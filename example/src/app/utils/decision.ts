import { CoinData } from "../data/mockData";

export type DisplayDecision = 'TRADE READY' | 'WATCHLIST' | 'WAIT' | 'BLOCKED' | 'NO SETUP' | 'DATA ISSUE';

const HARD_REASON_LABELS: Record<string, string> = {
  mixed_context_blocked: 'Mixed market context',
  scenario_not_allow: 'Scenario not allowed yet',
  oi_delta_unreliable: 'OI data not reliable',
  clarity_below_threshold: 'Clarity below threshold',
  volatile_noise_no_structure: 'Volatile noise, no structure',
  continuation_higher_timeframe_not_aligned: 'Higher timeframe not aligned',
  continuation_flow_alignment_below_threshold: 'Flow alignment too weak',
  chasing_pump_candle: 'Chasing pump candle',
  exhaustion_oi_climax: 'OI climax / exhaustion risk',
  efficient_build_taker_divergence_wait: 'Taker/price divergence',
};

const normalize = (value?: string) => (value || '').toLowerCase().replace(/[\s-]+/g, '_');
const textIncludes = (value: string | undefined, terms: string[]) => terms.some(term => normalize(value).includes(term));

export function getReasonLabel(reason: string) {
  return HARD_REASON_LABELS[reason] || reason.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function hasNoSetup(asset: CoinData) {
  return textIncludes(asset.setup, ['no_trade', 'no_clear_edge']) || textIncludes(asset.signal, ['neutral']);
}

export function hasSomeSetup(asset: CoinData) {
  return Boolean(asset.setup && !hasNoSetup(asset)) || asset.signal !== 'Neutral';
}

export function hasDataIssue(asset: CoinData) {
  const dq = normalize(asset.dqStatus);
  const critical = asset.dqCritical ?? (dq === 'stale' || dq === 'fallback');
  const activeSetup = hasSomeSetup(asset);
  return (critical && (dq === 'stale' || dq === 'fallback')) || (activeSetup && asset.requiredReliability === false);
}

export function isHardBlocked(asset: CoinData) {
  return normalize(asset.final_entry_permission) === 'block' || (asset.hard_filter_reasons?.length || 0) > 0;
}

export function getDisplayDecision(asset: CoinData): DisplayDecision {
  const scenario = normalize(asset.scenario_disposition);
  const setup = normalize(asset.setup);
  const action = normalize(asset.action);

  if (hasDataIssue(asset)) return 'DATA ISSUE';
  if (isHardBlocked(asset)) return 'BLOCKED';

  const forbiddenReady = hasNoSetup(asset) || scenario === 'wait' || scenario === 'observe' || scenario === 'mixed_context' || setup.includes('mixed_context');
  if (
    normalize(asset.final_entry_permission) === 'allow' &&
    scenario === 'allow' &&
    asset.dqStatus === 'FRESH' &&
    !asset.hard_filter_reasons?.length &&
    !forbiddenReady
  ) return 'TRADE READY';

  if (action.includes('watchlist') || setup.includes('watchlist') || setup.includes('structural_watchlist')) return 'WATCHLIST';
  if ((scenario === 'wait' || scenario === 'observe') && hasSomeSetup(asset)) return 'WAIT';
  if (hasNoSetup(asset)) return 'NO SETUP';
  return 'WAIT';
}

export function getHumanReason(asset: CoinData) {
  const firstHardReason = asset.hard_filter_reasons?.[0];
  if (firstHardReason) return getReasonLabel(firstHardReason);

  const setup = normalize(asset.setup);
  const scenario = normalize(asset.scenario_disposition);
  if (setup.includes('no_clear_edge') || asset.signal === 'Neutral') return 'No clear edge';
  if (setup.includes('watchlist') || normalize(asset.action).includes('watchlist')) return 'Watchlist only';
  if (scenario === 'observe') return 'Waiting for confirmation';
  if (scenario === 'mixed_context' || setup.includes('mixed_context')) return 'Mixed market context';
  if (asset.dqStatus && asset.dqStatus !== 'FRESH') return 'Data quality degraded';
  return 'No trade reason available';
}

export function getDecisionStyle(decision: DisplayDecision) {
  switch (decision) {
    case 'TRADE READY': return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    case 'WATCHLIST': return 'bg-purple-500/15 text-purple-300 border-purple-500/30';
    case 'WAIT': return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
    case 'BLOCKED': return 'bg-red-500/15 text-red-300 border-red-500/30';
    case 'DATA ISSUE': return 'bg-orange-500/15 text-orange-300 border-orange-500/30';
    case 'NO SETUP': return 'bg-slate-500/15 text-slate-300 border-slate-500/30';
  }
}
