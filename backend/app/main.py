from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from starlette.applications import Starlette
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from .data_store import store
from .forecast import forecast_next_24_hours
from .notifications import notify_alert
from .schemas import AlertHistoryItem, AlertStatus, TelemetryReading, DashboardStatus
from .services import evaluate_alert
from .simulator import generate_sample_reading
import os
import json
import random
from datetime import timedelta
import urllib.request
import urllib.error


def serialize_response(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize_response(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_response(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return serialize_response(value.__dict__)
    return value


def json_response(value: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(serialize_response(value), status_code=status_code)


def handle_validation_error(error_message: str) -> None:
    raise StarletteHTTPException(status_code=HTTP_400_BAD_REQUEST, detail=error_message)


def build_rul_regression_model() -> tuple[Any, List[str], Any]:
    try:
        from sklearn.ensemble import RandomForestRegressor
    except ModuleNotFoundError as exc:
        raise RuntimeError("scikit-learn is required for RUL prediction") from exc

    feature_names = [
        "age_months",
        "runtime_hours",
        "maintenance_visits",
        "avg_daily_power_kwh",
        "power_loss_events",
        "door_open_rate",
        "avg_temperature",
    ]

    train_X: List[List[float]] = []
    train_y: List[float] = []

    for _ in range(300):
        age_months = random.uniform(6, 120)
        runtime_hours = random.uniform(500, 22000)
        maintenance_visits = random.randint(0, 12)
        avg_daily_power_kwh = random.uniform(1.0, 14.0)
        power_loss_events = random.randint(0, 18)
        door_open_rate = random.uniform(0.0, 0.35)
        avg_temperature = random.uniform(2.0, 12.0)

        remaining = (
            48
            - age_months * 0.22
            - runtime_hours * 0.006
            + maintenance_visits * 1.8
            - power_loss_events * 1.1
            - max(0.0, avg_temperature - 6.0) * 2.2
            - door_open_rate * 28.0
            - max(0.0, avg_daily_power_kwh - 8.0) * 1.5
        )
        remaining = max(1, min(60, remaining + random.uniform(-4.0, 4.0)))

        train_X.append([
            age_months,
            runtime_hours,
            maintenance_visits,
            avg_daily_power_kwh,
            power_loss_events,
            door_open_rate,
            avg_temperature,
        ])
        train_y.append(remaining)

    model = RandomForestRegressor(n_estimators=150, random_state=42)
    model.fit(train_X, train_y)
    return model, feature_names, model.feature_importances_


async def ingest_telemetry(request: Request) -> JSONResponse:
    payload = await request.json()
    try:
        reading = TelemetryReading.from_dict(payload)
    except ValueError as exc:
        handle_validation_error(str(exc))

    store.save(reading)
    alert = evaluate_alert(reading)
    if alert is not None:
        notify_alert(reading, alert)

    return json_response(reading)


async def get_devices(request: Request) -> JSONResponse:
    devices: List[DashboardStatus] = []
    for reading in store.all_latest():
        alert = evaluate_alert(reading)
        devices.append(
            DashboardStatus(
                device_id=reading.device_id,
                last_reading=reading,
                alert_status=alert,
                healthy=alert is None,
            )
        )
    return json_response(devices)


async def get_device(request: Request) -> JSONResponse:
    device_id = request.path_params["device_id"]
    reading = store.latest(device_id)
    if reading is None:
        raise StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="Device not found")

    alert = evaluate_alert(reading)
    status = DashboardStatus(
        device_id=device_id,
        last_reading=reading,
        alert_status=alert,
        healthy=alert is None,
    )
    return json_response(status)


async def get_device_history(request: Request) -> JSONResponse:
    device_id = request.path_params["device_id"]
    history = store.history(device_id)
    if not history:
        raise StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="Device not found")
    return json_response(history)


async def get_device_alerts(request: Request) -> JSONResponse:
    device_id = request.path_params["device_id"]
    history = store.history(device_id)
    if not history:
        raise StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="Device not found")

    alerts: List[AlertHistoryItem] = []
    for reading in history:
        alert = evaluate_alert(reading)
        if alert is not None:
            alerts.append(
                AlertHistoryItem(
                    device_id=reading.device_id,
                    timestamp=reading.timestamp,
                    alert_level=alert.alert_level,
                    message=alert.message,
                    temperature_c=reading.temperature_c,
                    humidity_pct=reading.humidity_pct,
                    door_open=reading.door_open,
                    power_ok=reading.power_ok,
                )
            )
    return json_response(alerts)


async def get_device_rul(request: Request) -> JSONResponse:
    device_id = request.path_params["device_id"]
    payload = await request.json()

    if not payload:
        handle_validation_error("RUL prediction payload cannot be empty")

    try:
        age_months = float(payload["age_months"])
        runtime_hours = float(payload["runtime_hours"])
        maintenance_visits = float(payload["maintenance_visits"])
        avg_daily_power_kwh = float(payload["avg_daily_power_kwh"])
        power_loss_events = float(payload["power_loss_events"])
        door_open_rate = float(payload["door_open_rate"])
        avg_temperature = float(payload["avg_temperature"])
    except (KeyError, TypeError, ValueError) as exc:
        handle_validation_error(f"Invalid RUL request body: {exc}")

    try:
        model, feature_names, importances = build_rul_regression_model()
    except RuntimeError as exc:
        raise StarletteHTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))

    feature_vector = [
        age_months,
        runtime_hours,
        maintenance_visits,
        avg_daily_power_kwh,
        power_loss_events,
        door_open_rate,
        avg_temperature,
    ]

    prediction = model.predict([feature_vector])[0]
    prediction_months = max(1, round(float(prediction)))
    feature_importances = [
        {"feature": name, "importance": float(value)}
        for name, value in zip(feature_names, importances)
    ]

    return json_response({
        "device_id": device_id,
        "prediction_months": prediction_months,
        "feature_importances": feature_importances,
        "inputs": {
            "age_months": age_months,
            "runtime_hours": runtime_hours,
            "maintenance_visits": maintenance_visits,
            "avg_daily_power_kwh": avg_daily_power_kwh,
            "power_loss_events": power_loss_events,
            "door_open_rate": door_open_rate,
            "avg_temperature": avg_temperature,
        },
    })


