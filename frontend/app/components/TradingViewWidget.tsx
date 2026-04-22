"use client";

import React, { useEffect, useRef, memo } from "react";

interface TradingViewWidgetProps {
  symbol: string;
}

function TradingViewWidget({ symbol }: TradingViewWidgetProps) {
  const container = useRef<HTMLDivElement>(null);
  const chartId = `tv_${symbol.toLowerCase()}_${Math.random().toString(36).substring(7)}`;

  useEffect(() => {
    // Prevent multiple injections
    if (!container.current || container.current.querySelector("script")) {
      return;
    }

    const tvSymbol = symbol.includes(":") ? symbol : `BINANCE:${symbol.toUpperCase()}`;

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.type = "text/javascript";
    script.async = true;
    script.onload = () => {
      if (typeof window !== "undefined" && (window as any).TradingView) {
        new (window as any).TradingView.widget({
          autosize: true,
          symbol: tvSymbol,
          interval: "15",
          timezone: "Etc/UTC",
          theme: "dark",
          style: "1",
          locale: "en",
          enable_publishing: false,
          backgroundColor: "rgba(11, 16, 32, 1)",
          gridColor: "rgba(255, 255, 255, 0.05)",
          hide_top_toolbar: false,
          hide_legend: false,
          save_image: false,
          container_id: chartId,
          toolbar_bg: "rgba(11, 16, 32, 1)",
        });
      }
    };
    container.current.appendChild(script);
  }, [symbol, chartId]);

  return (
    <div className="h-[500px] w-full rounded-2xl overflow-hidden border border-white/10 bg-[#0b1020]">
      <div id={chartId} ref={container} className="h-full w-full" />
    </div>
  );
}

export default memo(TradingViewWidget);
