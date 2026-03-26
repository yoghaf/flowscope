"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCompactNumber, formatFundingRate } from "@/lib/formatters";
import type {
  FundingPoint,
  LiquidationPoint,
  PriceOpenInterestPoint,
  VolumePoint,
} from "@/lib/types";

const tooltipStyle = {
  backgroundColor: "#0F1419",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: "12px",
  color: "#F8FAFC",
};

function timeLabel(timestamp: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

function hasNonZeroSeries<T extends Record<string, unknown>>(data: T[], keys: string[]): boolean {
  return data.some((point) =>
    keys.some((key) => {
      const value = point[key];
      return typeof value === "number" && Number.isFinite(value) && Math.abs(value) > 0;
    }),
  );
}

function EmptyChartState({ message }: { message: string }) {
  return (
    <div className="flex h-[300px] items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/5 text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function PriceOpenInterestChart({ data }: { data: PriceOpenInterestPoint[] }) {
  const chartData = data.map((point) => ({
    ...point,
    time: timeLabel(point.timestamp),
  }));

  if (!chartData.length) {
    return <EmptyChartState message="Price and open interest history is not available yet." />;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis dataKey="time" stroke="#94A3B8" style={{ fontSize: 11 }} />
        <YAxis yAxisId="left" stroke="#3B82F6" style={{ fontSize: 11 }} />
        <YAxis
          yAxisId="right"
          orientation="right"
          stroke="#10B981"
          style={{ fontSize: 11 }}
          tickFormatter={(value) => formatCompactNumber(value)}
        />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line yAxisId="left" type="monotone" dataKey="price" stroke="#3B82F6" strokeWidth={2.5} dot={false} name="Price" />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="open_interest"
          stroke="#10B981"
          strokeWidth={2.5}
          dot={false}
          name="Open Interest"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function VolumeChart({ data }: { data: VolumePoint[] }) {
  const chartData = data.map((point) => ({
    ...point,
    time: timeLabel(point.timestamp),
  }));

  if (!chartData.length || !hasNonZeroSeries(chartData, ["spot_volume", "futures_volume"])) {
    return <EmptyChartState message="Volume history is not available yet." />;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis dataKey="time" stroke="#94A3B8" style={{ fontSize: 11 }} />
        <YAxis stroke="#94A3B8" style={{ fontSize: 11 }} tickFormatter={(value) => formatCompactNumber(value)} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="spot_volume" fill="#3B82F6" radius={[6, 6, 0, 0]} name="Spot Volume" />
        <Bar dataKey="futures_volume" fill="#8B5CF6" radius={[6, 6, 0, 0]} name="Futures Volume" />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function FundingChart({ data }: { data: FundingPoint[] }) {
  const chartData = data.map((point) => ({
    ...point,
    time: timeLabel(point.timestamp),
  }));

  if (!chartData.length || !hasNonZeroSeries(chartData, ["funding_rate"])) {
    return <EmptyChartState message="Funding history is not available yet." />;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData}>
        <defs>
          <linearGradient id="fundingGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis dataKey="time" stroke="#94A3B8" style={{ fontSize: 11 }} />
        <YAxis stroke="#94A3B8" style={{ fontSize: 11 }} tickFormatter={(value) => formatFundingRate(value)} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area type="monotone" dataKey="funding_rate" stroke="#F59E0B" strokeWidth={2.5} fill="url(#fundingGradient)" name="Funding Rate" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function LiquidationChart({ data }: { data: LiquidationPoint[] }) {
  const chartData = data.map((point) => ({
    ...point,
    time: timeLabel(point.timestamp),
  }));

  if (!chartData.length || !hasNonZeroSeries(chartData, ["long_liquidations", "short_liquidations"])) {
    return <EmptyChartState message="No liquidation events recorded in this window yet." />;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis dataKey="time" stroke="#94A3B8" style={{ fontSize: 11 }} />
        <YAxis stroke="#94A3B8" style={{ fontSize: 11 }} tickFormatter={(value) => formatCompactNumber(value)} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="long_liquidations" fill="#EF4444" radius={[6, 6, 0, 0]} name="Long Liquidations" />
        <Bar dataKey="short_liquidations" fill="#10B981" radius={[6, 6, 0, 0]} name="Short Liquidations" />
      </BarChart>
    </ResponsiveContainer>
  );
}
