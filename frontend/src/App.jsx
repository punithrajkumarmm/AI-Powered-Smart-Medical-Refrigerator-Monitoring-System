import { useEffect, useState } from "react";
import { fetchDeviceAlerts, fetchDeviceHistory, fetchDevices, simulateTelemetry } from "./api";
import "./dashboard.css";

const scenarios = [
  { key: "normal", label: "Normal" },
  { key: "door_open", label: "Door Open" },
  { key: "high_temperature", label: "High Temp" },
  { key: "high_humidity", label: "High Humidity" },
  { key: "power_loss", label: "Power Loss" },
];

function App() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const [deviceId, setDeviceId] = useState("fridge-001");
  const [simulationMessage, setSimulationMessage] = useState(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState("fridge-001");
  const [alertHistory, setAlertHistory] = useState([]);
  const [telemetryHistory, setTelemetryHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchDevices();
        setDevices(data);
      } catch (err) {
        setError(err?.message || "Failed to load devices.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  async function handleSimulate(scenario) {
    setSimulating(true);
    setSimulationMessage(null);
    setError(null);

    try {
      const reading = await simulateTelemetry(deviceId, scenario);
      setSimulationMessage(`Simulated ${scenario.replace("_", " ")} for ${reading.device_id}`);
      const refreshed = await fetchDevices();
      setDevices(refreshed);
    } catch (err) {
      setError(err?.message || "Simulation failed.");
    } finally {
      setSimulating(false);
    }
  }

  useEffect(() => {
    async function loadAlertHistory() {
      if (!selectedDeviceId) {
        return;
      }
      setHistoryLoading(true);
      setHistoryError(null);

      try {
        const [alerts, history] = await Promise.all([
          fetchDeviceAlerts(selectedDeviceId),
          fetchDeviceHistory(selectedDeviceId),
        ]);

        setAlertHistory(alerts);
        setTelemetryHistory(history);
      } catch (err) {
        setHistoryError(err?.message || "Failed to load history.");
      } finally {
        setHistoryLoading(false);
      }
    }

    loadAlertHistory();
  }, [selectedDeviceId, devices]);

  function getChartPath(values, width, height) {
    if (values.length === 0) {
      return "";
    }

    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const range = maxValue === minValue ? 1 : maxValue - minValue;
    const padding = 24;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    return values
      .map((value, index) => {
        const x = padding + (chartWidth * (values.length === 1 ? 0.5 : index / (values.length - 1)));
        const y = padding + chartHeight - ((value - minValue) / range) * chartHeight;
        return `${index === 0 ? "M" : "L"}${x},${y}`;
      })
      .join(" ");
  }

  return (
    <div className="app-shell">
      <section className="simulation-panel">
        <h2>Telemetry Simulator</h2>
        <div className="simulation-controls">
          <label>
            Device ID
            <input
              value={deviceId}
              onChange={(event) => setDeviceId(event.target.value)}
              placeholder="fridge-001"
            />
          </label>
          <div className="scenario-buttons">
            {scenarios.map((scenario) => (
              <button
                key={scenario.key}
                onClick={() => handleSimulate(scenario.key)}
                disabled={simulating}
              >
                {scenario.label}
              </button>
            ))}
          </div>
          {simulationMessage && <div className="status-message">{simulationMessage}</div>}
        </div>
      </section>
      <section className="history-panel">
        <h2>Device History</h2>
        <div className="history-controls">
          <label>
            Device
            <select value={selectedDeviceId} onChange={(event) => setSelectedDeviceId(event.target.value)}>
              {devices.map((device) => (
                <option key={device.device_id} value={device.device_id}>
                  {device.device_id}
                </option>
              ))}
            </select>
          </label>
        </div>

        {historyLoading && <div className="status-message">Loading device history...</div>}
        {historyError && <div className="status-message error">{historyError}</div>}

        {!historyLoading && !telemetryHistory.length && !historyError && (
          <div className="status-message">No telemetry history found for this device.</div>
        )}

        {telemetryHistory.length > 0 && (
          <div className="history-chart">
            <div className="chart-header">
              <span>Temperature and Humidity Trend</span>
              <div className="chart-legend">
                <span className="legend-item temp">Temperature</span>
                <span className="legend-item humidity">Humidity</span>
              </div>
            </div>
            <svg viewBox="0 0 720 180" className="chart-svg">
              <path
                d={getChartPath(telemetryHistory.map((reading) => reading.temperature_c), 720, 140)}
                fill="none"
                stroke="#ff8b3d"
                strokeWidth="3"
              />
              <path
                d={getChartPath(telemetryHistory.map((reading) => reading.humidity_pct), 720, 140)}
                fill="none"
                stroke="#0f4c81"
                strokeWidth="3"
              />
            </svg>
          </div>
        )}

        <div className="history-list">
          {alertHistory.map((alert) => (
            <section key={`${alert.device_id}-${alert.timestamp}`} className="history-card">
              <div className="history-header">
                <strong>{new Date(alert.timestamp).toLocaleString()}</strong>
                <span className={`alert-level ${alert.alert_level}`}>{alert.alert_level.toUpperCase()}</span>
              </div>
              <p>{alert.message}</p>
              <div className="device-row">
                <strong>Temp:</strong> {alert.temperature_c.toFixed(1)} °C
              </div>
              <div className="device-row">
                <strong>Humidity:</strong> {alert.humidity_pct.toFixed(0)}%</div>
              <div className="device-row">
                <strong>Door:</strong> {alert.door_open ? "Open" : "Closed"}
              </div>
              <div className="device-row">
                <strong>Power:</strong> {alert.power_ok ? "OK" : "Lost"}
              </div>
            </section>
          ))}
        </div>
      </section>
      <header className="app-header">
        <h1>Medical Refrigerator Monitoring</h1>
        <p>Live device status and alerts for cold chain medical storage.</p>
      </header>

      {loading && <div className="status-message">Loading dashboard...</div>}
      {error && <div className="status-message error">{error}</div>}

      <div className="device-grid">
        {devices.map((device) => (
          <section key={device.device_id} className={`device-card ${device.healthy ? "healthy" : "alert"}`}>
            <h2>{device.device_id}</h2>
            <div className="device-row">
              <strong>Temperature:</strong> {device.last_reading.temperature_c.toFixed(1)} °C
            </div>
            <div className="device-row">
              <strong>Humidity:</strong> {device.last_reading.humidity_pct.toFixed(0)}%</div>
            <div className="device-row">
              <strong>Door Open:</strong> {device.last_reading.door_open ? "Yes" : "No"}
            </div>
            <div className="device-row">
              <strong>Power OK:</strong> {device.last_reading.power_ok ? "Yes" : "No"}
            </div>
            <div className="device-row">
              <strong>Last updated:</strong> {new Date(device.last_reading.timestamp).toLocaleString()}
            </div>

            {device.alert_status ? (
              <div className="alert-banner">
                <span className="alert-level">{device.alert_status.alert_level.toUpperCase()}</span>
                <p>{device.alert_status.message}</p>
              </div>
            ) : (
              <div className="healthy-banner">All systems normal</div>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}

export default App;
