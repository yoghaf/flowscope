"use client";

import { Info, Save, ShieldCheck, ToggleLeft, ToggleRight } from "lucide-react";
import { useEffect, useState } from "react";

export interface DemoExecutionSettings {
  auto_execute: boolean;
  risk_usdt: number;
  entry_mode: "market_only" | "market_pullback_limit";
  max_entry_drift_pct: number;
  max_market_tp1_progress_pct: number;
  max_pullback_tp1_progress_pct: number;
  tp1_close_pct: number;
  enabled_timeframes: string[];
  enabled_setups: string[];
}

interface DemoSettingsPanelProps {
  settings?: DemoExecutionSettings;
  isLoading: boolean;
  isSaving: boolean;
  onSave: (settings: DemoExecutionSettings) => void;
}

const DEFAULT_SETTINGS: DemoExecutionSettings = {
  auto_execute: false,
  risk_usdt: 10,
  entry_mode: "market_pullback_limit",
  max_entry_drift_pct: 10,
  max_market_tp1_progress_pct: 30,
  max_pullback_tp1_progress_pct: 60,
  tp1_close_pct: 50,
  enabled_timeframes: ["15m", "1h"],
  enabled_setups: ["Continuation", "Squeeze", "Trap"],
};

export default function DemoSettingsPanel({
  settings,
  isLoading,
  isSaving,
  onSave,
}: DemoSettingsPanelProps) {
  const [draft, setDraft] = useState<DemoExecutionSettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    if (settings) {
      setDraft(settings);
    }
  }, [settings]);

  const updateNumber = (
    key:
      | "risk_usdt"
      | "max_entry_drift_pct"
      | "max_market_tp1_progress_pct"
      | "max_pullback_tp1_progress_pct"
      | "tp1_close_pct",
    value: string,
  ) => {
    const parsed = Number(value);
    setDraft((current) => ({
      ...current,
      [key]: Number.isFinite(parsed) ? parsed : current[key],
    }));
  };

  return (
    <section className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-300">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold">Demo Execution Settings</h2>
            <p className="text-sm text-muted-foreground">
              Fixed-risk entry with pullback backup and SL, TP1, TP2 protection.
            </p>
          </div>
        </div>

        <button
          onClick={() => onSave(draft)}
          disabled={isLoading || isSaving}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Save className={`h-4 w-4 ${isSaving ? "animate-pulse" : ""}`} />
          {isSaving ? "Saving..." : "Save Settings"}
        </button>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <button
          type="button"
          onClick={() =>
            setDraft((current) => ({
              ...current,
              auto_execute: !current.auto_execute,
            }))
          }
          className={`flex min-h-[86px] items-center justify-between rounded-xl border p-4 text-left transition ${
            draft.auto_execute
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
              : "border-white/10 bg-white/[0.03] text-muted-foreground hover:bg-white/[0.05]"
          }`}
        >
          <div>
            <FieldLabel
              label="Auto Execute"
              tooltip="Jika enabled, AI signal yang baru muncul akan otomatis dikirim ke demo trading selama demo session sedang running."
            />
            <p className="mt-1 text-sm font-bold">
              {draft.auto_execute ? "Enabled" : "Disabled"}
            </p>
          </div>
          {draft.auto_execute ? (
            <ToggleRight className="h-7 w-7" />
          ) : (
            <ToggleLeft className="h-7 w-7" />
          )}
        </button>

        <button
          type="button"
          onClick={() =>
            setDraft((current) => ({
              ...current,
              entry_mode:
                current.entry_mode === "market_pullback_limit"
                  ? "market_only"
                  : "market_pullback_limit",
            }))
          }
          className={`flex min-h-[86px] items-center justify-between rounded-xl border p-4 text-left transition ${
            draft.entry_mode === "market_pullback_limit"
              ? "border-blue-500/30 bg-blue-500/10 text-blue-100"
              : "border-white/10 bg-white/[0.03] text-muted-foreground hover:bg-white/[0.05]"
          }`}
        >
          <div>
            <FieldLabel
              label="Entry Mode"
              tooltip="Market + Limit berarti sistem market entry kalau harga masih fair, atau pasang limit di planned entry kalau harga sudah agak jalan."
            />
            <p className="mt-1 text-sm font-bold">
              {draft.entry_mode === "market_pullback_limit"
                ? "Market + Limit"
                : "Market Only"}
            </p>
          </div>
          {draft.entry_mode === "market_pullback_limit" ? (
            <ToggleRight className="h-7 w-7" />
          ) : (
            <ToggleLeft className="h-7 w-7" />
          )}
        </button>

        <SettingInput
          label="Risk / Trade"
          tooltip="Nominal rugi maksimum yang ditargetkan jika SL kena. Quantity dihitung dari jarak entry ke SL."
          suffix="USDT"
          value={draft.risk_usdt}
          min={1}
          step={1}
          onChange={(value) => updateNumber("risk_usdt", value)}
        />
        <SettingInput
          label="Entry Drift"
          tooltip="Batas harga boleh bergerak dari planned entry sebelum market entry ditolak. Nilainya dihitung sebagai persen dari jarak entry ke SL."
          suffix="% risk"
          value={draft.max_entry_drift_pct}
          min={0}
          max={100}
          step={1}
          onChange={(value) => updateNumber("max_entry_drift_pct", value)}
        />
        <SettingInput
          label="Market TP1 Max"
          tooltip="Batas progress harga menuju TP1 agar sistem masih boleh market entry. Di atas ini, sistem tidak akan mengejar harga."
          suffix="%"
          value={draft.max_market_tp1_progress_pct}
          min={0}
          max={100}
          step={1}
          onChange={(value) =>
            updateNumber("max_market_tp1_progress_pct", value)
          }
        />
        <SettingInput
          label="Limit TP1 Max"
          tooltip="Batas progress menuju TP1 selama pending limit masih dianggap valid. Jika melewati ini, limit dicancel otomatis."
          suffix="%"
          value={draft.max_pullback_tp1_progress_pct}
          min={0}
          max={100}
          step={1}
          onChange={(value) =>
            updateNumber("max_pullback_tp1_progress_pct", value)
          }
        />
        <SettingInput
          label="TP1 Close"
          tooltip="Persentase posisi yang ditutup di TP1. Sisa posisi lanjut ke TP2 dengan SL yang akan dipindah ke BE setelah TP1 terdeteksi."
          suffix="%"
          value={draft.tp1_close_pct}
          min={1}
          max={99}
          step={1}
          onChange={(value) => updateNumber("tp1_close_pct", value)}
        />
      </div>
    </section>
  );
}

