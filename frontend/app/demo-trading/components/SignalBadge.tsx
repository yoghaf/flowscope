"use client";

interface SignalBadgeProps {
  side: "Long" | "Short" | "Neutral";
}

export default function SignalBadge({ side }: SignalBadgeProps) {
  const styles = {
    Long: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    Short: "bg-red-500/20 text-red-400 border-red-500/30",
    Neutral: "bg-gray-500/20 text-gray-400 border-gray-500/30",
  };

  const icons = {
    Long: "↑",
    Short: "↓",
    Neutral: "•",
  };

  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-semibold ${styles[side]}`}
    >
      <span>{icons[side]}</span>
      {side}
    </span>
  );
}
