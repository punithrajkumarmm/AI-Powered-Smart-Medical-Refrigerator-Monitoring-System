import { useEffect, useState } from "react";
import { deleteDevice, deleteAllDevices, fetchDeviceAlerts, fetchDeviceHistory, fetchDeviceForecast, fetchDevices, simulateTelemetry, renameDevice, fetchDeviceCompliance, askDeviceQuestion } from "./api";
import { AlertHistoryItem, DashboardStatus, ForecastResponse, TelemetryReading } from "./types";
import { TelemetryChart, ForecastChart, AlertTrendChart, RiskGauge } from "./TelemetryChart";
import "./dashboard.css";

const scenarios = [
  { key: "normal", label: "Normal" },
  { key: "door_open", label: "Door Open" },
  { key: "high_temperature", label: "High Temp" },
  { key: "high_humidity", label: "High Humidity" },
  { key: "power_loss", label: "Power Loss" },
];

function App() {
  const [devices, setDevices] = useState<DashboardStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [deviceId, setDeviceId] = useState("fridge-001");
  const [simulationMessage, setSimulationMessage] = useState<string | null>(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState("fridge-001");
  const [alertHistory, setAlertHistory] = useState<AlertHistoryItem[]>([]);
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryReading[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);
  const [showComplianceDeviceId, setShowComplianceDeviceId] = useState<string | null>(null);
  const [complianceData, setComplianceData] = useState<any | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [complianceError, setComplianceError] = useState<string | null>(null);
  const [qaQuestion, setQaQuestion] = useState("");
  const [qaHistory, setQaHistory] = useState<Array<{ question: string; answer: string }>>([]);
  const [qaLoading, setQaLoading] = useState(false);

  const [currentPage, setCurrentPage] = useState<"dashboard" | "forecast">("dashboard");
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState<string | null>(null);

  // New states for renaming
  const [renamingDeviceId, setRenamingDeviceId] = useState<string | null>(null);
  const [newDeviceName, setNewDeviceName] = useState<string>("");

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchDevices();
        setDevices(data);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message || "Failed to load devices.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  async function handleSimulate(scenario: string) {
    setSimulating(true);
    setSimulationMessage(null);
    setError(null);

    try {
      const reading = await simulateTelemetry(deviceId, scenario);
      setSimulationMessage(`Simulated ${scenario.replace("_", " ")} for ${reading.device_id}`);
      const refreshed = await fetchDevices();
      setDevices(refreshed);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message || "Simulation failed.");
    } finally {
      setSimulating(false);
    }
  }

  useEffect(() => {
    async function loadAlertHistory() {
      if (!selectedDeviceId) return;
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
        const message = err instanceof Error ? err.message : String(err);
        setHistoryError(message || "Failed to load history.");
      } finally {
        setHistoryLoading(false);
      }
    }

    loadAlertHistory();
  }, [selectedDeviceId, devices]);

  useEffect(() => {
    if (showComplianceDeviceId) {
      loadCompliance(showComplianceDeviceId);
    }
  }, [showComplianceDeviceId]);

  useEffect(() => {
    async function loadForecast() {
      if (currentPage !== "forecast" || !selectedDeviceId) {
        return;
      }

      setForecastLoading(true);
      setForecastError(null);
      setForecastData(null);

      try {
        const data = await fetchDeviceForecast(selectedDeviceId);
        setForecastData(data);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setForecastError(message || "Failed to load forecast.");
      } finally {
        setForecastLoading(false);
      }
    }

    loadForecast();
  }, [currentPage, selectedDeviceId]);

  // Hash-based routing for compliance page: #/compliance/:deviceId
  useEffect(() => {
    function handleHash() {
      const h = window.location.hash || "";
      if (h.startsWith("#/compliance/")) {
        const id = decodeURIComponent(h.replace("#/compliance/", ""));
        setShowComplianceDeviceId(id);
      } else {
        setShowComplianceDeviceId(null);
        setComplianceData(null);
      }
    }

    window.addEventListener("hashchange", handleHash);
    handleHash();
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);

  async function handleDeleteDevice(deviceId: string) {
    if (!confirm(`Delete device ${deviceId}?`)) return;
    try {
      await deleteDevice(deviceId);
      setDeleteMessage(`Device ${deviceId} deleted successfully`);
      const refreshed = await fetchDevices();
      setDevices(refreshed);
    } catch (err) {
      setError("Failed to delete device");
    }
  }

  async function handleDeleteAllDevices() {
    if (!confirm("Delete all devices?")) return;
    try {
      await deleteAllDevices();
      setDeleteMessage("All devices deleted successfully");
      setDevices([]);
    } catch (err) {
      setError("Failed to delete all devices");
    }
  }

  async function handleRenameDevice(oldDeviceId: string) {
    if (!newDeviceName.trim()) {
      setError("New device name cannot be empty.");
      return;
    }
    if (oldDeviceId === newDeviceName.trim()) {
      setError("New device name cannot be the same as the old one.");
      return;
    }

    setError(null); // Clear previous errors

    try {
      await renameDevice(oldDeviceId, newDeviceName.trim());
      setDeleteMessage(`Device ${oldDeviceId} renamed to ${newDeviceName.trim()} successfully.`); // Reusing deleteMessage for simplicity
      setRenamingDeviceId(null); // Exit renaming mode
      setNewDeviceName(""); // Clear input
      const refreshed = await fetchDevices();
      setDevices(refreshed);
      if (selectedDeviceId === oldDeviceId) {
        setSelectedDeviceId(newDeviceName.trim());
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message || "Failed to rename device.");
    }
  }

  function getChartPath(values: number[], width: number, height: number): string {
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

  async function loadCompliance(deviceId: string) {
    setComplianceLoading(true);
    setComplianceError(null);
    try {
      const data = await fetchDeviceCompliance(deviceId);
      setComplianceData(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setComplianceError(message || "Failed to load compliance.");
    } finally {
      setComplianceLoading(false);
    }
  }

  async function handleAskQuestion(e: React.FormEvent) {
    e.preventDefault();
    if (!qaQuestion.trim() || !showComplianceDeviceId) return;

    setQaLoading(true);
    try {
      const response = await askDeviceQuestion(showComplianceDeviceId, qaQuestion);
      setQaHistory([...qaHistory, { question: qaQuestion, answer: response.answer }]);
      setQaQuestion("");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      alert(`Error: ${message}`);
    } finally {
      setQaLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <nav className="top-nav">
        <div className="brand">
          <div className="logo">MR</div>
          <div className="brand-text">
            <div className="brand-title">Medical Refrigerator</div>
            <div className="brand-sub">Monitoring</div>
          </div>
        </div>

        <ul className="nav-links">
          <li className={currentPage === "dashboard" ? "active" : ""} onClick={() => { setCurrentPage("dashboard"); window.location.hash = ""; }}>
            Dashboard
          </li>
          <li onClick={() => { window.scrollTo({ top: 0, behavior: 'smooth' }); setCurrentPage("dashboard"); window.location.hash = ""; }}>
            Devices
          </li>
          <li onClick={() => { document.querySelector('.simulation-panel')?.scrollIntoView({ behavior: 'smooth' }); setCurrentPage("dashboard"); window.location.hash = ""; }}>
            Simulator
          </li>
          <li className={currentPage === "forecast" ? "active" : ""} onClick={() => { setCurrentPage("forecast"); window.location.hash = ""; }}>
            Forecast
          </li>
          <li onClick={() => window.location.hash = `#/compliance/${encodeURIComponent(selectedDeviceId)}`}>Compliance</li>
        </ul>

        <div className="nav-actions">
          <input className="nav-search" placeholder="Search devices, e.g. fridge-001" />
          <button className="profile-btn">Admin</button>
        </div>
      </nav>
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
      {currentPage === "forecast" ? (
        <section className="forecast-panel">
          <h2>Temperature Forecast</h2>
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

          {forecastLoading && <div className="status-message">Loading forecast...</div>}
          {forecastError && <div className="status-message error">{forecastError}</div>}

          {forecastData && (
            <>
              <div className="forecast-summary-grid">
                <div className="forecast-card">
                  <h3>Current Temp</h3>
                  <p>{forecastData.current_temperature.toFixed(1)} °C</p>
                </div>
                <div className="forecast-card">
                  <h3>Predicted Max</h3>
                  <p>{forecastData.predicted_max.toFixed(1)} °C</p>
                </div>
                <div className="forecast-card">
                  <h3>Predicted Min</h3>
                  <p>{forecastData.predicted_min.toFixed(1)} °C</p>
                </div>
                <div className="forecast-card">
                  <h3>Trend</h3>
                  <p>{forecastData.trend} ({forecastData.avg_trend.toFixed(2)} °C/hr)</p>
                </div>
              </div>

              {forecastData.risk_alert ? (
                <div className="status-message error">
                  <strong>Warning:</strong> {forecastData.alert_message}
                </div>
              ) : (
                <div className="status-message">
                  {forecastData.alert_message}
                </div>
              )}

              <div className="history-chart">
                <ForecastChart data={forecastData.forecast} title={`24-Hour Forecast for ${forecastData.device_id}`} height={380} />
              </div>

              <div className="forecast-list">
                <h3>Hourly Forecast</h3>
                <div className="forecast-grid">
                  {forecastData.forecast.map((point) => (
                    <div key={point.timestamp} className="forecast-row">
                      <strong>{new Date(point.timestamp).toLocaleString()}</strong>
                      <span>{point.temperature_c.toFixed(1)} °C</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </section>
      ) : (
        <>
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
                <TelemetryChart
                  data={telemetryHistory}
                  title="Temperature and Humidity Trend"
                  height={400}
                />
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
      {deleteMessage && <div className="status-message">{deleteMessage}</div>}

      {devices.length > 0 && (
        <button className="delete-all-btn" onClick={handleDeleteAllDevices}>
          Delete All Devices
        </button>
      )}

      <div className="device-grid">
        {devices.map((device) => (
          <section key={device.device_id} className={`device-card ${device.healthy ? "healthy" : "alert"}`}>
            <h2>{device.device_id}</h2>
            <div className="device-row">
              <strong>Temperature:</strong> {device.last_reading.temperature_c.toFixed(1)} °C
            </div>
            <div className="device-row">
              <strong>Humidity:</strong> {device.last_reading.humidity_pct.toFixed(0)}%
            </div>
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
            <div className="device-actions">
              <button
                className="compliance-btn"
                onClick={() => {
                  window.location.hash = `#/compliance/${encodeURIComponent(device.device_id)}`;
                }}
              >
                AI Compliance
              </button>
              {renamingDeviceId === device.device_id ? (
                <div className="rename-controls">
                  <input
                    type="text"
                    value={newDeviceName}
                    onChange={(e) => setNewDeviceName(e.target.value)}
                    placeholder="New device ID"
                  />
                  <button onClick={() => handleRenameDevice(device.device_id)}>Confirm</button>
                  <button onClick={() => { setRenamingDeviceId(null); setNewDeviceName(""); setError(null); }}>Cancel</button>
                </div>
              ) : (
                <button
                  className="rename-btn"
                  onClick={() => {
                    setRenamingDeviceId(device.device_id);
                    setNewDeviceName(device.device_id); // Pre-fill with current name
                  }}
                >
                  Rename
                </button>
              )}
              <button
                className="delete-btn"
                onClick={() => handleDeleteDevice(device.device_id)}
              >
                Delete
              </button>
            </div>
          </section>
        ))}
      </div>
    </>
  )}

      {showComplianceDeviceId && (
        <div className="compliance-page">
          <div className="compliance-card">
            <header>
              <h2>AI Compliance Assistant — {showComplianceDeviceId}</h2>
              <button className="close-btn" onClick={() => (window.location.hash = "")}>Back</button>
            </header>

            {complianceLoading && <div className="status-message">Loading compliance...</div>}
            {complianceError && <div className="status-message error">{complianceError}</div>}

            {!complianceLoading && complianceData && (
              <>
                <section className="compliance-summary">
                  <h3>Why is {showComplianceDeviceId} at risk?</h3>
                  <div className="compliance-risk-factors">
                    {complianceData.details.temperature_exceed_hours > 0 && (
                      <p>• Temperature exceeded 8°C for {complianceData.details.temperature_exceed_hours} hours.</p>
                    )}
                    {complianceData.details.door_open_count > 0 && (
                      <p>• Door opened {complianceData.details.door_open_count} times.</p>
                    )}
                    {complianceData.details.compressor_vibration_pct > 0 && (
                      <p>• Compressor vibration increased by {complianceData.details.compressor_vibration_pct}%.</p>
                    )}
                    <p><strong>• Predicted Spoilage Risk = {complianceData.details.predicted_spoilage_risk}%.</strong></p>
                  </div>
                  {complianceData.summary && (
                    <div className="compliance-ai-summary">
                      <h4>AI Analysis</h4>
                      <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "0.95rem" }}>{complianceData.summary}</pre>
                    </div>
                  )}
                </section>

                <section className="compliance-tech">
                  <h4>Technologies</h4>
                  <p>• {complianceData.technologies.join("\n• ")}</p>
                </section>
                <section className="compliance-qa">
                  <h4>Ask a Question</h4>
                  <form onSubmit={handleAskQuestion} className="qa-form">
                    <input
                      type="text"
                      placeholder="Ask about this device's compliance..."
                      value={qaQuestion}
                      onChange={(e) => setQaQuestion(e.target.value)}
                      disabled={qaLoading}
                      className="qa-input"
                    />
                    <button type="submit" disabled={qaLoading || !qaQuestion.trim()} className="qa-submit">
                      {qaLoading ? "Thinking..." : "Ask"}
                    </button>
                  </form>

                  {qaHistory.length > 0 && (
                    <div className="qa-history">
                      <h5>Q&A History</h5>
                      {qaHistory.map((qa, idx) => (
                        <div key={idx} className="qa-item">
                          <p className="qa-question"><strong>Q: {qa.question}</strong></p>
                          <p className="qa-answer">A: {qa.answer}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </section>              </>
            )}

            {!complianceLoading && !complianceData && !complianceError && (
              <div className="status-message">No compliance data yet.</div>
            )}

            <footer>
              <button onClick={() => (window.location.hash = "")}>Close</button>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