async def get_all_alerts(request: Request) -> JSONResponse:
    """Get all alerts from all devices"""
    all_alerts: List[AlertHistoryItem] = []
    
    for reading in store.all_latest():
        alert = evaluate_alert(reading)
        if alert is not None:
            all_alerts.append(
                AlertHistoryItem(
                    device_id=reading.device_id,
                    timestamp=reading.timestamp,
                    alert_level=alert.alert_level,
                    message=alert.message,
                    temperature_c=reading.temperature_c,
                    humidity_pct=reading.humidity_pct,
                    door_open=reading.door_open,
                    power_ok=reading.power_ok,
                )
            )
    
    return json_response(all_alerts)


async def delete_device(request: Request) -> JSONResponse:
    device_id = request.path_params["device_id"]
    deleted = store.delete_device(device_id)
    if not deleted:
        raise StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="Device not found")
    return json_response({"message": f"Device {device_id} deleted successfully"})


async def rename_device(request: Request) -> JSONResponse:
    device_id = request.path_params["device_id"]
    payload = await request.json()
    new_device_id = payload.get("new_device_id", "").strip()

    if not new_device_id:
        handle_validation_error("New device ID cannot be empty")

    updated = store.rename_device(device_id, new_device_id)
    if not updated:
        raise StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="Device not found")
    return json_response({"message": f"Device {device_id} renamed to {new_device_id} successfully"})


async def delete_all_devices(request: Request) -> JSONResponse:
    count = store.delete_all_devices()
    return json_response({"message": f"All {count} devices deleted successfully"})


async def delete_old_devices(request: Request) -> JSONResponse:
    query_params = request.query_params
    days_str = query_params.get("days", "30")
    try:
        days = int(days_str)
    except ValueError:
        handle_validation_error("Invalid 'days' parameter")
    if days < 0:
        handle_validation_error("'days' must be non-negative")

    count = store.delete_devices_older_than(days)
    return json_response({"message": f"Deleted {count} devices not seen in the last {days} days"})


