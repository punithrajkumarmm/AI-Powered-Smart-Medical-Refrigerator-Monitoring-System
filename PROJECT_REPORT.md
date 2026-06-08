# Smart Medical Refrigerator Monitoring System

## Overview
This project is an AI-powered monitoring solution for medical refrigerators, combining a FastAPI backend, React dashboard, and simulated IoT telemetry. It supports real-time monitoring, alerting, and historical analysis for temperature-sensitive medical supplies.

## Problem Statement
Medical refrigerators need constant environmental control to preserve vaccines, biological samples, and temperature-sensitive medications. Failures in temperature management, power continuity, or door security can cause spoilage and regulatory non-compliance.

## Objectives of the Project
- Monitor refrigerator temperature, humidity, door state, and power status.
- Detect anomalies and health rule violations in real time.
- Store telemetry with persistence for historical analysis.
- Provide a dashboard for operators and stakeholders.
- Simulate device telemetry and alert scenarios for testing.

## Business Understanding
Healthcare organizations need reliable systems to ensure cold chain integrity. This project enables operations teams to identify issues quickly, reduce waste, and maintain compliance with medical storage regulations.

## Requirement Analysis
Functional requirements:
- Telemetry ingestion API
- Real-time device status and alert evaluation
- Alert notification logging
- Historical telemetry and alert retrieval
- Web dashboard with simulator and history visualization

Non-functional requirements:
- Fast, responsive UI
- Persisted device history
- Extensible architecture for future AI models
- Compatibility with Windows-based development environments

## System Architecture
The solution uses a simple service architecture:
- FastAPI backend for API and alert logic
- SQLite storage for telemetry persistence
- React frontend for monitoring and history visualization
- Simulated telemetry generator for prototype scenarios

## Data Collection and IoT Sensors
The system models refrigerator sensors that capture:
- temperature (°C)
- humidity (%)
- door open state
- power status

Simulated IoT data is generated in `backend/app/simulator.py` and can be sent to `/simulate`.

## Data Engineering Pipeline
Telemetry is received by the backend, validated against Pydantic schemas, and written to SQLite via `backend/app/data_store.py`. This enables both live status queries and historical analysis.

## Data Preprocessing and ETL
Data is normalized in the ingestion pipeline. Timestamps are stored in ISO format, boolean values are converted to integers for SQLite, and alert rules are evaluated on each incoming sample.

## Exploratory Data Analysis (EDA)
The dashboard provides early EDA through device status cards, alert history, and time series charts. This helps identify patterns like rising temperature, humidity spikes, or repeated door openings.

## Feature Engineering
Current features include:
- Alert evaluation for temperature, humidity, door state, and power
- Simulation scenarios for normal and failure states
- Historical telemetry and alert retrieval
- Inline temperature and humidity trend charts

## Temperature Anomaly Detection
The system flags temperature readings outside the safe range of 2–8 °C. Critical alerts are generated immediately when a reading violates this threshold.

## Power Outage Prediction
While the current prototype logs power failures as alerts, the system is designed to support future predictive analytics for outage risk based on historical patterns.

## Compressor Failure Prediction
The foundation is present for compressor health monitoring by capturing temperature drift and power status. Future enhancements can add model-based failure prediction.

## Temperature Forecasting
The system currently visualizes historical temperature trends. Forecasting models can be added in future iterations using the persisted telemetry history.

## Remaining Useful Life (RUL) Prediction
RUL prediction is a future enhancement. With enough telemetry history, the system can evolve to predict component degradation and refrigeration lifecycle.

## Compliance Monitoring System
Alert rules enforce compliance thresholds and generate notifications for out-of-range conditions. The dashboard supports audit-style history review for device events.

## Alert Management System
Alerts are evaluated by `backend/app/services.py` and logged to `backend/alert_notifications.log` through `backend/app/notifications.py`. The dashboard displays historical alert events and active device status.

## Power BI Dashboard Development
A Power BI dashboard is a recommended future enhancement. The current React dashboard provides the same monitoring capabilities in a web UI.

## AWS Cloud Architecture
This prototype runs locally, but the architecture can migrate to AWS using:
- API Gateway + Lambda or ECS for backend
- RDS or DynamoDB for storage
- S3 and CloudFront for frontend hosting
- SNS for alert notifications

## AI Compliance Assistant
A future AI compliance assistant could review telemetry and alert history to provide recommendations, regulatory guidance, and audit summaries.

## Testing and Validation
- Backend Python modules were validated using `python -m py_compile`
- Frontend TypeScript was validated using `npx tsc --noEmit --project tsconfig.json`
- Simulation endpoint provides test telemetry scenarios

## Results and Discussion
The system demonstrates real-time monitoring, alerting, and historical analytics for refrigerator devices. It provides a foundation for enhanced predictive and compliance capabilities.

## Business Benefits
- Reduces product spoilage through early alerting
- Supports regulatory compliance with historical records
- Enables operations teams to monitor multiple devices centrally
- Provides a foundation for advanced AI-driven predictions

## Future Enhancements
- Add true predictive models for power outages and compressor failures
- Integrate with email/SMS gateways for real notifications
- Add user authentication and multi-device management
- Extend to cloud storage and scalable deployment
- Build a Power BI or BI reporting layer

## Conclusion
This project provides a functional prototype for smart medical refrigerator monitoring, combining real-time telemetry ingestion, alerting, persistence, and dashboard visualization. It is designed to scale with future AI and cloud enhancements.

## References
- FastAPI documentation
- React documentation
- SQLite documentation
- Medical cold chain compliance guidelines

## Appendices
- Code: See `backend/app` and `frontend/src`
- Dataset: Simulated telemetry generated in `backend/app/simulator.py`
- Architecture: FastAPI backend with React frontend and SQLite persistence
