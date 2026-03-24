"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { RealtimeEvent } from "@/lib/types";

export function useRealtimeInvalidation(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    let websocket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let active = true;
    const lastInvalidationAt = new Map<string, number>();

    const invalidateThrottled = (queryKey: readonly unknown[], minIntervalMs: number) => {
      const key = JSON.stringify(queryKey);
      const now = Date.now();
      const lastRun = lastInvalidationAt.get(key) ?? 0;

      if (now - lastRun < minIntervalMs) {
        return;
      }

      lastInvalidationAt.set(key, now);
      queryClient.invalidateQueries({ queryKey });
    };

    const connect = () => {
      if (!active) {
        return;
      }

      websocket = new WebSocket(api.getWebSocketUrl());
      websocket.onmessage = (event) => {
        const payload = JSON.parse(event.data) as RealtimeEvent;
        if (payload.type === "ping") {
          return;
        }

        if (payload.type === "snapshot") {
          invalidateThrottled(["dashboard"], 10_000);
          invalidateThrottled(["scanner"], 10_000);
          payload.symbols.forEach((symbol) => {
            invalidateThrottled(["coin", symbol], 5_000);
          });
          return;
        }

        if (payload.type === "signal") {
          invalidateThrottled(["dashboard"], 2_000);
          invalidateThrottled(["scanner"], 2_000);
          queryClient.invalidateQueries({ queryKey: ["alerts"] });
          payload.symbols.forEach((symbol) => {
            invalidateThrottled(["coin", symbol], 2_000);
          });
          return;
        }

        invalidateThrottled(["dashboard"], 5_000);
        payload.symbols.forEach((symbol) => {
          invalidateThrottled(["coin", symbol], 5_000);
        });
      };

      websocket.onclose = () => {
        if (!active) {
          return;
        }
        retryTimer = setTimeout(connect, 3000);
      };

      websocket.onerror = () => {
        websocket?.close();
      };
    };

    connect();

    return () => {
      active = false;
      if (retryTimer) {
        clearTimeout(retryTimer);
      }
      websocket?.close();
    };
  }, [queryClient]);
}