function SettingInput({
  label,
  tooltip,
  suffix,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  tooltip: string;
  suffix: string;
  value: number;
  min: number;
  max?: number;
  step: number;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <FieldLabel label={label} tooltip={tooltip} />
      <div className="mt-2 flex items-center gap-2">
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(event) => onChange(event.target.value)}
          className="h-10 min-w-0 flex-1 rounded-lg border border-white/10 bg-background px-3 text-sm font-semibold tabular-nums outline-none transition focus:border-blue-500/60"
        />
        <span className="text-xs font-semibold text-muted-foreground">
          {suffix}
        </span>
      </div>
    </label>
  );
}

function FieldLabel({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {label}
      <Tooltip text={tooltip} />
    </span>
  );
}

function Tooltip({ text }: { text: string }) {
  return (
    <span
      className="group/tooltip relative inline-flex"
      aria-label={text}
    >
      <Info className="h-3.5 w-3.5 cursor-help text-muted-foreground/80 transition group-hover/tooltip:text-white" />
      <span className="pointer-events-none absolute left-0 top-5 z-50 w-64 rounded-lg border border-white/10 bg-[#10141d] px-3 py-2 text-left text-xs font-medium normal-case leading-relaxed tracking-normal text-slate-200 opacity-0 shadow-2xl shadow-black/40 transition group-hover/tooltip:opacity-100">
        {text}
      </span>
    </span>
  );
}
