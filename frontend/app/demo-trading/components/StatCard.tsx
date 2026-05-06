"use client";

import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string;
  change?: string;
  icon: LucideIcon;
  trend: "up" | "down" | "neutral";
}

export default function StatCard({
  title,
  value,
  change,
  icon: Icon,
  trend,
}: StatCardProps) {
  const trendColors = {
    up: "text-emerald-500",
    down: "text-red-500",
    neutral: "text-muted-foreground",
  };

  const bgColors = {
    up: "bg-emerald-500/10",
    down: "bg-red-500/10",
    neutral: "bg-muted",
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur transition hover:border-white/20">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="text-3xl font-bold text-foreground">{value}</p>
          {change && (
            <p className={`text-sm font-medium ${trendColors[trend]}`}>
              {change}
            </p>
          )}
        </div>
        <div className={`rounded-xl p-4 ${bgColors[trend]}`}>
          <Icon className={`h-6 w-6 ${trendColors[trend]}`} />
        </div>
      </div>
    </div>
  );
}
