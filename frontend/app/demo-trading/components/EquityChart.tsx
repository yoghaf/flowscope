"use client";

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { DemoTrade } from "@/lib/types";

interface EquityChartProps {
  trades: DemoTrade[];
  isLoading: boolean;
}

export default function EquityChart({ trades, isLoading }: EquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // 🔥 STEP 1: HAPUS CHART LAMA (WAJIB)
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    // 🔥 STEP 2: BERSIHKAN DOM
    containerRef.current.innerHTML = "";

    // 🔥 STEP 3: BUAT CHART BARU
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 300,
      layout: {
        background: { color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(148, 163, 184, 0.1)" },
        horzLines: { color: "rgba(148, 163, 184, 0.1)" },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: "rgba(148, 163, 184, 0.3)",
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderColor: "rgba(148, 163, 184, 0.3)",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // 🔥 STEP 4: SIMPAN KE REF (SETELAH CLEAN)
    chartRef.current = chart;

    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: "#3b82f6",
      topColor: "rgba(59, 130, 246, 0.4)",
      bottomColor: "rgba(59, 130, 246, 0.0)",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    seriesRef.current = areaSeries;

    // Handle resize
    const handleResize = () => {
      if (containerRef.current && chart) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    // 🔥 CLEANUP FINAL
    return () => {
      window.removeEventListener("resize", handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !trades.length) return;

    // RULE 7: NO FALLBACK - Get starting balance from first trade or use 0
    // Never use hardcoded $10,000
    let equity = 0; // Start from 0, will be calculated from trades
    const equityData: { time: UTCTimestamp; value: number }[] = [];

    const sortedTrades = [...trades].sort(
      (a, b) =>
        new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime(),
    );

    sortedTrades.forEach((trade, index) => {
      if (index === 0) {
        // First trade: initialize equity from entry value
        equity = (trade.entry_price || 0) * (trade.size || 0);
        equityData.push({
          time: Math.floor(
            new Date(trade.entry_time).getTime() / 1000,
          ) as UTCTimestamp,
          value: equity,
        });
      }

      if (trade.exit_time && trade.pnl) {
        equity += trade.pnl;
        equityData.push({
          time: Math.floor(
            new Date(trade.exit_time).getTime() / 1000,
          ) as UTCTimestamp,
          value: equity,
        });
      }
    });

    seriesRef.current.setData(equityData);
  }, [trades]);

  if (isLoading) {
    return (
      <div className="flex h-[300px] items-center justify-center rounded-2xl border border-white/10 bg-card/50">
        <p className="text-muted-foreground">Loading equity curve...</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-card/50 p-6 backdrop-blur">
      <h3 className="mb-4 text-lg font-semibold text-foreground">
        Equity Curve
      </h3>
      <div ref={containerRef} className="h-[300px] w-full" />
    </div>
  );
}
