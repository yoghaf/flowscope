"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CandlestickSeries, type Time } from "lightweight-charts";
import { api } from "@/lib/api";

interface SignalChartProps {
  symbol: string;
  entryPrice: number;
  tp1?: number;
  tp2?: number;
  sl?: number;
  bias: "Bullish" | "Bearish";
  timeframe: string;
  signalTime: string;
}

interface Kline {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
}

export function SignalChart({ symbol, entryPrice, tp1, tp2, sl, bias, timeframe, signalTime }: SignalChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Convert internal timeframe to Binance interval
    const intervalMap: Record<string, "15m" | "1h" | "4h" | "1d"> = {
      "15m": "15m",
      "1h": "1h",
      "4h": "4h",
      "24h": "1d",
    };
    const interval = intervalMap[timeframe] || "15m";

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9CA3AF", // Tailwind gray-400
      },
      grid: {
        vertLines: { color: "#1F2937" }, // Tailwind gray-800
        horzLines: { color: "#1F2937" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderVisible: false,
      },
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10B981", // Tailwind emerald-500
      downColor: "#F43F5E", // Tailwind rose-500
      borderVisible: false,
      wickUpColor: "#10B981",
      wickDownColor: "#F43F5E",
    });

    // Fetch data from Binance API
    const fetchKlines = async () => {
      try {
        setLoading(true);
        const cleanSymbol = symbol.replace(/[^A-Z0-9]/g, "").toUpperCase();
        const data = await api.getSignalKlines({
          symbol: cleanSymbol,
          interval,
          limit: 1000,
        });

        const klines: Kline[] = data.items.map((item) => ({
          time: item.time as Time,
          open: item.open,
          high: item.high,
          low: item.low,
          close: item.close,
        }));

        candlestickSeries.setData(klines);

        // Add Price Lines
        candlestickSeries.createPriceLine({
          price: entryPrice,
          color: "#3B82F6", // Blue
          lineWidth: 2,
          lineStyle: 2, // Dashed
          axisLabelVisible: true,
          title: "Entry",
        });

        if (tp1) {
          candlestickSeries.createPriceLine({
            price: tp1,
            color: "#10B981", // Emerald
            lineWidth: 1,
            lineStyle: 1, // Dotted
            axisLabelVisible: true,
            title: "TP1",
          });
        }

        if (tp2) {
          candlestickSeries.createPriceLine({
            price: tp2,
            color: "#059669", // Emerald darker
            lineWidth: 2,
            lineStyle: 0, // Solid
            axisLabelVisible: true,
            title: "TP2",
          });
        }

        if (sl) {
          candlestickSeries.createPriceLine({
            price: sl,
            color: "#F43F5E", // Rose
            lineWidth: 2,
            lineStyle: 0, // Solid
            axisLabelVisible: true,
            title: "SL",
          });
        }


        // Auto scale and fit content
        chart.timeScale().fitContent();

        setLoading(false);
      } catch (err: any) {
        console.error("Failed to load chart data:", err);
        setError(err.message);
        setLoading(false);
      }
    };

    fetchKlines();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [symbol, timeframe, entryPrice, tp1, tp2, sl, bias, signalTime]);

  return (
    <div className="relative w-full h-[400px] bg-slate-900 rounded-xl overflow-hidden border border-slate-800">
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-sm text-slate-400 font-medium">Loading Live Chart...</p>
          </div>
        </div>
      )}
      {error && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-900/90">
          <div className="text-center">
            <p className="text-rose-400 font-semibold mb-1">Chart Data Unavailable</p>
            <p className="text-xs text-slate-500">{error}</p>
          </div>
        </div>
      )}
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
}
