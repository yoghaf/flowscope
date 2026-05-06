"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, ChevronDown, Download, Filter, Plus, Trash2 } from "lucide-react";

import SignalBadge from "@/app/components/SignalBadge";
import { api } from "@/lib/api";
import { formatDate, formatTime, scoreToPercent, shortSymbol } from "@/lib/formatters";
import type { AlertPreferencesUpdate, MarketRegime, SignalType, TelegramDestination, Timeframe } from "@/lib/types";
import { getUserId } from "@/lib/user";

const TIMEFRAME_OPTIONS: Timeframe[] = ["15m", "1h", "4h", "24h"];
const FILTER_OPTIONS: Array<{ value: SignalType; label: string }> = [
  { value: "Accumulation", label: "Accumulation" },
  { value: "Breakout Watch", label: "Breakout Watch" },
  { value: "Continuation", label: "Continuation" },
  { value: "Short Squeeze", label: "Short Squeeze" },
  { value: "Long Squeeze", label: "Long Squeeze" },
  { value: "Neutral", label: "Neutral" },
];
const MARKET_REGIME_OPTIONS: Array<{ value: MarketRegime; label: string; hint: string }> = [
  { value: "Balanced", label: "Balanced", hint: "highest WR" },
  { value: "Ranging", label: "Ranging", hint: "range-bound" },
  { value: "Trending", label: "Trending", hint: "momentum" },
];

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const userId = getUserId();
  const timeframeMenuRef = useRef<HTMLDivElement | null>(null);
  const signalMenuRef = useRef<HTMLDivElement | null>(null);
  const [timeframeFilters, setTimeframeFilters] = useState<Timeframe[]>([]);
  const [timeframeMenuOpen, setTimeframeMenuOpen] = useState(false);
  const [signalFilters, setSignalFilters] = useState<SignalType[]>([]);
  const [signalMenuOpen, setSignalMenuOpen] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [watchlistInput, setWatchlistInput] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [debounceMinutes, setDebounceMinutes] = useState(10);
  const [enabledTypes, setEnabledTypes] = useState<SignalType[]>([]);
  const [enabledRegimes, setEnabledRegimes] = useState<MarketRegime[]>([]);
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramChatId, setTelegramChatId] = useState("");
  const [telegramDestinations, setTelegramDestinations] = useState<TelegramDestination[]>([]);
  const [newDestChatId, setNewDestChatId] = useState("");
  const [newDestTopicId, setNewDestTopicId] = useState("");
  const [newDestLabel, setNewDestLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [telegramMessage, setTelegramMessage] = useState<string | null>(null);
  const [testingTelegram, setTestingTelegram] = useState(false);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["alerts", userId, timeframeFilters.join(",")],
    queryFn: () =>
      api.getAlerts({
        symbol: "ALL",
        timeframes: timeframeFilters,
        snapshotId: "latest",
        limit: 200,
      }),
  });

  const { data: preferences } = useQuery({
    queryKey: ["alert-preferences", userId],
    queryFn: () => api.getAlertPreferences(),
  });

  useEffect(() => {
    if (!preferences) {
      return;
    }
    setTimeframeFilters(preferences.timeframes ?? []);
    setNotificationsEnabled(preferences.enabled);
    setMinScore(Math.round((preferences.min_score ?? 0) * 100));
    setDebounceMinutes(preferences.debounce_minutes ?? 10);
    setEnabledTypes(preferences.signal_types ?? []);
    setEnabledRegimes(preferences.market_regimes ?? []);
    setWatchlistInput(preferences.watchlist.map(shortSymbol).join(", "));
    setTelegramEnabled(preferences.telegram_enabled ?? false);
    setTelegramChatId(preferences.telegram_chat_id ?? "");
    setTelegramDestinations(preferences.telegram_destinations ?? []);
  }, [preferences]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (timeframeMenuRef.current && !timeframeMenuRef.current.contains(event.target as Node)) {
        setTimeframeMenuOpen(false);
      }
      if (signalMenuRef.current && !signalMenuRef.current.contains(event.target as Node)) {
        setSignalMenuOpen(false);
      }
    }

    if (signalMenuOpen || timeframeMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [signalMenuOpen, timeframeMenuOpen]);

  const filteredAlerts = useMemo(() => {
    if (!data) {
      return [];
    }
    if (signalFilters.length === 0) {
      return data.items;
    }
    const selected = new Set(signalFilters);
    return data.items.filter((alert) => selected.has(alert.signal));
  }, [data, signalFilters]);

  const signalFilterLabel = useMemo(() => {
    if (signalFilters.length === 0 || signalFilters.length === FILTER_OPTIONS.length) {
      return "All Signals";
    }
    if (signalFilters.length === 1) {
      return signalFilters[0];
    }
    if (signalFilters.length === 2) {
      return signalFilters.join(", ");
    }
    return `${signalFilters.length} signals selected`;
  }, [signalFilters]);

  const timeframeFilterLabel = useMemo(() => {
    if (timeframeFilters.length === 0 || timeframeFilters.length === TIMEFRAME_OPTIONS.length) {
      return "All Timeframes";
    }
    if (timeframeFilters.length <= 2) {
      return timeframeFilters.join(", ");
    }
    return `${timeframeFilters.length} timeframes selected`;
  }, [timeframeFilters]);

  const toggleTimeframeFilter = (timeframe: Timeframe) => {
    setTimeframeFilters((current) => {
      if (current.includes(timeframe)) {
        return current.filter((item) => item !== timeframe);
      }
      return [...current, timeframe];
    });
  };

  const clearTimeframeFilters = () => {
    setTimeframeFilters([]);
  };

  const toggleSignalType = (signal: SignalType) => {
    setEnabledTypes((current) => {
      if (current.includes(signal)) {
        return current.filter((item) => item !== signal);
      }
      return [...current, signal];
    });
  };

  const toggleRegime = (regime: MarketRegime) => {
    setEnabledRegimes((current) => {
      if (current.includes(regime)) {
        return current.filter((item) => item !== regime);
      }
      return [...current, regime];
    });
  };

  const toggleSignalFilter = (signal: SignalType) => {
    setSignalFilters((current) => {
      if (current.includes(signal)) {
        return current.filter((item) => item !== signal);
      }
      return [...current, signal];
    });
  };

  const clearSignalFilters = () => {
    setSignalFilters([]);
  };

  const handleSavePreferences = async () => {
    const watchlist = watchlistInput
      .split(",")
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean);
    const payload: AlertPreferencesUpdate = {
      enabled: notificationsEnabled,
      timeframes: timeframeFilters,
      signal_types: enabledTypes,
      market_regimes: enabledRegimes,
      watchlist,
      min_score: Math.max(0, Math.min(minScore, 100)) / 100,
      debounce_minutes: Math.max(0, Math.min(debounceMinutes, 1440)),
      telegram_enabled: telegramEnabled,
      telegram_chat_id: telegramChatId.trim() || null,
      telegram_destinations: telegramDestinations,
    };

    try {
      setSaving(true);
      setSaveMessage(null);
      await api.updateAlertPreferences(payload);
      await queryClient.invalidateQueries({ queryKey: ["alert-preferences"] });
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
      setSaveMessage("Preferences saved");
    } catch {
      setSaveMessage("Failed to save preferences");
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMessage(null), 2500);
    }
  };

  const handleExportCSV = () => {
    const header = ["Time", "Coin", "Signal", "Score"];
    const rows = filteredAlerts.map((alert) => [
      new Date(alert.timestamp).toISOString().replace("T", " ").replace("Z", ""),
      shortSymbol(alert.symbol),
      alert.signal,
      `${scoreToPercent(alert.score)}%`,
    ]);
    const csv = [header.join(","), ...rows.map((row) => row.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    const stamp = new Date().toISOString().slice(0, 10);
    anchor.download = `flowscope-alerts-${stamp}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const handleTestTelegram = async () => {
    try {
      setTestingTelegram(true);
      setTelegramMessage(null);
      const response = await api.testTelegramAlert();
      setTelegramMessage(response.message);
    } catch {
      setTelegramMessage("Failed to send Telegram test message");
    } finally {
      setTestingTelegram(false);
      setTimeout(() => setTelegramMessage(null), 3000);
    }
  };

  const handleAddTelegramDestination = () => {
    const chatId = newDestChatId.trim();
    if (!chatId) {
      return;
    }
    const parsedTopic = newDestTopicId.trim() ? Number.parseInt(newDestTopicId.trim(), 10) : null;
    const topicId = parsedTopic !== null && Number.isFinite(parsedTopic) && parsedTopic > 0 ? parsedTopic : null;
    const label = newDestLabel.trim() || chatId;
    const exists = telegramDestinations.some(
      (destination) => destination.chat_id === chatId && (destination.topic_id ?? null) === topicId,
    );
    if (!exists) {
      setTelegramDestinations((current) => [
        ...current,
        {
          chat_id: chatId,
          topic_id: topicId,
          label,
        },
      ]);
    }
    setNewDestChatId("");
    setNewDestTopicId("");
    setNewDestLabel("");
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="mb-2 text-4xl font-bold tracking-tight text-foreground">Signal History</h1>
          <p className="text-lg text-muted-foreground">Historical detections and notification management</p>
        </div>

        <button
          onClick={handleExportCSV}
          className="flex items-center gap-2 rounded-xl bg-primary px-5 py-3 font-semibold text-white shadow-lg shadow-primary/30 transition-all hover:scale-105 hover:bg-primary/90"
        >
          <Download className="h-4 w-4" />
          Export CSV
        </button>
      </div>

      <div id="alert-preferences" className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur-xl transition-all hover:border-white/20">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Filter className="h-5 w-5 text-primary" />
              <h3 className="font-semibold text-foreground">Filters</h3>
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-muted-foreground">Timeframe:</label>
              <div ref={timeframeMenuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setTimeframeMenuOpen((current) => !current)}
                  className="flex min-w-[190px] items-center justify-between rounded-xl border border-white/10 bg-[#0B0F14] px-4 py-2 font-medium text-foreground transition-all hover:border-primary/40 focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  <span className="truncate pr-3">{timeframeFilterLabel}</span>
                  <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${timeframeMenuOpen ? "rotate-180" : ""}`} />
                </button>
                {timeframeMenuOpen ? (
                  <div className="absolute z-20 mt-2 w-[260px] rounded-2xl border border-white/10 bg-[#0B0F14] p-3 shadow-2xl shadow-black/40">
                    <div className="mb-3 flex items-center justify-between">
                      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Alert Timeframes</span>
                      <button
                        type="button"
                        onClick={clearTimeframeFilters}
                        className="text-xs font-semibold text-primary transition hover:text-primary/80"
                      >
                        Clear
                      </button>
                    </div>
                    <div className="space-y-2">
                      {TIMEFRAME_OPTIONS.map((tf) => {
                        const active = timeframeFilters.includes(tf);
                        return (
                          <label
                            key={tf}
                            className="flex cursor-pointer items-center justify-between rounded-xl border border-white/5 bg-white/5 px-3 py-2 text-sm text-foreground transition hover:border-primary/30 hover:bg-white/10"
                          >
                            <div className="flex items-center gap-3">
                              <input
                                type="checkbox"
                                checked={active}
                                onChange={() => toggleTimeframeFilter(tf)}
                                className="h-4 w-4 rounded border-white/20 bg-transparent text-primary focus:ring-primary/50"
                              />
                              <span>{tf}</span>
                            </div>
                            {active ? <Check className="h-4 w-4 text-primary" /> : null}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-muted-foreground">Signal:</label>
              <div ref={signalMenuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setSignalMenuOpen((current) => !current)}
                  className="flex min-w-[190px] items-center justify-between rounded-xl border border-white/10 bg-[#0B0F14] px-4 py-2 font-medium text-foreground transition-all hover:border-primary/40 focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  <span className="truncate pr-3">{signalFilterLabel}</span>
                  <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${signalMenuOpen ? "rotate-180" : ""}`} />
                </button>
                {signalMenuOpen ? (
                  <div className="absolute z-20 mt-2 w-[280px] rounded-2xl border border-white/10 bg-[#0B0F14] p-3 shadow-2xl shadow-black/40">
                    <div className="mb-3 flex items-center justify-between">
                      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Signal Filter</span>
                      <button
                        type="button"
                        onClick={clearSignalFilters}
                        className="text-xs font-semibold text-primary transition hover:text-primary/80"
                      >
                        Clear
                      </button>
                    </div>
                    <div className="space-y-2">
                      {FILTER_OPTIONS.map((option) => {
                        const active = signalFilters.includes(option.value);
                        return (
                          <label
                            key={option.value}
                            className="flex cursor-pointer items-center justify-between rounded-xl border border-white/5 bg-white/5 px-3 py-2 text-sm text-foreground transition hover:border-primary/30 hover:bg-white/10"
                          >
                            <div className="flex items-center gap-3">
                              <input
                                type="checkbox"
                                checked={active}
                                onChange={() => toggleSignalFilter(option.value)}
                                className="h-4 w-4 rounded border-white/20 bg-transparent text-primary focus:ring-primary/50"
                              />
                              <span>{option.label}</span>
                            </div>
                            {active ? <Check className="h-4 w-4 text-primary" /> : null}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Bell className="h-4 w-4 text-muted-foreground" />
            <label className="text-sm font-medium text-muted-foreground">Notifications:</label>
            <button
              onClick={() => setNotificationsEnabled((current) => !current)}
              className={`relative inline-flex h-7 w-12 items-center rounded-full transition-all duration-300 ${
                notificationsEnabled ? "bg-primary shadow-lg shadow-primary/30" : "bg-white/10"
              }`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform duration-300 ${
                  notificationsEnabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
            <span className={notificationsEnabled ? "text-sm font-semibold text-primary" : "text-sm font-semibold text-muted-foreground"}>
              {notificationsEnabled ? "On" : "Off"}
            </span>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Watchlist</label>
            <input
              value={watchlistInput}
              onChange={(event) => setWatchlistInput(event.target.value)}
              placeholder="BTC, ETH, SOL"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-foreground transition-all focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <p className="text-xs text-muted-foreground">Leave empty to receive all symbols.</p>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Min Score</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={100}
                value={minScore}
                onChange={(event) => setMinScore(Number(event.target.value))}
                className="w-full"
              />
              <span className="w-10 text-right text-sm font-semibold text-foreground">{minScore}%</span>
            </div>
            <p className="text-xs text-muted-foreground">Only alert when score is above this.</p>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Debounce (min)</label>
            <input
              type="number"
              min={0}
              max={1440}
              value={debounceMinutes}
              onChange={(event) => setDebounceMinutes(Number(event.target.value))}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-foreground transition-all focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <p className="text-xs text-muted-foreground">Minimum minutes between alerts per symbol.</p>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Telegram Delivery</label>
              <span
                className={`text-[11px] font-semibold uppercase tracking-wider ${
                  preferences?.telegram_configured ? "text-emerald-300" : "text-amber-300"
                }`}
              >
                {preferences?.telegram_configured ? "Bot Ready" : "Bot Missing"}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setTelegramEnabled((current) => !current)}
                className={`relative inline-flex h-7 w-12 items-center rounded-full transition-all duration-300 ${
                  telegramEnabled ? "bg-primary shadow-lg shadow-primary/30" : "bg-white/10"
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform duration-300 ${
                    telegramEnabled ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
              <span className={telegramEnabled ? "text-sm font-semibold text-primary" : "text-sm font-semibold text-muted-foreground"}>
                {telegramEnabled ? "Telegram On" : "Telegram Off"}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">Aktifkan pengiriman alert ke Telegram untuk user/browser ini.</p>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Telegram Chat ID</label>
            <input
              value={telegramChatId}
              onChange={(event) => setTelegramChatId(event.target.value)}
              placeholder="123456789 atau -100..."
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-foreground transition-all focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <p className="text-xs text-muted-foreground">Isi chat ID tujuan bot Telegram. Simpan preferences sebelum test.</p>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Telegram Test</label>
            <button
              onClick={handleTestTelegram}
              disabled={testingTelegram}
              className="w-full rounded-xl border border-primary/30 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary transition-all hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {testingTelegram ? "Sending Test..." : "Send Test Message"}
            </button>
            <p className="text-xs text-muted-foreground">
              {telegramMessage ?? "Gunakan untuk cek bot token server + chat ID kamu sudah valid."}
            </p>
          </div>
        </div>

        <div className="mt-6 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Telegram Destinations</label>
            <span className="text-xs text-muted-foreground">{telegramDestinations.length} custom target{telegramDestinations.length === 1 ? "" : "s"}</span>
          </div>

          {telegramDestinations.length > 0 ? (
            <div className="grid gap-2 lg:grid-cols-2">
              {telegramDestinations.map((destination, index) => (
                <div
                  key={`${destination.chat_id}-${destination.topic_id ?? "main"}-${index}`}
                  className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-foreground">{destination.label || "Telegram Target"}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <code className="truncate">{destination.chat_id}</code>
                      {destination.topic_id ? <span className="text-cyan-300">Topic #{destination.topic_id}</span> : null}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTelegramDestinations((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-300 transition hover:bg-rose-500/20"
                    aria-label="Remove Telegram destination"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          <div className="grid gap-3 md:grid-cols-[1.3fr_0.7fr_1fr_auto]">
            <input
              value={newDestChatId}
              onChange={(event) => setNewDestChatId(event.target.value)}
              placeholder="Group/User chat ID, e.g. -100..."
              className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-foreground transition-all focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <input
              value={newDestTopicId}
              onChange={(event) => setNewDestTopicId(event.target.value)}
              placeholder="Topic ID"
              inputMode="numeric"
              className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-foreground transition-all focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <input
              value={newDestLabel}
              onChange={(event) => setNewDestLabel(event.target.value)}
              placeholder="Label"
              className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-foreground transition-all focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <button
              type="button"
              onClick={handleAddTelegramDestination}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-300 transition hover:bg-emerald-400/20"
            >
              <Plus className="h-4 w-4" />
              Add
            </button>
          </div>
          <p className="text-xs text-muted-foreground">Untuk grup/topik forum, tambahkan bot ke grup lalu isi chat ID grup dan topic ID tujuan.</p>
        </div>

        <div className="mt-6 flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Signals</span>
              <button
                type="button"
                onClick={() => setEnabledTypes([])}
                className={`rounded-full border px-3 py-1 text-xs font-semibold transition-all ${
                  enabledTypes.length === 0
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-white/10 bg-white/5 text-muted-foreground hover:text-foreground"
                }`}
                title="No signal filter"
              >
                All Signals
              </button>
              {FILTER_OPTIONS.map((option) => {
                const active = enabledTypes.includes(option.value);
                return (
                  <button
                    key={option.value}
                    onClick={() => toggleSignalType(option.value)}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold transition-all ${
                      active
                        ? "border-primary/40 bg-primary/10 text-primary"
                        : "border-white/10 bg-white/5 text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Regime</span>
              <button
                type="button"
                onClick={() => setEnabledRegimes([])}
                className={`rounded-full border px-3 py-1 text-xs font-semibold transition-all ${
                  enabledRegimes.length === 0
                    ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-300"
                    : "border-white/10 bg-white/5 text-muted-foreground hover:text-foreground"
                }`}
                title="No regime filter"
              >
                All Regimes
              </button>
              {MARKET_REGIME_OPTIONS.map((option) => {
                const active = enabledRegimes.includes(option.value);
                return (
                  <button
                    key={option.value}
                    onClick={() => toggleRegime(option.value)}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold transition-all ${
                      active
                        ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-300"
                        : "border-white/10 bg-white/5 text-muted-foreground hover:text-foreground"
                    }`}
                    title={option.hint}
                  >
                    {option.label}
                    {option.value === "Balanced" ? <span className="ml-1 text-[10px] opacity-80">WR+</span> : null}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {saveMessage ? <span className="text-xs text-muted-foreground">{saveMessage}</span> : null}
            <button
              onClick={handleSavePreferences}
              disabled={saving}
              className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-primary/30 transition-all hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Saving..." : "Save Preferences"}
            </button>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Showing <span className="font-semibold text-foreground">{filteredAlerts.length}</span> alerts
        </p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-card/50 backdrop-blur-xl transition-all hover:border-white/20">
        {isLoading ? (
          <div className="p-8 text-muted-foreground">Loading alerts...</div>
        ) : isError ? (
          <div className="p-8 text-muted-foreground">Unable to load alerts. Try again in a moment.</div>
        ) : filteredAlerts.length === 0 ? (
          <div className="p-10 text-center text-muted-foreground">
            No alerts yet. Once signals fire, they will show up here.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">Timestamp</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">Asset</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">Signal Type</th>
                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map((alert) => {
                  const score = scoreToPercent(alert.score);
                  return (
                    <tr key={`${alert.symbol}-${alert.timestamp}`} className="group border-b border-white/5 transition-colors hover:bg-white/5">
                      <td className="px-6 py-4">
                        <div>
                          <div className="font-semibold text-foreground">{formatDate(alert.timestamp)}</div>
                          <div className="text-sm text-muted-foreground">{formatTime(alert.timestamp)}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <Link
                          href={`/coin/${alert.symbol}?timeframe=${alert.timeframe}&snapshot_id=${alert.snapshot_id}`}
                          className="group/link flex items-center gap-3"
                        >
                          <div className="relative">
                            <div className="absolute inset-0 rounded-full bg-primary/20 blur-md" />
                            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-primary/20 to-primary/10 transition-transform group-hover:scale-110 group-hover/link:scale-110">
                              <span className="text-sm font-bold text-primary">{shortSymbol(alert.symbol).charAt(0)}</span>
                            </div>
                          </div>
                          <span className="font-semibold text-foreground transition-colors group-hover/link:text-primary">
                            {shortSymbol(alert.symbol)}
                          </span>
                        </Link>
                      </td>
                      <td className="px-6 py-4">
                        <SignalBadge signal={alert.signal} />
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-3">
                          <div className="h-2 w-20 overflow-hidden rounded-full bg-white/5">
                            <div className="h-full rounded-full bg-gradient-to-r from-primary to-primary/60" style={{ width: `${score}%` }} />
                          </div>
                          <span className="w-10 text-right font-semibold text-foreground">{score}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-white/20">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Total Alerts</p>
          <p className="text-3xl font-bold text-foreground">{data?.items.length ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-blue-500/20">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Accumulation</p>
          <p className="text-3xl font-bold text-blue-400">
            {data?.items.filter((item) => item.signal === "Accumulation").length ?? 0}
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-emerald-500/20">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Breakout Watch</p>
          <p className="text-3xl font-bold text-emerald-400">
            {data?.items.filter((item) => item.signal === "Breakout Watch").length ?? 0}
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-card/50 p-5 backdrop-blur-xl transition-all hover:border-primary/20">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Avg Score</p>
          <p className="text-3xl font-bold text-primary">
            {data && data.items.length > 0
              ? Math.round(data.items.reduce((total, item) => total + scoreToPercent(item.score), 0) / data.items.length)
              : 0}
          </p>
        </div>
      </div>
    </div>
  );
}
