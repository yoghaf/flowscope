"use client";

interface StatusDotProps {
  isRunning: boolean;
}

export default function StatusDot({ isRunning }: StatusDotProps) {
  return (
    <span className="relative flex h-3 w-3">
      <span
        className={`absolute inline-flex h-full w-full animate-ping rounded-full ${
          isRunning ? "bg-emerald-400 opacity-75" : "bg-red-400 opacity-75"
        }`}
      />
      <span
        className={`relative inline-flex h-3 w-3 rounded-full ${
          isRunning ? "bg-emerald-500" : "bg-red-500"
        }`}
      />
    </span>
  );
}
