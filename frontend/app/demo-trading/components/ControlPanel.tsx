"use client";

import { Play, Square, RefreshCw, AlertTriangle } from "lucide-react";
import type { DemoStatus } from "@/lib/types";

import StatusDot from "./StatusDot";

interface ControlPanelProps {
  isRunning: boolean;
  status: DemoStatus | undefined;
  isLoading: boolean;
  onStart: () => void;
  onStop: () => void;
  onForceStop?: () => void; // Optional for stuck sessions
  isStarting: boolean;
  isStopping: boolean;
  isForceStopping?: boolean;
}

export default function ControlPanel({
  isRunning,
  status,
  isLoading,
  onStart,
  onStop,
  onForceStop,
  isStarting,
  isStopping,
  isForceStopping = false,
}: ControlPanelProps) {
  return (
    <section className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        {/* Status Indicator */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg bg-muted px-4 py-2">
            <StatusDot isRunning={isRunning} />
            <span className="font-medium">
              {isLoading ? "Loading..." : isRunning ? "Running" : "Stopped"}
            </span>
          </div>

          {status && (
            <div className="hidden items-center gap-2 text-sm text-muted-foreground md:flex">
              <span>
                Last update:{" "}
                {status.last_update 
                  ? new Date(status.last_update).toLocaleTimeString()
                  : new Date().toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>

        {/* Control Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onStart}
            disabled={isRunning || isStarting}
            className="flex items-center gap-2 rounded-lg bg-emerald-600 px-6 py-3 font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isStarting ? (
              <RefreshCw className="h-5 w-5 animate-spin" />
            ) : (
              <Play className="h-5 w-5" />
            )}
            {isStarting ? "Starting..." : "▶ Start Demo"}
          </button>

          <button
            onClick={onStop}
            disabled={!isRunning || isStopping}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-6 py-3 font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isStopping ? (
              <RefreshCw className="h-5 w-5 animate-spin" />
            ) : (
              <Square className="h-5 w-5" />
            )}
            {isStopping ? "Stopping..." : "⏹ Stop Demo"}
          </button>

          {onForceStop && (
            <button
              onClick={onForceStop}
              disabled={isForceStopping}
              className="flex items-center gap-2 rounded-lg bg-orange-600 px-6 py-3 font-semibold text-white transition hover:bg-orange-700 disabled:cursor-not-allowed disabled:opacity-50"
              title="Use this if normal stop fails or session is stuck"
            >
              {isForceStopping ? (
                <RefreshCw className="h-5 w-5 animate-spin" />
              ) : (
                <AlertTriangle className="h-5 w-5" />
              )}
              <span className="hidden md:inline">
                {isForceStopping ? "Stopping..." : "⚠️ Force Stop"}
              </span>
            </button>
          )}

          <button
            onClick={() => window.location.reload()}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
          >
            <RefreshCw className="h-5 w-5" />
            <span className="hidden md:inline">Refresh</span>
          </button>
        </div>
      </div>
    </section>
  );
}
