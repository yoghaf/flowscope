"use client";

import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

export type NotificationTone = "success" | "error" | "warning" | "info";

export interface NotificationState {
  title: string;
  message: string;
  tone: NotificationTone;
}

interface NotificationModalProps {
  notification: NotificationState | null;
  onClose: () => void;
}

export default function NotificationModal({
  notification,
  onClose,
}: NotificationModalProps) {
  if (!notification) return null;

  const toneClasses = {
    success: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
    error: "border-red-500/25 bg-red-500/10 text-red-300",
    warning: "border-amber-500/25 bg-amber-500/10 text-amber-300",
    info: "border-blue-500/25 bg-blue-500/10 text-blue-300",
  };

  const Icon =
    notification.tone === "success"
      ? CheckCircle2
      : notification.tone === "error"
        ? XCircle
        : notification.tone === "warning"
          ? AlertTriangle
          : Info;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-card p-5 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className={`rounded-xl border p-2 ${toneClasses[notification.tone]}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-bold text-foreground">
              {notification.title}
            </h2>
            <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
              {notification.message}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-muted-foreground transition hover:bg-white/5 hover:text-foreground"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-5 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-foreground transition hover:bg-white/15"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
