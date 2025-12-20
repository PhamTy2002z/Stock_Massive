# Codebase Summary

This document provides a high-level overview of the codebase, focusing on recent changes related to the Volume Anomaly Detection feature.

## Recent Updates (Phase 01: Backend API Enhancement of Volume Anomaly Detection)

The following core components have been introduced or modified:

### 1. API Endpoints

- **`/api/v1/stocks/{symbol}/volume-anomalies` (GET)**:
  - **Description**: This new endpoint retrieves volume anomaly detection results for a given stock symbol.
  - **Location**: `apps/api/src/stocks/price/router.py`

### 2. Core Logic & Schemas

- **Volume Anomaly Detection Logic**:
  - **Method**: `detect_volume_anomalies()`
  - **Location**: `apps/api/src/stocks/intraday_collector.py`
  - **Description**: This method is responsible for identifying significant deviations in trading volume for a stock.

- **Data Models (Pydantic Schemas)**:
  - **`VolumeAnomalyLevel`**: Defines different levels or categories of volume anomalies.
  - **`VolumeTimeSlot`**: Represents a specific time interval within which volume anomalies are detected.
  - **`VolumeAnomalyResponse`**: Structures the response returned by the volume anomaly detection API, including anomaly levels and time slots.
  - **Location**: `apps/api/src/stocks/schemas/price.py`

### 3. Dependencies

- **`greenlet`**: Added to `apps/api/requirements.txt`.
- **`pandas`**: Added to `apps/api/requirements.txt`.
  - **Purpose**: These libraries are crucial for data manipulation and potentially for asynchronous operations within the volume anomaly detection process.

## Overall Structure

The codebase is structured into `apps/api` (for backend services) and `apps/web` (for the frontend). The `docs` directory contains project documentation.

## Top 5 Files by Token Count (as per Repomix)

1.  `apps/web/tsconfig.tsbuildinfo` (49,741 tokens)
2.  `apps/api/src/stocks/service_old.py` (14,162 tokens)
3.  `apps/web/src/components/dashboard/finance-tab-content.tsx` (8,532 tokens)
4.  `apps/api/src/stocks/financial/service.py` (6,144 tokens)
5.  `apps/web/src/components/ui/sidebar.tsx` (6,104 tokens)

This summary will be updated periodically to reflect the latest state of the codebase.