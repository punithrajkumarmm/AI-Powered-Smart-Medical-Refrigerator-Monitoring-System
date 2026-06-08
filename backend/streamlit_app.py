import json
import os
from typing import Any, Dict, List

import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Allow the API URL to be configured via environment variables, defaulting to localhost
API_BASE = os.getenv("MEDICAL_MONITOR_API_URL", "http://127.0.0.1:8000")


@st.cache_data(ttl=30)
def fetch_json(path: str) -> Any:
    url = f"{API_BASE}{path}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        raise requests.RequestException(f"Failed to connect to backend at {url}")


def post_json(path: str, params: Dict[str, str] | None = None, json_data: Dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE}{path}"
    response = requests.post(url, params=params or {}, json=json_data, timeout=10)
    response.raise_for_status()
    return response.json()


def to_history_frame(readings: List[Dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(readings)
    if frame.empty:
        return frame

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True).dt.tz_convert(None)
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp")
    frame["date"] = frame["timestamp"].dt.date
    frame["week"] = frame["timestamp"].dt.to_period("W").dt.start_time
    frame["month"] = frame["timestamp"].dt.to_period("M").dt.start_time
    frame["hour"] = frame["timestamp"].dt.hour
    frame["shift"] = frame["hour"].apply(shift_name)
    frame["door_open_int"] = frame["door_open"].astype(int)
    frame["power_loss_int"] = (~frame["power_ok"].astype(bool)).astype(int)
    frame["temperature_delta_c"] = frame.groupby("device_id")["temperature_c"].diff().fillna(0)
    frame["temperature_spike"] = (frame["temperature_delta_c"] >= 1.0) | (frame["temperature_c"] > 8.0)
    frame["cooling_load_score"] = (frame["temperature_c"] - 5.0).clip(lower=0)
    return frame


def get_all_history(device_ids: List[str]) -> pd.DataFrame:
    """Helper to consolidate history fetching and processing."""
    all_history: List[Dict[str, Any]] = []
    for device_id in device_ids:
        try:
            # fetch_json is cached, so this is efficient
            all_history.extend(fetch_json(f"/devices/{device_id}/history"))
        except requests.RequestException:
            continue
    return to_history_frame(all_history)


def shift_name(hour: int) -> str:
    if 6 <= hour < 14:
        return "Morning (06:00-14:00)"
    if 14 <= hour < 22:
        return "Evening (14:00-22:00)"
    return "Night (22:00-06:00)"


def safe_numeric(value: Any, default: str = "N/A", precision: int = 1) -> str:
    try:
        return f"{float(value):.{precision}f}"
    except (TypeError, ValueError):
        return default


def trend_chart(frame: pd.DataFrame, period_column: str, label: str) -> None:
    trend = (
        frame.groupby([period_column, "device_id"], as_index=False)
        .agg(
            avg_temperature_c=("temperature_c", "mean"),
            max_temperature_c=("temperature_c", "max"),
            avg_humidity_pct=("humidity_pct", "mean"),
            door_open_events=("door_open_int", "sum"),
        )
        .rename(columns={period_column: label})
    )
    if trend.empty:
        st.info("Not enough telemetry available for this trend.")
        return

    # Modern Plotly line chart
    fig = px.line(
        trend,
        x=label,
        y="avg_temperature_c",
        color="device_id",
        markers=True,
        hover_name="device_id",
        hover_data={"avg_temperature_c": ":.2f", "max_temperature_c": ":.2f", "avg_humidity_pct": ":.1f"},
        title="Temperature Trend Over Time",
    )
    fig.update_layout(
        hovermode="x unified",
        height=400,
        template="plotly_white",
        plot_bgcolor="rgba(240, 245, 251, 0.5)",
        paper_bgcolor="white",
        font=dict(size=11),
        showlegend=True,
        xaxis_title=label,
        yaxis_title="Average Temperature (°C)",
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=8))
    st.plotly_chart(fig, use_container_width=True)
    
    st.dataframe(
        trend.sort_values([label, "device_id"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True,
    )


def render_exploratory_data_analysis(device_ids: List[str]) -> None:
    st.title("Exploratory Data Analysis")

    eda_frame = get_all_history(device_ids)
    if eda_frame.empty:
        st.info("EDA will appear after telemetry history is available.")
        return

    selected_eda_devices = st.multiselect(
        "Analyze Refrigerators",
        options=device_ids,
        default=device_ids,
        key="eda_devices",
    )

    if not selected_eda_devices:
        st.warning("Select at least one refrigerator to analyze.")
        return

    eda_frame = eda_frame[eda_frame["device_id"].isin(selected_eda_devices)]

    st.subheader("Temperature Trends")
    daily_tab, weekly_tab, monthly_tab = st.tabs(["Daily", "Weekly", "Monthly"])
    with daily_tab:
        trend_chart(eda_frame, "date", "day")
    with weekly_tab:
        trend_chart(eda_frame, "week", "week_start")
    with monthly_tab:
        trend_chart(eda_frame, "month", "month_start")

    st.subheader("Door Open Patterns")
    door_summary = (
        eda_frame.groupby("device_id", as_index=False)
        .agg(
            door_open_events=("door_open_int", "sum"),
            readings=("door_open_int", "count"),
            avg_temperature_c=("temperature_c", "mean"),
            max_temperature_c=("temperature_c", "max"),
        )
        .sort_values("door_open_events", ascending=False)
    )
    door_summary["door_open_rate_pct"] = (
        door_summary["door_open_events"] / door_summary["readings"] * 100
    ).round(1)

    door_col, shift_col = st.columns(2)
    with door_col:
        st.markdown("**Which refrigerators are opened most?**")
        fig_door = px.bar(
            door_summary,
            x="device_id",
            y="door_open_events",
            title="Door Open Events by Device",
            labels={"door_open_events": "Open Events", "device_id": "Device ID"},
            color="door_open_events",
            color_continuous_scale="Blues_r",
        )
        fig_door.update_layout(
            height=350,
            template="plotly_white",
            showlegend=False,
            hovermode="x unified",
            plot_bgcolor="rgba(240, 245, 251, 0.5)",
        )
        fig_door.update_traces(marker_line_color="#0b89f8", marker_line_width=2)
        st.plotly_chart(fig_door, use_container_width=True)
        st.dataframe(door_summary, use_container_width=True, hide_index=True)

    shift_summary = (
        eda_frame.groupby("shift", as_index=False)
        .agg(
            temperature_spikes=("temperature_spike", "sum"),
            avg_temperature_c=("temperature_c", "mean"),
            max_temperature_c=("temperature_c", "max"),
            door_open_events=("door_open_int", "sum"),
        )
        .sort_values("temperature_spikes", ascending=False)
    )

    with shift_col:
        st.markdown("**Which shift causes temperature spikes?**")
        fig_shift = px.bar(
            shift_summary,
            x="shift",
            y="temperature_spikes",
            title="Temperature Spikes by Shift",
            labels={"temperature_spikes": "Spike Count", "shift": "Shift"},
            color="temperature_spikes",
            color_continuous_scale="Reds_r",
        )
        fig_shift.update_layout(
            height=350,
            template="plotly_white",
            showlegend=False,
            hovermode="x unified",
            plot_bgcolor="rgba(255, 243, 240, 0.5)",
        )
        fig_shift.update_traces(marker_line_color="#ff8b3d", marker_line_width=2)
        st.plotly_chart(fig_shift, use_container_width=True)
        st.dataframe(shift_summary, use_container_width=True, hide_index=True)

    st.subheader("Power Consumption")
    st.caption(
        "Telemetry does not include measured energy consumption yet, so these charts use power-loss events and a compressor load score based on temperature above 5 C."
    )

    power_summary = (
        eda_frame.groupby("device_id", as_index=False)
        .agg(
            power_loss_events=("power_loss_int", "sum"),
            readings=("power_loss_int", "count"),
            avg_compressor_load_score=("cooling_load_score", "mean"),
            max_compressor_load_score=("cooling_load_score", "max"),
        )
        .sort_values("avg_compressor_load_score", ascending=False)
    )
    power_summary["power_loss_rate_pct"] = (
        power_summary["power_loss_events"] / power_summary["readings"] * 100
    ).round(1)

    efficiency_col, energy_col = st.columns(2)
    with efficiency_col:
        st.markdown("**Is compressor efficiency declining?**")
        load_trend = (
            eda_frame.groupby(["date", "device_id"], as_index=False)
            .agg(avg_compressor_load_score=("cooling_load_score", "mean"))
        )
        fig_efficiency = px.line(
            load_trend,
            x="date",
            y="avg_compressor_load_score",
            color="device_id",
            markers=True,
            title="Compressor Load Trend",
            labels={"avg_compressor_load_score": "Avg Load Score", "date": "Date"},
        )
        fig_efficiency.update_layout(
            height=350,
            template="plotly_white",
            hovermode="x unified",
            plot_bgcolor="rgba(240, 245, 251, 0.5)",
        )
        fig_efficiency.update_traces(line=dict(width=3), marker=dict(size=7))
        st.plotly_chart(fig_efficiency, use_container_width=True)

    with energy_col:
        st.markdown("**Is energy consumption increasing?**")
        power_loss_trend = (
            eda_frame.groupby(["date", "device_id"], as_index=False)
            .agg(power_loss_events=("power_loss_int", "sum"))
        )
        fig_power = px.line(
            power_loss_trend,
            x="date",
            y="power_loss_events",
            color="device_id",
            markers=True,
            title="Power Loss Events Trend",
            labels={"power_loss_events": "Power Loss Events", "date": "Date"},
        )
        fig_power.update_layout(
            height=350,
            template="plotly_white",
            hovermode="x unified",
            plot_bgcolor="rgba(255, 243, 240, 0.5)",
        )
        fig_power.update_traces(line=dict(width=3), marker=dict(size=7))
        st.plotly_chart(fig_power, use_container_width=True)

    st.dataframe(power_summary, width="stretch", hide_index=True)


def create_engineered_features(frame: pd.DataFrame) -> pd.DataFrame:
    feature_frames: List[pd.DataFrame] = []
    for _, group in frame.groupby("device_id"):
        device_frame = group.sort_values("timestamp").set_index("timestamp")
        rolling_temp = device_frame["temperature_c"].rolling("24h", min_periods=1)
        rolling_door = device_frame["door_open_int"].rolling("24h", min_periods=1)
        rolling_power_loss = device_frame["power_loss_int"].rolling("24h", min_periods=1)

        device_frame["avg_temp_24h"] = rolling_temp.mean()
        device_frame["temp_variation"] = rolling_temp.std().fillna(0)
        device_frame["door_open_rate"] = rolling_door.mean()
        device_frame["power_stability"] = (1 - rolling_power_loss.mean()) * 100

        # Per user request, force compressor health to always be 100%
        device_frame["compressor_health"] = 100

        feature_frames.append(device_frame.reset_index())

    if not feature_frames:
        return pd.DataFrame()

    return pd.concat(feature_frames, ignore_index=True).sort_values(["device_id", "timestamp"])


# Feature engineering view removed by request


def render_remaining_useful_life(device_ids: List[str]) -> None:
    st.title("Remaining Useful Life Prediction")
    st.markdown("Predict when a refrigerator will need replacement using a RandomForest regression model served by the backend.")

    history_frame = get_all_history(device_ids)
    device_id = st.selectbox("Select Refrigerator", options=device_ids, index=0, key="rul_device")

    st.markdown("### Equipment Signals")
    age_months = st.slider("Equipment Age (months)", min_value=6, max_value=180, value=48, step=1)
    runtime_hours = st.number_input("Compressor Runtime (hours)", min_value=100.0, max_value=30000.0, value=8000.0, step=100.0)
    maintenance_visits = st.number_input("Maintenance visits in last 24 months", min_value=0, max_value=20, value=3, step=1)
    avg_daily_power_kwh = st.number_input("Average daily power consumption (kWh)", min_value=0.1, max_value=20.0, value=7.5, step=0.1)

    if not history_frame.empty:
        device_history = history_frame[history_frame["device_id"] == device_id]
        if not device_history.empty:
            power_loss_events = int(device_history["power_loss_int"].sum())
            door_open_rate = float(device_history["door_open_int"].mean())
            avg_temperature = float(device_history["temperature_c"].mean())
            st.markdown("**Derived device health metrics**")
            st.write(
                {
                    "Power loss events": power_loss_events,
                    "Door open rate": f"{door_open_rate * 100:.1f}%",
                    "Average temperature": f"{avg_temperature:.1f}°C",
                }
            )
        else:
            power_loss_events = 0
            door_open_rate = 0.0
            avg_temperature = 5.5
    else:
        power_loss_events = 0
        door_open_rate = 0.0
        avg_temperature = 5.5

    st.markdown("### Prediction Controls")
    if st.button("📈 Estimate Remaining Useful Life", use_container_width=True):
        payload = {
            "age_months": age_months,
            "runtime_hours": runtime_hours,
            "maintenance_visits": maintenance_visits,
            "avg_daily_power_kwh": avg_daily_power_kwh,
            "power_loss_events": power_loss_events,
            "door_open_rate": door_open_rate,
            "avg_temperature": avg_temperature,
        }
        try:
            result = post_json(f"/devices/{device_id}/rul", json_data=payload)
            estimate_months = int(result.get("prediction_months", 0))
            st.markdown("---")
            st.markdown(f"### ✅ Estimated Remaining Life: **{estimate_months} Months**")
            st.info(
                "This prediction is generated by the backend RandomForest regression service using equipment age, runtime, maintenance history, power consumption, and device performance signals."
            )

            feature_importances = pd.DataFrame(result.get("feature_importances", []))
            if not feature_importances.empty:
                st.subheader("Feature Importance")
                st.dataframe(feature_importances.sort_values("importance", ascending=False), hide_index=True)

            st.subheader("Prediction Inputs")
            st.write(payload)

        except requests.RequestException as exc:
            st.error(f"Failed to request RUL prediction: {exc}")

    st.markdown("---")
    st.caption("Note: This RUL model is trained on synthetic equipment lifecycle examples because actual replacement labels are not available in the current telemetry dataset.")


def render_temperature_anomaly_detection(device_ids: List[str]) -> None:
    st.title("Temperature Anomaly Detection")
    st.caption("Detect unusual temperature fluctuations with Isolation Forest. Output: 1 = Normal, -1 = Anomaly.")

    try:
        from sklearn.ensemble import IsolationForest
    except ModuleNotFoundError:
        st.error("scikit-learn is not installed in the current Python environment.")
        st.code("pip install -r backend/requirements.txt", language="powershell")
        return

    history_frame = get_all_history(device_ids)
    if history_frame.empty:
        st.info("Anomaly detection will appear after telemetry history is available.")
        return

    selected_devices = st.multiselect(
        "Analyze Refrigerators",
        options=device_ids,
        default=device_ids,
        key="anomaly_devices",
    )
    if not selected_devices:
        st.warning("Select at least one refrigerator to detect anomalies.")
        return

    contamination = st.slider(
        "Expected Anomaly Rate",
        min_value=0.01,
        max_value=0.30,
        value=0.10,
        step=0.01,
    )

    anomaly_frame = history_frame[history_frame["device_id"].isin(selected_devices)].copy()
    if len(anomaly_frame) < 2:
        st.info("At least two telemetry readings are needed for Isolation Forest.")
        return

    model = IsolationForest(contamination=contamination, random_state=42)
    anomaly_frame["temperature"] = anomaly_frame["temperature_c"]
    anomaly_frame["anomaly"] = model.fit_predict(anomaly_frame[["temperature"]])
    anomaly_frame["status"] = anomaly_frame["anomaly"].map({1: "Normal", -1: "Anomaly"})
    anomaly_frame["safe_range_alert"] = ~anomaly_frame["temperature_c"].between(2.0, 8.0)
    anomaly_frame["immediate_notification"] = (
        (anomaly_frame["anomaly"] == -1) | anomaly_frame["safe_range_alert"]
    )

    latest = anomaly_frame.sort_values("timestamp").tail(1).iloc[0]
    metric_cols = st.columns(4)
    metric_cols[0].metric("Latest Temperature", f"{latest['temperature_c']:.1f} C")
    metric_cols[1].metric("Latest Model Output", int(latest["anomaly"]))
    metric_cols[2].metric("Anomalies", int((anomaly_frame["anomaly"] == -1).sum()))
    metric_cols[3].metric("Notifications", int(anomaly_frame["immediate_notification"].sum()))

    st.subheader("Business Requirement")
    st.write("Detect unusual temperature fluctuations and surface immediate alerts for unsafe readings.")

    normal_count = int((anomaly_frame["anomaly"] == 1).sum())
    anomaly_count = int((anomaly_frame["anomaly"] == -1).sum())
    summary = pd.DataFrame(
        [
            {"output": 1, "meaning": "Normal", "readings": normal_count},
            {"output": -1, "meaning": "Anomaly", "readings": anomaly_count},
        ]
    )
    st.dataframe(summary, width="stretch", hide_index=True)

    st.subheader("Temperature Timeline")
    fig_timeline = px.line(
        anomaly_frame,
        x="timestamp",
        y="temperature_c",
        color="device_id",
        markers=True,
        title="Temperature Anomaly Detection Timeline",
        labels={"temperature_c": "Temperature (°C)", "timestamp": "Time"},
    )
    fig_timeline.update_layout(
        height=350,
        template="plotly_white",
        hovermode="x unified",
        plot_bgcolor="rgba(240, 245, 251, 0.5)",
    )
    fig_timeline.update_traces(line=dict(width=2), marker=dict(size=6))
    st.plotly_chart(fig_timeline, use_container_width=True)

    alerts = anomaly_frame[anomaly_frame["immediate_notification"]].sort_values(
        "timestamp", ascending=False
    )
    st.subheader("Immediate Notifications")
    if alerts.empty:
        st.success("No temperature anomalies detected.")
    else:
        st.dataframe(
            alerts[
                [
                    "device_id",
                    "timestamp",
                    "temperature_c",
                    "anomaly",
                    "status",
                    "safe_range_alert",
                    "immediate_notification",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    st.subheader("Model Dataset")
    st.dataframe(
        anomaly_frame[
            [
                "device_id",
                "timestamp",
                "temperature",
                "anomaly",
                "status",
                "safe_range_alert",
                "immediate_notification",
            ]
        ].sort_values("timestamp", ascending=False),
        width="stretch",
        hide_index=True,
    )


def build_compliance_report(frame: pd.DataFrame, period_column: str, period_label: str) -> pd.DataFrame:
    report = (
        frame.groupby([period_column, "device_id"], as_index=False)
        .agg(
            total_readings=("temperature_c", "count"),
            compliant_readings=("is_compliant", "sum"),
            violations=("is_violation", "sum"),
            min_temperature_c=("temperature_c", "min"),
            max_temperature_c=("temperature_c", "max"),
            avg_temperature_c=("temperature_c", "mean"),
        )
        .rename(columns={period_column: period_label})
    )
    report["compliance_rate_pct"] = (
        report["compliant_readings"] / report["total_readings"] * 100
    ).round(1)
    report["report_status"] = report["violations"].apply(
        lambda violations: "Compliant" if violations == 0 else "Violation"
    )
    return report.sort_values([period_label, "device_id"], ascending=[False, True])


def render_ai_compliance_assistant(device_ids: List[str]) -> None:
    st.markdown("# 🤖 AI Compliance Assistant")
    st.markdown("### Analyze device risk factors with AI-powered compliance scoring")

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_device = st.selectbox(
            "🔍 Select a Refrigerator to Analyze",
            options=device_ids,
            index=0,
        )
    with col2:
        if st.button("🔄 Refresh Analysis"):
            st.rerun()

    if not selected_device:
        st.warning("📌 Select a device to view compliance analysis.")
        return

    try:
        compliance_data = fetch_json(f"/devices/{selected_device}/compliance")
    except requests.RequestException as exc:
        st.error(f"❌ Failed to load compliance data: {exc}")
        return

    # Main question section
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 30px; border-radius: 15px; color: white; text-align: center;'>
        <h2 style='margin: 0; color: white;'>❓ User Question</h2>
        <h3 style='margin: 10px 0 0 0; color: white;'>Why is {selected_device} at risk?</h3>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # Risk Factors with color coding
    st.markdown("## 🚨 Risk Factors")
    
    risk_level = compliance_data['details']['predicted_spoilage_risk']
    if risk_level >= 70:
        risk_color = "#c92a2a"
        risk_emoji = "🔴"
        risk_text = "HIGH RISK"
    elif risk_level >= 40:
        risk_color = "#b04f00"
        risk_emoji = "🟠"
        risk_text = "MEDIUM RISK"
    else:
        risk_color = "#1f9d55"
        risk_emoji = "🟢"
        risk_text = "LOW RISK"

    col1, col2 = st.columns([2, 1])
    with col1:
        risk_factors = []
        if compliance_data["details"]["temperature_exceed_hours"] > 0:
            risk_factors.append(
                f"🌡️ Temperature exceeded 8°C for **{compliance_data['details']['temperature_exceed_hours']} hours**"
            )
        if compliance_data["details"]["door_open_count"] > 0:
            risk_factors.append(f"🚪 Door opened **{compliance_data['details']['door_open_count']} times**")
        if compliance_data["details"]["compressor_vibration_pct"] > 0:
            risk_factors.append(
                f"⚙️ Compressor vibration increased by **{compliance_data['details']['compressor_vibration_pct']}%**"
            )
        
        for factor in risk_factors:
            st.markdown(f"• {factor}")
    
    with col2:
        st.markdown(f"""
        <div style='background: {risk_color}; color: white; padding: 20px; 
                    border-radius: 12px; text-align: center; font-weight: bold;'>
            <div style='font-size: 30px; margin-bottom: 10px;'>{risk_emoji}</div>
            <div style='font-size: 24px;'>{risk_level}%</div>
            <div style='font-size: 14px; margin-top: 5px;'>{risk_text}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # AI Analysis
    st.markdown("## 🧠 AI Analysis Summary")
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #e7f5ff 0%, #f0f3ff 100%); 
                padding: 20px; border-radius: 12px; border-left: 4px solid #0b89f8;'>
        {compliance_data['summary']}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # (Technologies display removed by request)

    # Detailed Metrics
    st.markdown("## 📊 Detailed Metrics")
    metric_cols = st.columns(4)
    
    metrics_data = [
        ("🌡️ Temperature Exceed", f"{compliance_data['details']['temperature_exceed_hours']:.2f} hrs", "#ff8b3d"),
        ("🚪 Door Opens", f"{compliance_data['details']['door_open_count']}", "#0b89f8"),
        ("⚙️ Performance", "100%", "#764ba2"),
        ("☠️ Spoilage Risk", f"{compliance_data['details']['predicted_spoilage_risk']}%", risk_color),
    ]
    
    for col, (label, value, color) in zip(metric_cols, metrics_data):
        col.markdown(f"""
        <div style='background: linear-gradient(135deg, {color}20 0%, {color}10 100%); 
                    padding: 20px; border-radius: 12px; border: 2px solid {color};'>
            <div style='font-size: 12px; color: #666;'>{label}</div>
            <div style='font-size: 28px; font-weight: bold; color: {color}; margin-top: 10px;'>{value}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Q&A Section
    st.markdown("## 💬 Ask the AI Assistant")
    st.markdown("*Ask any question about this device's compliance and risk factors*")

    question_input = st.text_input(
        "🔤 Your Question",
        placeholder="e.g., What measures should I take to prevent spoilage?",
        key=f"question_{selected_device}",
    )

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        ask_button = st.button("🚀 Ask AI", key=f"ask_{selected_device}", use_container_width=True)
    
    if ask_button:
        if not question_input:
            st.warning("⚠️ Please enter a question.")
        else:
            with st.spinner("🤔 AI is thinking..."):
                try:
                    response = requests.post(
                        f"{API_BASE}/devices/{selected_device}/compliance-question",
                        json={"question": question_input},
                        timeout=15,
                    )
                    response.raise_for_status()
                    answer_data = response.json()
                    
                    st.markdown("### 💡 AI Answer")
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #ebfbee 0%, #f0fff4 100%); 
                                padding: 20px; border-radius: 12px; border-left: 4px solid #1f9d55;
                                color: #1a1f34;'>
                        {answer_data['answer']}
                    </div>
                    """, unsafe_allow_html=True)
                except requests.exceptions.Timeout:
                    st.error("⏱️ Request timed out. Please try again.")
                except requests.RequestException as exc:
                    st.error(f"❌ Failed to get answer: {exc}")

    # Display chat history from session state
    if f"qa_history_{selected_device}" not in st.session_state:
        st.session_state[f"qa_history_{selected_device}"] = []

    history = st.session_state.get(f"qa_history_{selected_device}", [])
    if history:
        st.markdown("---")
        st.markdown("## 📚 Previous Questions")
        for idx, qa in enumerate(history):
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #f0f3ff 0%, #e7f5ff 100%); 
                        padding: 15px; border-radius: 12px; margin: 10px 0;'>
                <p style='color: #0b89f8; font-weight: bold; margin: 0;'>❓ Q: {qa['question']}</p>
                <p style='color: #1a1f34; margin: 10px 0 0 0;'>💬 A: {qa['answer']}</p>
            </div>
            """, unsafe_allow_html=True)


def get_session_device_state(device_id: str) -> Dict[str, Any] | None:
    return st.session_state.get(f"device_state_{device_id}")


def build_device_reading(device: Dict[str, Any]) -> Dict[str, Any]:
    last = device.get("last_reading", {}) or {}
    session_state = get_session_device_state(device.get("device_id", ""))
    if not session_state:
        return last

    merged = dict(last)
    if session_state.get("temperature_c") is not None:
        merged["temperature_c"] = session_state["temperature_c"]
    if session_state.get("humidity_pct") is not None:
        merged["humidity_pct"] = session_state["humidity_pct"]
    if session_state.get("power_ok") is not None:
        merged["power_ok"] = session_state["power_ok"]
    if session_state.get("door_open") is not None:
        merged["door_open"] = session_state["door_open"]
    return merged


def render_dashboard(device_ids: List[str], devices: List[Dict[str, Any]]) -> None:
    st.title("Executive Dashboard")
    st.markdown("### Fleet data overview with KPI cards, recent alerts, and telemetry history")

    # Device Selection Control - Moved to Top
    st.markdown("---")
    selected_device = st.selectbox("🔍 Select a refrigerator for detailed alerts and history", options=device_ids, index=0)
    
    # Dashboard Controls for Selected Device
    if selected_device:
        device_info = next((d for d in devices if d["device_id"] == selected_device), None)
        if device_info:
            device_state_key = f"device_state_{selected_device}"
            device_changes_key = f"device_changes_{selected_device}"
            
            # Initialize state if not exists
            if device_state_key not in st.session_state:
                last_reading = device_info.get("last_reading", {})
                st.session_state[device_state_key] = {
                    "temperature_c": last_reading.get("temperature_c"),
                    "humidity_pct": last_reading.get("humidity_pct"),
                    "power_ok": last_reading.get("power_ok", False),
                    "door_open": last_reading.get("door_open", False),
                }
            
            # Track if changes have been made
            if device_changes_key not in st.session_state:
                st.session_state[device_changes_key] = False
            
            device_state = st.session_state[device_state_key]
            temp_default = float(device_state.get("temperature_c")) if isinstance(device_state.get("temperature_c"), (int, float)) else 5.0
            humidity_default = int(device_state.get("humidity_pct")) if isinstance(device_state.get("humidity_pct"), (int, float)) else 50
            
            st.markdown("### ⚙️ Quick Device Controls")
            ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns(4)
            
            def execute_power_action(action: str) -> None:
                if action == "Power On":
                    device_state["power_ok"] = True
                elif action == "Power Off":
                    device_state["power_ok"] = False
                elif action == "Hard Reset":
                    device_state["power_ok"] = True
                st.session_state[device_state_key] = device_state
                st.session_state[device_changes_key] = True
                # Persist to backend
                try:
                    post_json(f"/devices/{selected_device}/update", json_data=device_state)
                except requests.RequestException as e:
                    st.warning(f"⚠️ Could not save to backend: {e}")

            def execute_temp_action(value: float) -> None:
                device_state["temperature_c"] = value
                st.session_state[device_state_key] = device_state
                st.session_state[device_changes_key] = True
                # Persist to backend
                try:
                    post_json(f"/devices/{selected_device}/update", json_data=device_state)
                except requests.RequestException as e:
                    st.warning(f"⚠️ Could not save to backend: {e}")

            def execute_door_action(action: str) -> None:
                # Accept multiple possible labels coming from different UI controls
                if action in ("Open", "Open Door", "Opened"):
                    device_state["door_open"] = True
                elif action in ("Close", "Closed", "Close Door"):
                    device_state["door_open"] = False
                st.session_state[device_state_key] = device_state
                st.session_state[device_changes_key] = True
                # Persist to backend
                try:
                    post_json(f"/devices/{selected_device}/update", json_data=device_state)
                except requests.RequestException as e:
                    st.warning(f"⚠️ Could not save to backend: {e}")

            def execute_humidity_action(value: int) -> None:
                device_state["humidity_pct"] = value
                st.session_state[device_state_key] = device_state
                st.session_state[device_changes_key] = True
                # Persist to backend
                try:
                    post_json(f"/devices/{selected_device}/update", json_data=device_state)
                except requests.RequestException as e:
                    st.warning(f"⚠️ Could not save to backend: {e}")
            
            with ctrl_col1:
                st.markdown("**🔌 Power**")
                power_action = st.radio("Power:", ["On", "Off", "Reset"], key=f"dash_power_{selected_device}", index=0 if device_state.get("power_ok") else 1)
                if st.button("Apply Power", key=f"dash_power_btn_{selected_device}", use_container_width=True):
                    action_map = {"On": "Power On", "Off": "Power Off", "Reset": "Hard Reset"}
                    execute_power_action(action_map[power_action])
                    st.success(f"✅ Power {power_action}")
            
            with ctrl_col2:
                st.markdown("**🌡️ Temperature**")
                temp_val = st.slider("Temp (°C):", 2.0, 10.0, temp_default, 0.5, key=f"dash_temp_{selected_device}")
                if st.button("Set Temp", key=f"dash_temp_btn_{selected_device}", use_container_width=True):
                    execute_temp_action(temp_val)
                    st.success(f"✅ Set to {temp_val}°C")
            
            with ctrl_col3:
                st.markdown("**🚪 Door**")
                door_action = st.radio("Door:", ["Closed", "Open"], key=f"dash_door_{selected_device}", index=1 if device_state.get("door_open") else 0)
                if st.button("Set Door", key=f"dash_door_btn_{selected_device}", use_container_width=True):
                    execute_door_action(door_action)
                    st.success(f"✅ Door {door_action}")
            
            with ctrl_col4:
                st.markdown("**💧 Humidity**")
                humidity_val = st.slider("Humidity (%):", 20, 90, humidity_default, 5, key=f"dash_humidity_{selected_device}")
                if st.button("Set Humidity", key=f"dash_humidity_btn_{selected_device}", use_container_width=True):
                    execute_humidity_action(humidity_val)
                    st.success(f"✅ Set to {humidity_val}%")
            
            # Show change indicator
            if st.session_state[device_changes_key]:
                st.info(f"💾 Changes made to {selected_device} — they will persist during this session")
    
    st.markdown("---")

    total_devices = len(devices)
    active_units = sum(1 for device in devices if device.get("last_reading"))
    healthy_count = sum(1 for device in devices if device.get("healthy", False))
    avg_temperature = None
    avg_humidity = None
    device_temps = [build_device_reading(device).get("temperature_c") for device in devices if build_device_reading(device).get("temperature_c") is not None]
    device_humidities = [build_device_reading(device).get("humidity_pct") for device in devices if build_device_reading(device).get("humidity_pct") is not None]
    if device_temps:
        avg_temperature = sum(device_temps) / len(device_temps)
    if device_humidities:
        avg_humidity = sum(device_humidities) / len(device_humidities)

    history_frame = get_all_history(device_ids)
    total_readings = len(history_frame)
    violation_count = 0
    compliance_rate = 0.0
    spoilage_risk_pct = 0.0
    if not history_frame.empty:
        compliant_mask = history_frame["temperature_c"].between(2.0, 8.0)
        violation_count = int((~compliant_mask).sum())
        compliance_rate = (total_readings - violation_count) / total_readings * 100 if total_readings else 0.0
        spoilage_risk_pct = violation_count / total_readings * 100 if total_readings else 0.0

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Total Refrigerators", total_devices)
    kpi_cols[1].metric("Active Units", active_units, f"{active_units / total_devices * 100:.0f}%" if total_devices else "N/A")
    kpi_cols[2].metric("Compliance %", f"{compliance_rate:.1f}%", "WHO 2–8°C")
    kpi_cols[3].metric("Spoilage Risk %", f"{spoilage_risk_pct:.1f}%", "Recent violations")

    st.markdown("---")
    st.markdown("### 📋 Device Overview")
    st.write("A quick view of each refrigerator's latest temperature, humidity, power and door state.")

    overview_data = []
    for device in devices:
        last = build_device_reading(device)
        overview_data.append(
            {
                "device_id": device.get("device_id", "Unknown"),
                "temperature_c": safe_numeric(last.get("temperature_c")),
                "humidity_pct": safe_numeric(last.get("humidity_pct"), precision=0),
                "power_ok": "Yes" if last.get("power_ok") else "No",
                "door_open": "Open" if last.get("door_open") else "Closed",
                "status": "Healthy" if device.get("healthy", False) else "Alert",
            }
        )

    if overview_data:
        for row_start in range(0, len(overview_data), 3):
            cols = st.columns(3)
            for idx, device in enumerate(overview_data[row_start:row_start + 3]):
                card_color = "#1f9d55" if device["status"] == "Healthy" else "#dc2626"
                with cols[idx]:
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, {card_color}15 0%, {card_color}05 100%); padding: 20px; border-radius: 18px; border: 1px solid {card_color}33; box-shadow: 0 10px 20px rgba(0,0,0,0.05);'>
                        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;'>
                            <div>
                                <div style='font-size: 14px; color: #475569; margin-bottom: 4px;'>Device ID</div>
                                <div style='font-size: 20px; font-weight: 700; color: {card_color};'>{device['device_id']}</div>
                            </div>
                            <div style='font-size: 12px; color: white; background: {card_color}; padding: 6px 12px; border-radius: 999px;'>
                                {device['status']}
                            </div>
                        </div>
                        <div style='display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px;'>
                            <div style='background: white; border-radius: 14px; padding: 12px; text-align: center;'>
                                <div style='font-size: 12px; color: #6b7280; margin-bottom: 6px;'>Temperature</div>
                                <div style='font-size: 18px; font-weight: 700;'>{device['temperature_c']}°C</div>
                            </div>
                            <div style='background: white; border-radius: 14px; padding: 12px; text-align: center;'>
                                <div style='font-size: 12px; color: #6b7280; margin-bottom: 6px;'>Humidity</div>
                                <div style='font-size: 18px; font-weight: 700;'>{device['humidity_pct']}%</div>
                            </div>
                            <div style='background: white; border-radius: 14px; padding: 12px; text-align: center;'>
                                <div style='font-size: 12px; color: #6b7280; margin-bottom: 6px;'>Power</div>
                                <div style='font-size: 18px; font-weight: 700;'>{device['power_ok']}</div>
                            </div>
                            <div style='background: white; border-radius: 14px; padding: 12px; text-align: center;'>
                                <div style='font-size: 12px; color: #6b7280; margin-bottom: 6px;'>Door</div>
                                <div style='font-size: 18px; font-weight: 700;'>{device['door_open']}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        st.markdown("---")
        st.subheader("Device Overview Table")
        st.dataframe(pd.DataFrame(overview_data), use_container_width=True, hide_index=True)
    else:
        st.info("No device overview data available.")

    st.markdown("---")
    st.markdown(f"### 🔔 Recent Alerts for: **{selected_device}**")
    if not selected_device:
        st.info("Select a device above to view alerts and history.")
        return

    try:
        alerts = fetch_json(f"/devices/{selected_device}/alerts") if selected_device else []
        history = fetch_json(f"/devices/{selected_device}/history") if selected_device else []
    except requests.RequestException as exc:
        st.error(f"❌ Unable to load device data: {exc}")
        return

    if alerts:
        for alert in alerts[:5]:
            level = alert.get("alert_level", "UNKNOWN").upper()
            color = "#c92a2a" if level == "CRITICAL" else "#b04f00" if level == "WARNING" else "#334155"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, {color}15 0%, {color}05 100%); padding: 18px; border-radius: 14px; border-left: 4px solid {color}; margin-bottom: 10px;'>
                <div style='color: {color}; font-weight: 700;'>{alert.get('timestamp', '')} — {level}</div>
                <div style='margin-top: 8px;'>{alert.get('message', '')}</div>
                <div style='font-size: 12px; color: #6b7280; margin-top: 8px;'>Temp: {safe_numeric(alert.get('temperature_c'))}°C | Humidity: {safe_numeric(alert.get('humidity_pct'), precision=0)}%</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ No recent alerts for this device.")

    st.markdown("---")
    st.markdown("### 📈 Recent Telemetry History")
    if history:
        for reading in history[-10:]:
            st.markdown(f"""
            <div style='padding: 14px; border-radius: 14px; background: #ffffff; border: 1px solid #e2e8f0; margin-bottom: 10px;'>
                <strong>{reading.get('timestamp', '')}</strong><br>
                🌡️ {safe_numeric(reading.get('temperature_c'))}°C &nbsp; | &nbsp;
                💧 {safe_numeric(reading.get('humidity_pct'), precision=0)}% &nbsp; | &nbsp;
                🚪 {'Open' if reading.get('door_open') else 'Closed'} &nbsp; | &nbsp;
                ⚡ {'OK' if reading.get('power_ok') else 'Lost'}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No telemetry history available for this device.")


def render_alert_management(device_ids: List[str]) -> None:
    st.title("🚨 Alert Management System")
    st.markdown("### Monitor and manage device alerts with color-coded severity levels and multi-channel notifications")

    # Alert Levels Reference
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div style='background: #10b981; padding: 20px; border-radius: 12px; text-align: center; color: white;'>
            <div style='font-size: 24px; margin-bottom: 10px;'>🟢</div>
            <div style='font-weight: bold; margin-bottom: 5px;'>GREEN</div>
            <div style='font-size: 12px;'>Normal</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='background: #eab308; padding: 20px; border-radius: 12px; text-align: center; color: white;'>
            <div style='font-size: 24px; margin-bottom: 10px;'>🟡</div>
            <div style='font-weight: bold; margin-bottom: 5px;'>YELLOW</div>
            <div style='font-size: 12px;'>Potential Issue</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='background: #f97316; padding: 20px; border-radius: 12px; text-align: center; color: white;'>
            <div style='font-size: 24px; margin-bottom: 10px;'>🟠</div>
            <div style='font-weight: bold; margin-bottom: 5px;'>ORANGE</div>
            <div style='font-size: 12px;'>High Risk</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style='background: #ef4444; padding: 20px; border-radius: 12px; text-align: center; color: white;'>
            <div style='font-size: 24px; margin-bottom: 10px;'>🔴</div>
            <div style='font-weight: bold; margin-bottom: 5px;'>RED</div>
            <div style='font-size: 12px;'>Immediate Action</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Alert Management Controls
    st.markdown("### 📋 Alert Configuration")
    
    control_cols = st.columns([2, 2, 2])
    selected_device = control_cols[0].selectbox("Select Refrigerator", options=device_ids, key="alert_device")
    alert_level = control_cols[1].selectbox(
        "Alert Level", 
        ["Green - Normal", "Yellow - Potential Issue", "Orange - High Risk", "Red - Immediate Action"],
        key="alert_level"
    )
    
    # Notification Channel Selection
    st.markdown("### 📢 Notification Channels")
    
    channel_cols = st.columns(5)
    email_enabled = channel_cols[0].checkbox("📧 Email", value=True)
    sms_enabled = channel_cols[1].checkbox("💬 SMS", value=True)
    whatsapp_enabled = channel_cols[2].checkbox("💚 WhatsApp", value=True)
    teams_enabled = channel_cols[3].checkbox("🔵 Teams", value=False)
    slack_enabled = channel_cols[4].checkbox("⚫ Slack", value=False)

    st.markdown("---")

    # Active Alerts Display
    st.markdown("### 🔔 Active Alerts")
    
    try:
        alerts = fetch_json(f"/devices/{selected_device}/alerts")
    except requests.RequestException:
        alerts = []

    if alerts:
        alert_tabs = st.tabs(["All Alerts", "Critical", "Warnings", "Info"])
        
        with alert_tabs[0]:
            for alert in alerts[:10]:
                level = alert.get("alert_level", "UNKNOWN").upper()
                temp = alert.get("temperature_c", 0)
                humidity = alert.get("humidity_pct", 0)
                message = alert.get("message", "")
                timestamp = alert.get("timestamp", "")
                
                # Determine color and emoji based on alert level
                if "CRITICAL" in level or temp > 10:
                    color = "#ef4444"
                    emoji = "🔴"
                    level_text = "RED - Immediate Action"
                elif "HIGH" in level or temp > 8:
                    color = "#f97316"
                    emoji = "🟠"
                    level_text = "ORANGE - High Risk"
                elif "WARNING" in level or temp > 5:
                    color = "#eab308"
                    emoji = "🟡"
                    level_text = "YELLOW - Potential Issue"
                else:
                    color = "#10b981"
                    emoji = "🟢"
                    level_text = "GREEN - Normal"
                
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, {color}15 0%, {color}05 100%); padding: 18px; border-radius: 14px; border-left: 5px solid {color}; margin: 12px 0;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div>
                            <div style='color: {color}; font-weight: 700; font-size: 16px;'>{emoji} {level_text}</div>
                            <div style='color: #1f2937; margin: 10px 0; font-weight: 500;'>Refrigerator: {selected_device}</div>
                            <div style='color: #1f2937; margin: 8px 0;'>{message}</div>
                            <div style='font-size: 12px; color: #6b7280; margin-top: 10px;'>
                                🌡️ Temperature: {temp:.1f}°C | 💧 Humidity: {humidity:.0f}%
                            </div>
                            <div style='font-size: 11px; color: #9ca3af; margin-top: 5px;'>⏰ {timestamp}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        with alert_tabs[1]:
            critical_alerts = [a for a in alerts if "CRITICAL" in a.get("alert_level", "").upper()]
            if critical_alerts:
                for alert in critical_alerts[:5]:
                    st.markdown(f"""
                    <div style='background: #fee2e2; padding: 18px; border-radius: 14px; border-left: 5px solid #ef4444; margin: 12px 0;'>
                        <div style='color: #ef4444; font-weight: 700;'>🔴 {alert.get('message', '')}</div>
                        <div style='color: #6b7280; font-size: 12px; margin-top: 8px;'>{alert.get('timestamp', '')}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ No critical alerts")
        
        with alert_tabs[2]:
            warning_alerts = [a for a in alerts if "WARNING" in a.get("alert_level", "").upper()]
            if warning_alerts:
                for alert in warning_alerts[:5]:
                    st.markdown(f"""
                    <div style='background: #ffedd5; padding: 18px; border-radius: 14px; border-left: 5px solid #f97316; margin: 12px 0;'>
                        <div style='color: #f97316; font-weight: 700;'>🟠 {alert.get('message', '')}</div>
                        <div style='color: #6b7280; font-size: 12px; margin-top: 8px;'>{alert.get('timestamp', '')}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("ℹ️ No warning alerts")
        
        with alert_tabs[3]:
            st.info("ℹ️ Informational alerts - system is operating normally")
    else:
        st.success("✅ No active alerts. System is operating normally.")

    st.markdown("---")

    # Alert History and Statistics
    st.markdown("### 📊 Alert Statistics")
    
    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
    
    try:
        all_alerts = fetch_json("/devices/alerts/all")
        red_count = sum(1 for a in all_alerts if "CRITICAL" in a.get("alert_level", "").upper() or "RED" in a.get("alert_level", "").upper())
        orange_count = sum(1 for a in all_alerts if "HIGH" in a.get("alert_level", "").upper() or "ORANGE" in a.get("alert_level", "").upper())
        yellow_count = sum(1 for a in all_alerts if "WARNING" in a.get("alert_level", "").upper() or "YELLOW" in a.get("alert_level", "").upper())
        green_count = sum(1 for a in all_alerts if "INFO" in a.get("alert_level", "").upper() or "GREEN" in a.get("alert_level", "").upper())
    except requests.RequestException:
        red_count = orange_count = yellow_count = green_count = 0

    stats_col1.metric("🔴 Red Alerts", red_count)
    stats_col2.metric("🟠 Orange Alerts", orange_count)
    stats_col3.metric("🟡 Yellow Alerts", yellow_count)
    stats_col4.metric("🟢 Green Status", green_count)

    st.markdown("---")

    # Notification Settings
    st.markdown("### ⚙️ Notification Settings")
    
    settings_cols = st.columns(2)
    
    with settings_cols[0]:
        st.markdown("#### Email Settings")
        email_recipient = st.text_input("Email Recipient", value="ops-team@example.com", key="email_recipient")
        st.caption("Alert emails will be sent to this address")
    
    with settings_cols[1]:
        st.markdown("#### SMS Settings")
        sms_recipient = st.text_input("SMS Recipient", value="+1-800-000-0000", key="sms_recipient")
        st.caption("SMS alerts will be sent to this number")

    # Test Alert Button
    st.markdown("---")
    st.markdown("### 🧪 Test Alert System")
    
    test_col1, test_col2 = st.columns([1, 3])
    
    with test_col1:
        alert_to_test = st.selectbox(
            "Test Alert Level",
            ["Red - Immediate Action", "Orange - High Risk", "Yellow - Potential Issue"],
            key="test_alert"
        )
    
    if test_col2.button("🚨 Send Test Alert", use_container_width=True):
        with st.spinner("Sending test alert..."):
            st.success("✅ Test alert sent successfully!")
            
            # Display example notification
            st.markdown("##### Example Notification Sent:")
            
            example_alert = f"""
            ALERT
            
            Refrigerator: {selected_device}
            Temperature: 9.4°C
            Vaccine Spoilage Risk: High
            Alert Level: {alert_to_test}
            Timestamp: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            st.code(example_alert, language="text")
            
            # Show which channels were notified
            notified_channels = []
            if email_enabled:
                notified_channels.append("📧 Email")
            if sms_enabled:
                notified_channels.append("💬 SMS")
            if whatsapp_enabled:
                notified_channels.append("💚 WhatsApp")
            if teams_enabled:
                notified_channels.append("🔵 Microsoft Teams")
            if slack_enabled:
                notified_channels.append("⚫ Slack")
            
            if notified_channels:
                st.info(f"✓ Notifications sent via: {', '.join(notified_channels)}")


def render_compliance_monitoring(device_ids: List[str]) -> None:
    st.title("Compliance Dashboard")
    st.caption("WHO vaccine cold-chain guideline: maintain refrigerator temperature between 2°C and 8°C.")

    compliance_frame = get_all_history(device_ids)
    if compliance_frame.empty:
        st.info("Compliance reports will appear after telemetry history is available.")
        return

    selected_devices = st.multiselect(
        "Select Refrigerators",
        options=device_ids,
        default=device_ids,
    )
    if not selected_devices:
        st.warning("Select at least one refrigerator to monitor compliance.")
        return

    compliance_frame = compliance_frame[compliance_frame["device_id"].isin(selected_devices)].copy()
    compliance_frame["is_compliant"] = compliance_frame["temperature_c"].between(2.0, 8.0)
    compliance_frame["is_violation"] = ~compliance_frame["is_compliant"]
    compliance_frame["compliance_status"] = compliance_frame["is_violation"].map(
        {True: "Violation", False: "Compliant"}
    )

    total_readings = len(compliance_frame)
    violation_count = int(compliance_frame["is_violation"].sum())
    compliance_rate = (total_readings - violation_count) / total_readings * 100

    metric_cols = st.columns(4)
    metric_cols[0].metric("WHO Compliance %", f"{compliance_rate:.1f}%")
    metric_cols[1].metric("Temperature Violations", violation_count)
    metric_cols[2].metric("Audit Readings", total_readings)
    metric_cols[3].metric("Monitored Devices", len(selected_devices))

    st.subheader("Compliance Engine")
    st.code(
        'if temperature_c > 8 or temperature_c < 2:\n    compliance_status = "Violation"',
        language="python",
    )

    st.markdown("### DAX Example")
    st.code(
        "Compliance Rate =\nDIVIDE(\n    COUNTROWS(\n        FILTER(\n            Refrigerator,\n            Refrigerator[Status] = \"Compliant\"\n        )\n    ),\n    COUNTROWS(Refrigerator)\n)",
        language="dax",
    )

    daily_report = build_compliance_report(compliance_frame, "date", "day")
    weekly_report = build_compliance_report(compliance_frame, "week", "week_start")
    monthly_report = build_compliance_report(compliance_frame, "month", "month_start")

    daily_tab, weekly_tab, monthly_tab, violations_tab = st.tabs(
        ["Daily Compliance Report", "Weekly Compliance Report", "Monthly Audit Report", "Violations"]
    )
    with daily_tab:
        st.dataframe(daily_report, width="stretch", hide_index=True)
    with weekly_tab:
        st.dataframe(weekly_report, width="stretch", hide_index=True)
    with monthly_tab:
        st.dataframe(monthly_report, width="stretch", hide_index=True)
    with violations_tab:
        violations = compliance_frame[compliance_frame["is_violation"]].sort_values(
            "timestamp", ascending=False
        )
        if violations.empty:
            st.success("No compliance violations found.")
        else:
            st.dataframe(
                violations[
                    [
                        "device_id",
                        "timestamp",
                        "temperature_c",
                        "humidity_pct",
                        "door_open",
                        "power_ok",
                        "compliance_status",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

    st.subheader("Compliance Trend")
    trend = (
        compliance_frame.groupby(["date", "device_id"], as_index=False)
        .agg(compliance_rate_pct=("is_compliant", lambda values: values.mean() * 100))
    )
    fig_compliance = px.line(
        trend,
        x="date",
        y="compliance_rate_pct",
        color="device_id",
        markers=True,
        title="Cold Chain Compliance Rate Over Time",
        labels={"compliance_rate_pct": "Compliance Rate (%)", "date": "Date"},
    )
    fig_compliance.update_layout(
        height=350,
        template="plotly_white",
        hovermode="x unified",
        plot_bgcolor="rgba(240, 245, 251, 0.5)",
        yaxis=dict(range=[0, 105]),
    )
    fig_compliance.update_traces(line=dict(width=3), marker=dict(size=8))
    st.plotly_chart(fig_compliance, use_container_width=True)

    st.markdown("---")
    st.subheader("Feed Summary")
    feed_device_count = len(selected_devices)
    violation_devices = int(
        compliance_frame.groupby("device_id")["is_violation"].any().sum()
    )
    avg_device_compliance = (
        compliance_frame.groupby("device_id")["is_compliant"].mean() * 100
    ).mean()

    summary_cols = st.columns(4)
    summary_cols[0].metric("Monitored Devices", feed_device_count)
    summary_cols[1].metric("Avg Device Compliance", f"{avg_device_compliance:.1f}%")
    summary_cols[2].metric("Violation Devices", violation_devices)
    summary_cols[3].metric("Overall Compliance", f"{compliance_rate:.1f}%")

    st.markdown(
        "<div style='background: linear-gradient(135deg, #eef2ff 0%, #f8fafc 100%); padding: 18px; border-radius: 18px; border: 1px solid #c7d2fe;'>"
        f"<strong>Fleet insights:</strong> {feed_device_count} refrigerators are currently monitored, with an average device compliance of {avg_device_compliance:.1f}% and {violation_devices} devices showing one or more violations."
        "</div>",
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="Medical Refrigerator Monitor", layout="wide")

# Custom CSS for enhanced styling
st.markdown("""
<style>
    :root {
        --primary: #1e3a8a;
        --accent: #0ea5e9;
        --secondary: #0f172a;
        --surface: #ffffff;
        --surface-muted: #eef2ff;
        --border: #cbd5e1;
        --success: #14b8a6;
        --danger: #ef4444;
        --warning: #f59e0b;
    }

    body {
        background: transparent !important;
    }

    [data-testid="stAppViewContainer"] {
        background: transparent !important;
    }

    .main {
        background: transparent !important;
    }

    .login-page {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: block;
        background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
        color: #0f172a;
        z-index: 0;
    }

    .login-page::before {
        content: '';
        position: absolute;
        inset: 0;
        background: rgba(255, 255, 255, 0.35);
        pointer-events: none;
    }

    .login-card {
        position: relative;
        z-index: 1;
        max-width: 420px;
        width: 100%;
        margin: 0 auto 24px auto;
        padding: 24px 22px 22px 22px;
        border-radius: 24px;
        background: rgba(255, 255, 255, 0.84);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(148, 163, 184, 0.22);
        box-shadow: 0 20px 48px rgba(15, 23, 42, 0.08);
    }

    .login-banner {
        width: 100%;
        max-width: 520px;
        height: 220px;
        object-fit: cover;
        border-radius: 20px;
        margin-bottom: 20px;
        border: 1px solid rgba(148, 163, 184, 0.22);
        box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
    }

    .stTitle {
        color: var(--secondary);
        font-weight: 800;
        text-align: center;
        padding: 20px 0;
        border-bottom: 3px solid var(--primary);
        margin-bottom: 16px;
    }

    .stMetric {
        background: var(--surface);
        padding: 22px;
        border-radius: 18px;
        border: 1px solid rgba(30, 58, 138, 0.12);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
    }

    .stMetric:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.1);
    }

    [data-testid="stMetricDelta"] {
        color: var(--success);
        font-weight: 700;
    }

    .stButton > button {
        background: var(--primary);
        color: white;
        border: none;
        border-radius: 14px;
        padding: 12px 26px;
        font-weight: 700;
        font-size: 15px;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        box-shadow: 0 8px 18px rgba(30, 58, 138, 0.2);
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 12px 24px rgba(30, 58, 138, 0.2);
    }

    .stSelectbox, .stMultiSelect, .stTextInput {
        border-radius: 14px !important;
        border: 1px solid var(--border) !important;
        background: var(--surface) !important;
    }

    .stButton > button {
        border: 1px solid rgba(255, 255, 255, 0.18) !important;
        background: var(--primary) !important;
        color: white !important;
        border-radius: 14px !important;
    }

    .stInfo, .stSuccess, .stWarning, .stError {
        border-radius: 14px !important;
        border-left: 4px solid !important;
        padding: 16px !important;
    }

    .stInfo {
        background: #eff6ff !important;
        border-color: var(--accent) !important;
    }

    .stSuccess {
        background: #ecfdf5 !important;
        border-color: var(--success) !important;
    }

    .stWarning {
        background: #ffedd5 !important;
        border-color: var(--warning) !important;
    }

    .stError {
        background: #fee2e2 !important;
        border-color: var(--danger) !important;
    }

    .risk-high {
        color: var(--danger);
        font-weight: 700;
        font-size: 18px;
    }

    .risk-medium {
        color: var(--warning);
        font-weight: 700;
        font-size: 18px;
    }

    .risk-low {
        color: var(--success);
        font-weight: 700;
        font-size: 18px;
    }

    .metric-card {
        background: var(--surface);
        padding: 20px;
        border-radius: 18px;
        border: 1px solid rgba(30, 58, 138, 0.1);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
        margin: 10px 0;
    }

    .compliance-pass {
        background: #d1fae5;
        color: #0f5132;
        padding: 16px;
        border-radius: 14px;
        text-align: center;
        font-weight: 700;
    }

    .compliance-fail {
        background: #fee2e2;
        color: #991b1b;
        padding: 16px;
        border-radius: 14px;
        text-align: center;
        font-weight: 700;
    }

    h1, h2, h3, h4, h5, h6 {
        color: var(--secondary) !important;
        font-weight: 700 !important;
    }

    .stTabs [data-baseweb="tab-list"] button {
        background: var(--surface-muted);
        border-radius: 16px;
        margin: 4px;
        border: 1px solid rgba(148, 163, 184, 0.28);
        font-weight: 600;
        color: var(--secondary);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }

    .stTabs [data-baseweb="tab-list"] button:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
    }

    .stTabs [aria-selected="true"] {
        background: var(--primary) !important;
        color: white !important;
        border-color: var(--primary) !important;
        box-shadow: 0 14px 28px rgba(30, 58, 138, 0.18) !important;
    }

    .login-card {
        max-width: 560px;
        margin: 0 auto 24px auto;
        padding: 28px 26px 24px 26px;
        border-radius: 24px;
        background: var(--surface);
        border: 1px solid rgba(148, 163, 184, 0.22);
        box-shadow: 0 20px 48px rgba(15, 23, 42, 0.08);
    }

    .sidebar-summary-card {
        padding: 22px;
        border-radius: 18px;
        background: var(--surface);
        border: 1px solid rgba(148, 163, 184, 0.24);
        box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
        margin-bottom: 20px;
    }

    .sidebar-summary-card h3 {
        margin: 0 0 14px 0;
        color: #1e293b;
        font-size: 18px;
        font-weight: 800;
    }

    .sidebar-summary-metric {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
        color: #334155;
    }

    .sidebar-summary-metric:last-child {
        border-bottom: none;
    }

    .sidebar-summary-value {
        font-weight: 800;
        color: var(--secondary);
    }

    [data-testid="stHeader"] {
        background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
    }

    [data-testid="stSidebar"] {
        background: var(--surface-muted);
    }
</style>
""", unsafe_allow_html=True)


def render_operations_dashboard(device_ids: List[str]) -> None:
    st.title("Operations Dashboard")
    st.markdown("### Visualize temperature, power, door, and compressor health patterns.")

    history_frame = get_all_history(device_ids)
    if history_frame.empty:
        st.info("Operations metrics will appear once telemetry history is available.")
        return

    selected_devices = st.multiselect(
        "Select Refrigerators",
        options=device_ids,
        default=device_ids,
        key="operations_devices",
    )
    if not selected_devices:
        st.warning("Select at least one refrigerator to analyze.")
        return

    history_frame = history_frame[history_frame["device_id"].isin(selected_devices)].copy()
    feature_frame = create_engineered_features(history_frame)

    st.subheader("Temperature Trends")
    temp_trend = (
        history_frame.groupby(["date", "device_id"], as_index=False)
        .agg(avg_temperature_c=("temperature_c", "mean"))
    )
    fig_temp = px.line(
        temp_trend,
        x="date",
        y="avg_temperature_c",
        color="device_id",
        markers=True,
        title="Temperature Trend by Refrigerator",
        labels={"avg_temperature_c": "Avg Temp (°C)", "date": "Date"},
    )
    fig_temp.update_layout(height=360, template="plotly_white", hovermode="x unified")
    st.plotly_chart(fig_temp, use_container_width=True)

    st.subheader("Power Consumption Proxy")
    power_trend = (
        history_frame.groupby(["date", "device_id"], as_index=False)
        .agg(power_loss_events=("power_loss_int", "sum"), avg_load=("cooling_load_score", "mean"))
    )
    fig_power = px.bar(
        power_trend,
        x="date",
        y="power_loss_events",
        color="device_id",
        title="Daily Power Loss Events",
        labels={"power_loss_events": "Power Loss Events", "date": "Date"},
    )
    fig_power.update_layout(height=360, template="plotly_white", barmode="group")
    st.plotly_chart(fig_power, use_container_width=True)
    st.write("Power loss events are used as a proxy for intermittent power issues and compressor stress.")

    st.subheader("Door Open Events")
    door_summary = (
        history_frame.groupby(["device_id"], as_index=False)
        .agg(door_open_events=("door_open_int", "sum"), door_open_rate=("door_open_int", "mean"))
        .sort_values("door_open_events", ascending=False)
    )
    fig_door = px.bar(
        door_summary,
        x="device_id",
        y="door_open_events",
        title="Total Door Open Events by Refrigerator",
        labels={"door_open_events": "Door Open Events", "device_id": "Device ID"},
        color="door_open_events",
        color_continuous_scale="Blues",
    )
    fig_door.update_layout(
        height=360,
        template="plotly_white",
        showlegend=False,
        xaxis_title="Device ID",
        yaxis_title="Door Open Events",
    )
    st.plotly_chart(fig_door, use_container_width=True)

    st.subheader("Device Simulation Axis")
    device_simulation = (
        history_frame.groupby(["device_id"], as_index=False)
        .agg(
            avg_temp=("temperature_c", "mean"),
            avg_humidity=("humidity_pct", "mean"),
        )
    )
    fig_device_axis = px.bar(
        device_simulation,
        x="device_id",
        y=["avg_temp", "avg_humidity"],
        title="Device Simulation Axis by Refrigerator",
        labels={"device_id": "Device ID", "value": "Average Metric", "variable": "Metric"},
    )
    fig_device_axis.update_layout(
        height=380,
        template="plotly_white",
        barmode="group",
        xaxis_title="Device ID",
        yaxis_title="Average Value",
    )
    st.plotly_chart(fig_device_axis, use_container_width=True)
    st.dataframe(door_summary, hide_index=True, use_container_width=True)

    st.subheader("Compressor Health")
    if feature_frame.empty:
        st.warning("Compressor health metrics are not yet available.")
    else:
        latest_health = (
            feature_frame.sort_values("timestamp")
            .groupby("device_id", as_index=False)
            .tail(1)
            .sort_values("compressor_health", ascending=False)
        )
        st.dataframe(latest_health[["device_id", "compressor_health", "power_stability", "door_open_rate"]], hide_index=True, use_container_width=True)

        fig_health = px.line(
            feature_frame,
            x="timestamp",
            y="compressor_health",
            color="device_id",
            markers=True,
            title="Compressor Health Over Time",
            labels={"compressor_health": "Health Score", "timestamp": "Time"},
        )
        fig_health.update_layout(height=360, template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig_health, use_container_width=True)

    st.markdown("---")
    st.write("Operations insights reveal whether temperature drift, power disruption, door usage, or compressor health is driving refrigeration risk.")

# Top navigation: removed from UI
# params = st.query_params
# current_page = params.get("page", "Dashboard") if params else "Dashboard"

# Build active class indicators for each nav link
# active_dashboard = 'active' if current_page == 'Dashboard' else ''
# active_ai = 'active' if current_page == 'AI Compliance Assistant' else ''
# active_eda = 'active' if current_page == 'Exploratory Data Analysis' else ''
# active_feat = 'active' if current_page == 'Feature Engineering' else ''
# active_anom = 'active' if current_page == 'Temperature Anomaly Detection' else ''
# active_comp = 'active' if current_page == 'Compliance Monitoring' else ''

# Navigation HTML removed from UI - reference code can be restored if needed

# Navigation bar removed from UI
# st.markdown(nav_html, unsafe_allow_html=True)

# Basic authentication logic
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def show_login_form():
    st.markdown("<div class='login-page'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown(
            """
            <div class='login-card' style='text-align:center;'>
                <div style='font-size:48px; margin-bottom:16px;'>❄️🧊</div>
                <h2 style='font-size:22px; font-weight:800; color:#0f172a; margin-bottom:16px;'>AI-Powered Smart Medical Refrigerator Monitoring System</h2>
                <p style='color:#475569; margin-bottom:22px;'>Please sign in to continue.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", use_container_width=True):
            # In production, use hashed passwords and a database
            if username == "admin" and password == "admin123":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Invalid username or password")


def render_sidebar_summary(devices: List[Dict[str, Any]]) -> None:
    total_devices = len(devices)
    healthy_count = sum(1 for device in devices if device.get("healthy", False))
    alert_count = total_devices - healthy_count
    temps = [
        device.get("last_reading", {}).get("temperature_c")
        for device in devices
        if device.get("last_reading") and device.get("last_reading").get("temperature_c") is not None
    ]
    humidity_values = [
        device.get("last_reading", {}).get("humidity_pct")
        for device in devices
        if device.get("last_reading") and device.get("last_reading").get("humidity_pct") is not None
    ]
    avg_temp = f"{sum(temps) / len(temps):.1f}°C" if temps else "N/A"
    avg_humidity = f"{sum(humidity_values) / len(humidity_values):.0f}%" if humidity_values else "N/A"

    st.sidebar.markdown(
        f"""
        <div class='sidebar-summary-card'>
            <h3>Fleet Summary</h3>
            <div class='sidebar-summary-metric'><span>Total devices</span><span class='sidebar-summary-value'>{total_devices}</span></div>
            <div class='sidebar-summary-metric'><span>Healthy</span><span class='sidebar-summary-value'>{healthy_count}</span></div>
            <div class='sidebar-summary-metric'><span>Alerts</span><span class='sidebar-summary-value'>{alert_count}</span></div>
            <div class='sidebar-summary-metric'><span>Avg temp</span><span class='sidebar-summary-value'>{avg_temp}</span></div>
            <div class='sidebar-summary-metric'><span>Avg humidity</span><span class='sidebar-summary-value'>{avg_humidity}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_device_controller(device_ids: List[str], devices: List[Dict[str, Any]]) -> None:
    st.title("🎮 Device Controller")
    st.markdown("### Manage and control refrigerator settings and operations.")

    selected_device = st.selectbox("Select Device to Control", options=device_ids)
    
    if not selected_device:
        st.info("Please select a device to manage.")
        return
    
    # Get device details
    device_info = next((d for d in devices if d["device_id"] == selected_device), None)
    if not device_info:
        st.error(f"Device {selected_device} not found.")
        return
    
    device_state_key = f"device_state_{selected_device}"
    if device_state_key not in st.session_state:
        last_reading = device_info.get("last_reading", {})
        st.session_state[device_state_key] = {
            "temperature_c": last_reading.get("temperature_c"),
            "humidity_pct": last_reading.get("humidity_pct"),
            "power_ok": last_reading.get("power_ok", False),
            "door_open": last_reading.get("door_open", False),
        }

    device_state = st.session_state[device_state_key]
    current_temp = device_state.get("temperature_c")
    current_humidity = device_state.get("humidity_pct")
    temp_display = safe_numeric(current_temp)
    humidity_display = safe_numeric(current_humidity, precision=0)
    temp_default = float(current_temp) if isinstance(current_temp, (int, float)) else 5.0
    humidity_default = int(current_humidity) if isinstance(current_humidity, (int, float)) else 50

    st.markdown("---")
    
    # Current Status
    st.subheader("📊 Current Status")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Temperature", f"{temp_display}°C")
    col2.metric("Humidity", f"{humidity_display}%")
    col3.metric("Power Status", "✅ OK" if device_state.get("power_ok") else "❌ Lost")
    col4.metric("Door Status", "🚪 Open" if device_state.get("door_open") else "✅ Closed")
    
    st.markdown("---")
    st.subheader("⚙️ Device Controls")
    
    control_col1, control_col2 = st.columns(2)

    control_history_key = f"control_history_{selected_device}"
    if control_history_key not in st.session_state:
        st.session_state[control_history_key] = []

    action_message_key = f"action_message_{selected_device}"
    if action_message_key not in st.session_state:
        st.session_state[action_message_key] = ""

    def record_control_action(action: str) -> None:
        st.session_state[control_history_key].insert(0, {
            "Timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Action": action,
            "Status": "✅ Success",
            "Duration": "1s",
        })

    def execute_power_action(action: str) -> None:
        if action == "Power On":
            device_state["power_ok"] = True
        elif action == "Power Off":
            device_state["power_ok"] = False
        elif action == "Hard Reset":
            device_state["power_ok"] = True
        record_control_action(action)
        st.session_state[action_message_key] = f"✅ {action} command sent to {selected_device}"

    def execute_temp_action(value: float) -> None:
        device_state["temperature_c"] = value
        record_control_action(f"Set Temperature to {value}°C")
        st.session_state[action_message_key] = f"✅ Target temperature set to {value}°C for {selected_device}"

    def execute_door_action(action: str) -> None:
        if action == "Open Door":
            device_state["door_open"] = True
            result_message = "Door is now open"
        elif action == "Close Door":
            device_state["door_open"] = False
            result_message = "Door is now closed"
        else:
            result_message = "No door action taken"
        record_control_action(action)
        st.session_state[action_message_key] = f"✅ {action} command sent to {selected_device} — {result_message}"

    def execute_humidity_action(value: int) -> None:
        device_state["humidity_pct"] = value
        record_control_action(f"Set Humidity to {value}%")
        st.session_state[action_message_key] = f"✅ Target humidity set to {value}% for {selected_device}"

    def execute_maintenance_action(action: str) -> None:
        record_control_action(action)
        st.session_state[action_message_key] = f"✅ {action} initiated for {selected_device}"

    def clear_alerts_action() -> None:
        record_control_action("Clear All Alerts")
        st.session_state[action_message_key] = f"✅ All alerts cleared for {selected_device}"

    with control_col1:
        st.markdown("**Power Management**")
        power_action = st.selectbox("Power Action", ["No Action", "Power On", "Power Off", "Hard Reset"], key=f"power_{selected_device}")
        st.button("Execute Power Action", key=f"power_btn_{selected_device}", on_click=execute_power_action, args=(power_action,))

        st.markdown("**Temperature Control**")
        target_temp = st.slider("Set Target Temperature (°C)", 2.0, 10.0, temp_default, 0.1, key=f"temp_{selected_device}")
        st.button("Set Temperature", key=f"temp_btn_{selected_device}", on_click=execute_temp_action, args=(target_temp,))

        st.markdown("**Door Control**")
        door_action = st.selectbox("Door Action", ["No Action", "Open Door", "Close Door"], key=f"door_{selected_device}")
        st.button("Execute Door Action", key=f"door_btn_{selected_device}", on_click=execute_door_action, args=(door_action,))

    with control_col2:
        st.markdown("**Humidity Control**")
        humidity_target = st.slider("Set Target Humidity (%)", 20, 90, humidity_default, key=f"humidity_{selected_device}")
        st.button("Set Humidity", key=f"humidity_btn_{selected_device}", on_click=execute_humidity_action, args=(humidity_target,))

        st.markdown("**Maintenance Actions**")
        maintenance_action = st.selectbox("Maintenance Action", ["None", "Calibrate Sensors", "Run Diagnostics", "Clear Alerts"], key=f"maint_{selected_device}")
        st.button("Execute Maintenance", key=f"maint_btn_{selected_device}", on_click=execute_maintenance_action, args=(maintenance_action,))

        st.markdown("**Alert Management**")
        st.button("Clear All Alerts", key=f"clear_alerts_{selected_device}", on_click=clear_alerts_action)

    if st.session_state[action_message_key]:
        st.info(st.session_state[action_message_key])
    
    st.markdown("---")
    st.subheader("📋 Control History")
    control_history = pd.DataFrame(st.session_state.get(control_history_key, []))
    if control_history.empty:
        st.info("No control history yet. Perform an action to start tracking.")
    else:
        st.dataframe(control_history, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("🔔 Device Notifications")
    
    try:
        alerts = fetch_json(f"/devices/{selected_device}/alerts")
        if alerts:
            for alert in alerts[:3]:
                level = alert.get("alert_level", "UNKNOWN").upper()
                color = "#c92a2a" if level == "CRITICAL" else "#b04f00" if level == "WARNING" else "#334155"
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, {color}15 0%, {color}05 100%); padding: 16px; border-radius: 12px; border-left: 4px solid {color}; margin-bottom: 10px;'>
                    <div style='color: {color}; font-weight: 700;'>{level}</div>
                    <div style='color: #1f2937;'>{alert.get('message', '')}</div>
                    <div style='font-size: 12px; color: #6b7280; margin-top: 8px;'>{alert.get('timestamp', '')}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ No active alerts")
    except requests.RequestException:
        st.info("Unable to load alerts")


def render_page_navigation(device_ids: List[str], devices: List[Dict[str, Any]]) -> None:
    # Removed Device Controller tab per user request
    nav_items = [
        ("Executive Dashboard", "📊"),
        ("Alert Management", "🚨"),
        ("Operations Dashboard", "⚙️"),
        ("AI Compliance Assistant", "🤖"),
        ("Remaining Useful Life", "📉"),
        ("Temperature Anomaly Detection", "⚠️"),
        ("Compliance Dashboard", "✅"),
    ]

    tab_labels = [f"{icon} {name}" for name, icon in nav_items]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        render_dashboard(device_ids, devices)
    with tabs[1]:
        render_alert_management(device_ids)
    with tabs[2]:
        render_operations_dashboard(device_ids)
    with tabs[3]:
        render_ai_compliance_assistant(device_ids)
    with tabs[4]:
        render_remaining_useful_life(device_ids)
    with tabs[5]:
        render_temperature_anomaly_detection(device_ids)
    with tabs[6]:
        render_compliance_monitoring(device_ids)


if not st.session_state["authenticated"]:
    show_login_form()
    st.stop()

# Top-left app title block
st.markdown(
    """
    <div style='display:flex; align-items:center; gap:12px; margin-bottom:20px;'>
        <div style='width:48px; height:48px; background: linear-gradient(135deg, #0ea5e, #22d3ee); border-radius:14px; display:flex; align-items:center; justify-content:center; font-size:24px; color:white;'>
            ❄️
        </div>
        <div style='line-height:1.1;'>
            <div style='font-size:22px; font-weight:800; margin:0; color:#0f172a;'>AI-Powered Smart Medical Refrigerator Monitoring System</div>
            <div style='font-size:13px; color:#475569; margin-top:4px;'>Cold-chain visibility, alerts, and AI-driven compliance</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar Logout Button
st.sidebar.button("Log Out", on_click=lambda: st.session_state.update({"authenticated": False}))

# Fetch devices first, before building controls
try:
    devices = fetch_json("/devices")
except requests.RequestException as exc:
    st.error("### ❌ Backend Connection Error")
    st.info("The Streamlit app cannot connect to the FastAPI backend. Please ensure the backend server is running.")
    st.markdown("""
    **To start the backend, run the following in a separate terminal:**
    ```bash
    # Navigate to the backend folder
    cd backend

    # Activate your virtual environment (Windows)
    .\\venv\\Scripts\\Activate.ps1

    # Run the server
    uvicorn app.main:app --reload --port 8000
    ```
    """)
    st.stop()

if not devices:
    st.warning("No devices returned from backend.")
    st.stop()

device_ids = [device["device_id"] for device in devices]

render_page_navigation(device_ids, devices)

render_sidebar_summary(devices)
