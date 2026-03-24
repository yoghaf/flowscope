import { SignalType } from "../data/mockData";

interface SignalBadgeProps {
  signal: SignalType;
  size?: 'sm' | 'md';
}

export default function SignalBadge({ signal, size = 'sm' }: SignalBadgeProps) {
  const getSignalStyle = (signal: SignalType) => {
    switch (signal) {
      case 'Accumulation':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20 shadow-blue-500/10';
      case 'Breakout':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 shadow-emerald-500/10';
      case 'Short Squeeze':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20 shadow-amber-500/10';
      case 'Long Squeeze':
        return 'bg-red-500/10 text-red-400 border-red-500/20 shadow-red-500/10';
      case 'Watch':
        return 'bg-purple-500/10 text-purple-400 border-purple-500/20 shadow-purple-500/10';
      default:
        return 'bg-slate-500/10 text-slate-400 border-slate-500/20 shadow-slate-500/10';
    }
  };

  const sizeClasses = size === 'sm' ? 'px-3 py-1 text-xs' : 'px-4 py-1.5 text-sm';

  return (
    <span className={`${getSignalStyle(signal)} ${sizeClasses} rounded-lg border font-semibold inline-flex items-center gap-1.5 shadow-lg backdrop-blur-sm`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse"></span>
      {signal}
    </span>
  );
}
