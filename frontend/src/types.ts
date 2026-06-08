export interface TelemetryReading {
  device_id: string;
  timestamp: string;
  temperature_c: number;
  humidity_pct: number;
  door_open: boolean;
  power_ok: boolean;
}

export interface AlertStatus {
  device_id: string;
  alert_level: string;
  message: string;
  triggered_at: string;
}

export interface AlertHistoryItem {
  device_id: string;
  timestamp: string;
  alert_level: string;
  message: string;
  temperature_c: number;
  humidity_pct: number;
  door_open: boolean;
  power_ok: boolean;
}

export interface DashboardStatus {
  device_id: string;
  last_reading: TelemetryReading;
  alert_status: AlertStatus | null;
  healthy: boolean;
}

export interface ForecastPoint {
  timestamp: string;
  temperature_c: number;
}

export interface ForecastResponse {
  device_id: string;
  current_temperature: number;
  predicted_max: number;
  predicted_min: number;
  avg_trend: number;
  trend: string;
  risk_alert: boolean;
  alert_message: string;
  forecast: ForecastPoint[];
}
