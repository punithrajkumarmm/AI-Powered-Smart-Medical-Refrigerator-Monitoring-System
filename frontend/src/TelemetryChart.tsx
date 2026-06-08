import React from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
  Bar,
} from "recharts";
import { TelemetryReading } from "./types";

interface TelemetryChartProps {
  data: TelemetryReading[];
  title: string;
  height?: number;
}

export const TelemetryChart: React.FC<TelemetryChartProps> = ({
  data,
  title,
  height = 400,
}) => {
  if (!data || data.length === 0) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "#666" }}>
        No data available for chart
      </div>
    );
  }

  const chartData = data.map((reading, index) => ({
    index,
    timestamp: new Date(reading.timestamp).toLocaleTimeString(),
    temperature_c: parseFloat(reading.temperature_c.toFixed(2)),
    humidity_pct: parseFloat(reading.humidity_pct.toFixed(2)),
    door_open: reading.door_open ? 1 : 0,
    power_ok: reading.power_ok ? 1 : 0,
  }));

  return (
    <div className="telemetry-chart-container">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={chartData}
          margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="timestamp"
            stroke="#666"
            tick={{ fontSize: 12 }}
            interval={Math.max(0, Math.floor(chartData.length / 8) - 1)}
          />
          <YAxis yAxisId="left" stroke="#ff8b3d" label={{ value: "Temp (°C)", angle: -90, position: "insideLeft" }} />
          <YAxis yAxisId="right" orientation="right" stroke="#0b89f8" label={{ value: "Humidity (%)", angle: 90, position: "insideRight" }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #ccc",
              borderRadius: "4px",
              padding: "8px",
            }}
            formatter={(value: any, name: string) => {
              if (name === "temperature_c") return [value.toFixed(2), "Temperature (°C)"];
              if (name === "humidity_pct") return [value.toFixed(1), "Humidity (%)"];
              if (name === "door_open") return [value === 1 ? "Open" : "Closed", "Door"];
              if (name === "power_ok") return [value === 1 ? "OK" : "Lost", "Power"];
              return value;
            }}
          />
          <Legend />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="temperature_c"
            stroke="#ff8b3d"
            strokeWidth={2}
            dot={false}
            name="Temperature (°C)"
            isAnimationActive
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="humidity_pct"
            stroke="#0b89f8"
            strokeWidth={2}
            dot={false}
            name="Humidity (%)"
            isAnimationActive
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

interface ForecastChartProps {
  data: Array<{ timestamp: string; temperature_c: number }>;
  title: string;
  height?: number;
}

export const ForecastChart: React.FC<ForecastChartProps> = ({
  data,
  title,
  height = 400,
}) => {
  if (!data || data.length === 0) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "#666" }}>
        No forecast data available.
      </div>
    );
  }

  const chartData = data.map((point, index) => ({
    index,
    timestamp: new Date(point.timestamp).toLocaleTimeString(),
    temperature_c: point.temperature_c,
  }));

  return (
    <div className="telemetry-chart-container">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="timestamp"
            stroke="#666"
            tick={{ fontSize: 12 }}
            interval={Math.max(0, Math.floor(chartData.length / 8) - 1)}
          />
          <YAxis stroke="#ff8b3d" label={{ value: "Temp (°C)", angle: -90, position: "insideLeft" }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #ccc",
              borderRadius: "4px",
              padding: "8px",
            }}
            formatter={(value: any, name: string) => [
              typeof value === "number" ? value.toFixed(2) : value,
              "Temperature (°C)",
            ]}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="temperature_c"
            stroke="#ff8b3d"
            strokeWidth={2}
            dot={false}
            name="Forecast Temp"
            isAnimationActive
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

interface AlertTrendChartProps {
  data: Array<{
    timestamp: string;
    alert_level: string;
    temperature_c: number;
  }>;
  title: string;
  height?: number;
}

export const AlertTrendChart: React.FC<AlertTrendChartProps> = ({
  data,
  title,
  height = 300,
}) => {
  if (!data || data.length === 0) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "#666" }}>
        No alert data available
      </div>
    );
  }

  const chartData = data.map((item, index) => ({
    index,
    timestamp: new Date(item.timestamp).toLocaleTimeString(),
    temperature_c: item.temperature_c,
    alert_level: item.alert_level,
    alertColor:
      item.alert_level === "critical"
        ? "#c92a2a"
        : item.alert_level === "warning"
        ? "#ff8b3d"
        : "#1f9d55",
  }));

  return (
    <div className="alert-chart-container">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="timestamp"
            stroke="#666"
            tick={{ fontSize: 12 }}
            interval={Math.max(0, Math.floor(chartData.length / 6) - 1)}
          />
          <YAxis stroke="#ff8b3d" label={{ value: "Temperature (°C)", angle: -90, position: "insideLeft" }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #ccc",
              borderRadius: "4px",
              padding: "8px",
            }}
            formatter={(value: any) => [
              typeof value === "number" ? value.toFixed(2) : value,
              "Temperature (°C)",
            ]}
          />
          <Area
            type="monotone"
            dataKey="temperature_c"
            fill="#ff8b3d"
            stroke="#ff6b1f"
            fillOpacity={0.6}
            name="Temperature (°C)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

// Modern Risk Score Gauge
export const RiskGauge: React.FC<{ risk: number; label: string }> = ({
  risk,
  label,
}) => {
  const getColor = (value: number) => {
    if (value >= 70) return "#c92a2a"; // red - critical
    if (value >= 40) return "#ff8b3d"; // orange - warning
    return "#1f9d55"; // green - ok
  };

  const getStatus = (value: number) => {
    if (value >= 70) return "CRITICAL";
    if (value >= 40) return "WARNING";
    return "NORMAL";
  };

  const circumference = 2 * Math.PI * 45;
  const strokeOffset = circumference - (risk / 100) * circumference;

  return (
    <div className="risk-gauge" style={{ textAlign: "center", padding: "20px" }}>
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle
          cx="60"
          cy="60"
          r="45"
          fill="none"
          stroke="#e0e0e0"
          strokeWidth="8"
        />
        <circle
          cx="60"
          cy="60"
          r="45"
          fill="none"
          stroke={getColor(risk)}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={strokeOffset}
          strokeLinecap="round"
          style={{ transform: "rotate(-90deg)", transformOrigin: "60px 60px" }}
        />
        <text
          x="60"
          y="55"
          textAnchor="middle"
          fontSize="24"
          fontWeight="bold"
          fill={getColor(risk)}
        >
          {Math.round(risk)}%
        </text>
        <text
          x="60"
          y="75"
          textAnchor="middle"
          fontSize="12"
          fill="#666"
        >
          {getStatus(risk)}
        </text>
      </svg>
      <p style={{ marginTop: "10px", fontWeight: "500", color: "#333" }}>
        {label}
      </p>
    </div>
  );
};
