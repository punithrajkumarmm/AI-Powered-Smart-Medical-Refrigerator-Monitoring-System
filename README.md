# AI-Powered Smart Medical Refrigerator Monitoring System

A full-stack monitoring system for medical refrigerators with a FastAPI backend and React dashboard.

## Features

- Temperature and humidity telemetry ingest API
- Smart alerts for door state, temperature, humidity, and power events
- Dashboard showing latest readings, alarm status, and device health
- Simulated device telemetry endpoints for prototype and testing

## Prerequisites

- Python 3.10+ for the backend
- Node.js 12+ for the frontend dashboard
- On Windows, Visual Studio Build Tools may be required for Python packages that compile native extensions

## Backend

The `backend` directory contains a FastAPI service and a sample telemetry simulator endpoint:

- `backend/app/main.py`: API routes, telemetry ingest, and simulation endpoints
- `backend/app/services.py`: monitoring and alert rules
- `backend/app/data_store.py`: SQLite-backed telemetry store
- `backend/app/simulator.py`: sample telemetry generation for alert scenarios
- `backend/app/schemas.py`: request/response models

Install dependencies and run the backend:

```powershell
cd backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Telemetry is now persisted to `backend/telemetry.db` using SQLite.

### Simulate telemetry

The backend includes a simulation endpoint for demo data and alerts:

```powershell
curl "http://localhost:8000/simulate?device_id=fridge-001&scenario=high_temperature" -X POST
```

Supported `scenario` values:
- `normal`
- `door_open`
- `high_temperature`
- `high_humidity`
- `power_loss`

### Device history

Persisted telemetry history is available for each device:

```powershell
curl "http://localhost:8000/devices/fridge-001/history"
```

The frontend dashboard now includes a device history chart showing temperature and humidity trends, along with alert event history.

Telemetry is persisted to `backend/telemetry.db` using SQLite.

### Alert notifications

Alert notifications are written to `backend/alert_notifications.log` when a telemetry sample triggers an alert. Configure recipients using environment variables:

- `ALERT_EMAIL_RECIPIENT`
- `ALERT_SMS_RECIPIENT`
- `ALERT_NOTIFICATION_LOG`

## Frontend

The `frontend` directory contains a React dashboard:

- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`

Install dependencies and run the frontend:

```powershell
cd frontend
npm install
npm start
```

## Notes

This scaffold provides a prototype-ready structure. Replace simulated device telemetry and in-memory storage with production hardware integration and persistent storage when ready.

## Deploying to Render

1. Push the repository to GitHub.
2. Create a new Render account and connect your GitHub repository.
3. Use the repository's `render.yaml` to deploy two services:
   - `smart-medical-refrigerator-backend` as a Python web service
   - `smart-medical-refrigerator-frontend` as a Node static site
4. After the backend service is live, set the frontend environment variable `REACT_APP_API_BASE` to the backend service URL (for example, `https://your-backend-service.onrender.com`).
5. Re-deploy the frontend service so it picks up the backend URL at build time.

### Render service settings

- Backend build command: `pip install -r backend/requirements.txt`
- Backend start command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Frontend build command: `cd frontend && npm install && npm run build`
- Frontend publish directory: `frontend/build`

> If you want a single-service deployment, you can also add backend static file serving later and use one web service instead of two.

## Project Documentation

A full project report is available in `PROJECT_REPORT.md`, including business understanding, system architecture, data pipeline, alert management, and future enhancements.
