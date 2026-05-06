"use client";

interface PnLIndicatorProps {
  value: number;
  percentage?: number;
}

export default function PnLIndicator({ value, percentage }: PnLIndicatorProps) {
  const isPositive = value >= 0;

  return (
    <div className="text-right">
      <div
        className={`text-lg font-bold ${isPositive ? "text-emerald-400" : "text-red-400"}`}
      >
        {isPositive ? "↑" : "↓"} ${Math.abs(value).toFixed(2)}
      </div>
      {percentage !== undefined && (
        <div
          className={`text-xs font-medium ${isPositive ? "text-emerald-500" : "text-red-500"}`}
        >
          ({isPositive ? "+" : ""}
          {percentage.toFixed(2)}%)
        </div>
      )}
    </div>
  );
}