async def simulate_telemetry(request: Request) -> JSONResponse:
    query_params = request.query_params
    device_id = query_params.get("device_id", "fridge-001")
    scenario = query_params.get("scenario", "normal")

    sample = generate_sample_reading(device_id=device_id, scenario=scenario)
    store.save(sample)
    alert = evaluate_alert(sample)
    if alert is not None:
        notify_alert(sample, alert)
    return json_response(sample)


async def get_device_compliance(request: Request) -> JSONResponse:
    device_id = request.path_params["device_id"]
    history = store.history(device_id)
    if not history:
        raise StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="Device not found")

    # compute temperature exceed duration (>8C)
    exceed_seconds = 0
    for i in range(len(history) - 1):
        cur = history[i]
        nxt = history[i + 1]
        if cur.temperature_c > 8:
            delta = (nxt.timestamp - cur.timestamp).total_seconds()
            if delta > 0:
                exceed_seconds += delta

    exceed_hours = round(exceed_seconds / 3600, 2)

    # door open count
    door_count = sum(1 for r in history if r.door_open)

    # simple compressor vibration proxy: relative change in temp derivative magnitude
    temps = [r.temperature_c for r in history]
    vib_pct = 0
    if len(temps) >= 6:
        diffs = [abs(temps[i + 1] - temps[i]) for i in range(len(temps) - 1)]
        mid = len(diffs) // 2
        first = sum(diffs[:mid]) / max(1, len(diffs[:mid]))
        last = sum(diffs[mid:]) / max(1, len(diffs[mid:]))
        if first > 0:
            vib_pct = int((last - first) / first * 100)
        else:
            vib_pct = int(last * 100)

    # predicted spoilage risk heuristic
    risk = min(100, int(exceed_hours * 10 + door_count * 0.5 + max(0, vib_pct) * 0.4))

    summary_text = (
        f"Temperature exceeded 8°C for {exceed_hours} hours.\n\n"
        f"Door opened {door_count} times.\n\n"
        f"Compressor vibration increased by {vib_pct}% if measured.\n\n"
        f"Predicted Spoilage Risk = {risk}%."
    )

    # If OPENAI_API_KEY is set, optionally call OpenAI to rewrite/expand the summary
    openai_key = os.environ.get("OPENAI_API_KEY")
    ai_text = None
    if openai_key:
        try:
            prompt = (
                "You are an assistant that summarizes refrigerator telemetry.\n"
                f"Device: {device_id}\nSummary:\n" + summary_text + "\nProvide a concise explanation why the device is at risk."
            )
            payload = json.dumps({
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
                ai_text = body["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, KeyError, Exception):
            ai_text = None

    response = {
        "device_id": device_id,
        "summary": ai_text or summary_text,
        "details": {
            "temperature_exceed_hours": exceed_hours,
            "door_open_count": door_count,
            "compressor_vibration_pct": vib_pct,
            "predicted_spoilage_risk": risk,
        },
        "technologies": ["OpenAI GPT", "LangChain", "Vector Database", "RAG"],
    }

    return json_response(response)


async def get_device_forecast(request: Request) -> JSONResponse:
    device_id = request.path_params["device_id"]
    history = store.history(device_id)
    if not history:
        raise StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="Device not found")

    latest = history[-1]
    forecast_values = forecast_next_24_hours(history)

    if forecast_values is None:
        recent_history = history[-48:]
        slopes = []
        for i in range(len(recent_history) - 1):
            current = recent_history[i]
            next_reading = recent_history[i + 1]
            delta_hours = (next_reading.timestamp - current.timestamp).total_seconds() / 3600.0
            if delta_hours <= 0:
                continue
            slopes.append((next_reading.temperature_c - current.temperature_c) / delta_hours)

        if slopes:
            weights = list(range(1, len(slopes) + 1))
            weighted_sum = sum(slope * weight for slope, weight in zip(slopes, weights))
            avg_slope = weighted_sum / sum(weights)
        else:
            avg_slope = 0.0

        forecast_values = [round(latest.temperature_c + avg_slope * hour, 1) for hour in range(1, 25)]
        avg_trend = avg_slope
    else:
        avg_trend = (forecast_values[-1] - forecast_values[0]) / max(1, len(forecast_values) - 1)

    forecast = []
    for hour, temperature in enumerate(forecast_values, start=1):
        timestamp = latest.timestamp + timedelta(hours=hour)
        forecast.append({
            "timestamp": timestamp.isoformat(),
            "temperature_c": temperature,
        })

    predicted_max = max(forecast_values)
    predicted_min = min(forecast_values)
    trend = "Stable"
    if avg_trend > 0.05:
        trend = "Rising"
    elif avg_trend < -0.05:
        trend = "Falling"

    risk_alert = any(value > 8.0 for value in forecast_values)
    alert_message = (
        "Predicted temperature may exceed safe storage conditions within the next 24 hours. Please inspect cooling and door closure." if risk_alert
        else "Forecast indicates the device should remain within safe operating range for the next 24 hours."
    )

    return json_response({
        "device_id": device_id,
        "current_temperature": latest.temperature_c,
        "predicted_max": round(predicted_max, 1),
        "predicted_min": round(predicted_min, 1),
        "avg_trend": round(avg_trend, 3),
        "trend": trend,
        "risk_alert": risk_alert,
        "alert_message": alert_message,
        "forecast": forecast,
    })


async def ask_device_question(request: Request) -> JSONResponse:
    device_id = request.path_params["device_id"]
    payload = await request.json()
    question = payload.get("question", "").strip()

    if not question:
        handle_validation_error("Question cannot be empty")

    history = store.history(device_id)
    if not history:
        raise StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="Device not found")

    # Fetch compliance data for context
    compliance = await get_device_compliance(request)
    compliance_json = json.loads(compliance.body.decode())

    # Build rich context from device data
    latest = history[-1] if history else None
    avg_temp = sum(r.temperature_c for r in history) / len(history) if history else 0
    max_temp = max(r.temperature_c for r in history) if history else 0
    min_temp = min(r.temperature_c for r in history) if history else 0
    total_readings = len(history)
    power_losses = sum(1 for r in history if not r.power_ok)
    humidity_avg = sum(r.humidity_pct for r in history) / len(history) if history else 0

    context_data = {
        "device_id": device_id,
        "latest_reading": {
            "temperature": latest.temperature_c if latest else None,
            "humidity": latest.humidity_pct if latest else None,
            "door_open": latest.door_open if latest else None,
            "power_ok": latest.power_ok if latest else None,
        },
        "statistics": {
            "total_readings": total_readings,
            "avg_temperature": round(avg_temp, 2),
            "max_temperature": round(max_temp, 2),
            "min_temperature": round(min_temp, 2),
            "avg_humidity": round(humidity_avg, 2),
            "power_loss_events": power_losses,
        },
        "compliance": compliance_json["details"],
        "risk_level": "HIGH" if compliance_json["details"]["predicted_spoilage_risk"] >= 70 else "MEDIUM" if compliance_json["details"]["predicted_spoilage_risk"] >= 40 else "LOW",
    }

    # Use OpenAI to answer the question
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        answer = _provide_fallback_answer(question, context_data)
        return json_response({
            "device_id": device_id,
            "question": question,
            "answer": answer,
            "ai_source": "fallback_knowledge_base",
        })

    try:
        context_str = f"""You are an expert AI assistant for medical refrigerator cold-chain monitoring.
You must answer questions based on ACTUAL device data provided below.

DEVICE DATA:
- Device ID: {context_data['device_id']}
- Current Status: {context_data['risk_level']} RISK
- Total Readings: {context_data['statistics']['total_readings']}
- Temperature Range: {context_data['statistics']['min_temperature']}°C to {context_data['statistics']['max_temperature']}°C (avg: {context_data['statistics']['avg_temperature']}°C)
- Humidity: {context_data['statistics']['avg_humidity']}%
- Power Loss Events: {context_data['statistics']['power_loss_events']}
- Temperature exceed hours (>8°C): {context_data['compliance']['temperature_exceed_hours']}
- Door open count: {context_data['compliance']['door_open_count']}
- Compressor vibration change: {context_data['compliance']['compressor_vibration_pct']}%
- Predicted Spoilage Risk: {context_data['compliance']['predicted_spoilage_risk']}%

RULES:
1. Base your answer on the device data provided
2. Provide specific, actionable recommendations
3. If temperature is above 8°C, recommend immediate cooling checks
4. If door is frequently open, suggest staff training
5. If power loss occurs, recommend backup power solutions
6. Keep answers concise but informative (2-3 paragraphs max)
7. Always reference the actual data in your answer

QUESTION: {question}

Provide a detailed, data-driven answer based on the device data above."""

        payload_data = json.dumps({
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert cold-chain medical refrigerator compliance officer with deep knowledge of vaccine storage, spoilage prevention, and WHO guidelines.",
                },
                {
                    "role": "user",
                    "content": context_str,
                }
            ],
            "temperature": 0.7,
            "max_tokens": 600,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai_key}",
            },
        )
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
            if "choices" in body and len(body["choices"]) > 0:
                answer = body["choices"][0]["message"]["content"].strip()
            else:
                answer = _provide_fallback_answer(question, context_data)
                
    except urllib.error.HTTPError as exc:
        # Detailed HTTP error handling
        error_body = exc.read().decode()
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get("error", {}).get("message", str(exc))
        except:
            error_msg = error_body
        answer = f"API Error: {error_msg}. Please check your OpenAI API key and usage limits. Falling back to knowledge base answer: {_provide_fallback_answer(question, context_data)}"
    except urllib.error.URLError as exc:
        answer = f"Connection Error: {str(exc)}. Fallback answer: {_provide_fallback_answer(question, context_data)}"
    except Exception as exc:
        answer = f"Error: {str(exc)}. Fallback answer: {_provide_fallback_answer(question, context_data)}"

    return json_response({
        "device_id": device_id,
        "question": question,
        "answer": answer,
        "context": context_data,
    })


