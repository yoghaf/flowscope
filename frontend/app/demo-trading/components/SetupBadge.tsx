"use client";

import type { SetupType } from "@/lib/types";

interface SetupBadgeProps {
  setupType: SetupType | string;
}

export default function SetupBadge({ setupType }: SetupBadgeProps) {
  const getStyles = (type: string) => {
    switch (type) {
      case "Continuation":
        return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      case "Trap":
        return "bg-purple-500/20 text-purple-400 border-purple-500/30";
      case "Squeeze":
        return "bg-orange-500/20 text-orange-400 border-orange-500/30";
      case "Breakout":
        return "bg-cyan-500/20 text-cyan-400 border-cyan-500/30";
      case "Accumulation":
        return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      default:
        return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    }
  };

  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${getStyles(setupType)}`}
    >
      {setupType}
    </span>
  );
}
