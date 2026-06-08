import { AlertHistoryItem, DashboardStatus, ForecastResponse, TelemetryReading } from "./types";

const API_BASE = process.env.REACT_APP_API_BASE || window.location.origin;

export async function fetchDevices(): Promise<DashboardStatus[]> {
  const response = await fetch(`${API_BASE}/devices`);
  if (!response.ok) {
    throw new Error("Unable to load device dashboard data.");
  }
  return response.json();
}

export async function postTelemetry(reading: TelemetryReading): Promise<TelemetryReading> {
  const response = await fetch(`${API_BASE}/telemetry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(reading),
  });

  if (!response.ok) {
    throw new Error("Telemetry submission failed.");
  }

  return response.json();
}

export async function simulateTelemetry(deviceId: string, scenario: string): Promise<TelemetryReading> {
  const response = await fetch(`${API_BASE}/simulate?device_id=${encodeURIComponent(deviceId)}&scenario=${encodeURIComponent(scenario)}`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Telemetry simulation failed.");
  }

  return response.json();
}

export async function fetchDeviceAlerts(deviceId: string): Promise<AlertHistoryItem[]> {
  const response = await fetch(`${API_BASE}/devices/${encodeURIComponent(deviceId)}/alerts`);
  if (!response.ok) {
    throw new Error("Unable to load device alert history.");
  }

  return response.json();
}

export async function fetchDeviceHistory(deviceId: string): Promise<TelemetryReading[]> {
  const response = await fetch(`${API_BASE}/devices/${encodeURIComponent(deviceId)}/history`);
  if (!response.ok) {
    throw new Error("Unable to load device telemetry history.");
  }

  return response.json();
}

export async function fetchDeviceCompliance(deviceId: string): Promise<any> {
  const response = await fetch(`${API_BASE}/devices/${encodeURIComponent(deviceId)}/compliance`);
  if (!response.ok) {
    throw new Error("Unable to load device compliance summary.");
  }

  return response.json();
}

export async function askDeviceQuestion(deviceId: string, question: string): Promise<any> {
  const response = await fetch(`${API_BASE}/devices/${encodeURIComponent(deviceId)}/compliance-question`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!response.ok) {
    throw new Error("Unable to get answer from AI.");
  }

  return response.json();
}

export async function fetchDeviceForecast(deviceId: string): Promise<ForecastResponse> {
  const response = await fetch(`${API_BASE}/devices/${encodeURIComponent(deviceId)}/forecast`);
  if (!response.ok) {
    throw new Error("Unable to load device forecast.");
  }

  return response.json();
}

export async function renameDevice(oldDeviceId: string, newDeviceId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/devices/${encodeURIComponent(oldDeviceId)}/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_device_id: newDeviceId }),
  });
  if (!response.ok) {
    throw new Error("Unable to rename device.");
  }
}

export async function deleteDevice(deviceId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/devices/${encodeURIComponent(deviceId)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete device.");
  }
}

export async function deleteAllDevices(): Promise<void> {
  const response = await fetch(`${API_BASE}/devices`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete all devices.");
  }
}