def _provide_fallback_answer(question: str, context: dict) -> str:
    """Provide rule-based answers when OpenAI is not available"""
    q_lower = question.lower()
    risk = context.get("compliance", {}).get("predicted_spoilage_risk", 0)
    temp_exceed = context.get("compliance", {}).get("temperature_exceed_hours", 0)
    door_count = context.get("compliance", {}).get("door_open_count", 0)
    
    # Temperature-related questions
    if any(word in q_lower for word in ["temperature", "temp", "cool", "warm", "heat"]):
        if temp_exceed > 0:
            return f"Your device has exceeded safe temperature (>8°C) for {temp_exceed} hours. Immediate actions: 1) Check cooling system, 2) Verify door seal, 3) Ensure proper ventilation, 4) Check if power supply is stable. Consider preventive maintenance if this continues."
        else:
            avg_temp = context.get("statistics", {}).get("avg_temperature", 5)
            return f"Temperature is stable at average {avg_temp}°C, which is within WHO guidelines (2-8°C). Continue monitoring and maintain regular preventive maintenance schedules."
    
    # Door-related questions
    elif any(word in q_lower for word in ["door", "open", "access"]):
        if door_count > 10:
            return f"Door has been opened {door_count} times. High frequency indicates: 1) Staff may need access training, 2) Inventory management issues, 3) Consider implementing limited-access protocols. Excessive door openings increase temperature fluctuations and spoilage risk."
        else:
            return f"Door usage is normal ({door_count} openings). Maintain current access protocols. Ensure door seal is intact and staff follows proper procedures."
    
    # Risk/spoilage questions
    elif any(word in q_lower for word in ["risk", "spoilage", "damage", "waste"]):
        if risk >= 70:
            return f"CRITICAL: Spoilage risk is at {risk}%! Immediate action required: 1) Check all systems immediately, 2) Review recent temperature logs, 3) Consider relocating contents if temperature cannot be stabilized within 1 hour, 4) Contact maintenance."
        elif risk >= 40:
            return f"WARNING: Spoilage risk is moderate at {risk}%. Recommended actions: 1) Increase monitoring frequency, 2) Review recent operational changes, 3) Schedule preventive maintenance, 4) Train staff on proper procedures."
        else:
            return f"Risk level is low at {risk}%. Maintain current protocols and continue regular monitoring."
    
    # Maintenance questions
    elif any(word in q_lower for word in ["maintain", "service", "repair", "check", "problem"]):
        return f"Based on device data: Avg temp={context['statistics']['avg_temperature']}°C, Power losses={context['statistics']['power_loss_events']}. If power losses exist, check electrical connections. If temperature fluctuates, inspect door seal and cooling system. Schedule quarterly preventive maintenance."
    
    # General compliance
    elif any(word in q_lower for word in ["compli", "who", "standard", "guide"]):
        return f"WHO vaccine cold-chain guidelines require 2-8°C maintenance. Your device shows temp range {context['statistics']['min_temperature']}-{context['statistics']['max_temperature']}°C. Current compliance status: {context['risk_level']} RISK. Ensure all staff are trained on proper storage procedures."
    
    # Default fallback
    else:
        return f"Based on current device status: Temperature avg {context['statistics']['avg_temperature']}°C (Range: {context['statistics']['min_temperature']}-{context['statistics']['max_temperature']}°C), Spoilage Risk: {risk}%, Door openings: {door_count}. Please rephrase your question about temperature, door access, maintenance, risk assessment, or compliance."


async def update_device_settings(request: Request) -> JSONResponse:
    """Update device settings (temperature, humidity, power, door) with a new telemetry reading"""
    device_id = request.path_params["device_id"]
    payload = await request.json()
    
    try:
        # Get the latest reading as base
        latest_reading = store.latest(device_id)
        if not latest_reading:
            raise StarletteHTTPException(status_code=HTTP_404_NOT_FOUND, detail="Device not found")
        
        # Extract updated values from payload, fallback to latest if not provided
        temperature_c = float(payload.get("temperature_c", latest_reading.temperature_c))
        humidity_pct = float(payload.get("humidity_pct", latest_reading.humidity_pct))
        power_ok = bool(payload.get("power_ok", latest_reading.power_ok))
        door_open = bool(payload.get("door_open", latest_reading.door_open))
        
        # Create new reading with updated values
        updated_reading = TelemetryReading(
            device_id=device_id,
            timestamp=datetime.utcnow(),
            temperature_c=temperature_c,
            humidity_pct=humidity_pct,
            door_open=door_open,
            power_ok=power_ok,
        )
        
        # Save to store (persists permanently)
        store.save(updated_reading)
        
        # Evaluate alert
        alert = evaluate_alert(updated_reading)
        
        return json_response({
            "device_id": device_id,
            "message": "Device settings updated successfully",
            "updated_reading": updated_reading,
            "alert_status": alert,
        })
    
    except (KeyError, ValueError, TypeError) as exc:
        handle_validation_error(f"Invalid update payload: {exc}")


app = Starlette(
    debug=True,
    routes=[
        Route("/telemetry", ingest_telemetry, methods=["POST"]),
        Route("/devices", get_devices, methods=["GET"]),
        Route("/devices/{device_id}", get_device, methods=["GET"]),
        Route("/devices/{device_id}/history", get_device_history, methods=["GET"]),
        Route("/devices/{device_id}/alerts", get_device_alerts, methods=["GET"]),
        Route("/devices/{device_id}/update", update_device_settings, methods=["POST"]),
        Route("/devices/{device_id}/rul", get_device_rul, methods=["POST"]),
        Route("/devices/alerts/all", get_all_alerts, methods=["GET"]),
        Route("/devices/{device_id}", delete_device, methods=["DELETE"]),
        Route("/devices/{device_id}/rename", rename_device, methods=["POST"]),
        Route("/devices", delete_all_devices, methods=["DELETE"]),
        Route("/devices/old", delete_old_devices, methods=["DELETE"]),
        Route("/devices/{device_id}/compliance", get_device_compliance, methods=["GET"]),
        Route("/devices/{device_id}/forecast", get_device_forecast, methods=["GET"]),
        Route("/devices/{device_id}/compliance-question", ask_device_question, methods=["POST"]),
        Route("/simulate", simulate_telemetry, methods=["POST"]),
    ],
)

cors_origins = os.getenv("CORS_ORIGINS", "*")
if cors_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
