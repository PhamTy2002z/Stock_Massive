# Codebase Summary

This document provides a high-level overview of the codebase, focusing on recent changes related to the Volume Anomaly Detection feature.

## Recent Updates (Phase 03: Frontend Integration of Volume Anomaly Detection)

This phase completes the frontend integration of the Volume Anomaly Detection feature, making it fully accessible and interactive within the stock detail page.

### 1. Key Components Introduced/Modified:

- **`useVolumeAnalysis`**:
  - **Description**: React Query hook for fetching volume anomaly data from the backend API, now integrated into the frontend for display.
  - **Location**: `apps/web/src/hooks/use-volume-analysis.ts`

- **`StockDetailTabs`**:
  - **Description**: Modified to include the "Khối Lượng" (Volume) tab as the fourth tab in the stock detail page.
  - **Location**: `apps/web/src/components/dashboard/stock-detail-tabs.tsx`

- **`StockDetailClient`**:
  - **Description**: Integrates the `VolumeTabContent` component, making the volume anomaly feature available on the stock detail page.
  - **Location**: `apps/web/src/components/dashboard/stock-detail-client.tsx`

- **`VolumeTabContent`**:
  - **Description**: Wrapper component for the volume anomaly chart, including the baseline selector, refresh button, and handling loading/error states.
  - **Location**: `apps/web/src/components/dashboard/volume-tab-content.tsx`

- **`Dashboard Index Export`**:
  - **Description**: Ensures `VolumeTabContent` is exported for use within other dashboard components.
  - **Location**: `apps/web/src/components/dashboard/index.ts`

### 2. Features Integrated:

-   **Volume Tab**: A new "Khối Lượng" (Volume) tab is added as the 4th tab in the stock detail page, providing dedicated access to volume anomaly analysis.
-   **Baseline Selector**: Users can now select baseline periods (10/20/30/60 days) to customize the volume anomaly calculation.
-   **Refresh Button**: A refresh button with an associated loading state allows users to manually update the volume anomaly data.
-   **Error Handling with Retry**: Robust error handling is implemented, including the ability to retry fetching data in case of issues.
-   **Info Card**: An informative card is displayed, explaining the different anomaly levels to the user.
-   **Vietnamese Localization**: All new UI elements and messages are fully localized in Vietnamese for a seamless user experience.

## Recent Updates (Phase 02: Frontend Chart for Volume Anomaly Detection)

This phase introduces the frontend visualization for volume anomaly detection, providing a clear and interactive chart to analyze stock volume.

### 1. Key Components Introduced/Modified:

-   **`VolumeAnomalyChart`**:
    -   **Description**: React component responsible for rendering the volume anomaly bar chart with color-coded anomaly levels, baseline average, and hover tooltips.
    -   **Location**: `apps/web/src/components/dashboard/volume-anomaly-chart.tsx`

-   **`VolumeTabContent`**:
    -   **Description**: Wrapper component for the volume anomaly chart, including the baseline selector and handling loading/error states.
    -   **Location**: `apps/web/src/components/dashboard/volume-tab-content.tsx`

-   **`useVolumeAnalysis`**:
    -   **Description**: Custom React Query hook for fetching volume anomaly data from the backend API.
    -   **Location**: `apps/web/src/hooks/use-volume-analysis.ts`

-   **API Integration**:
    -   **Description**: Added `VolumeAnomalyResponse` types and `fetchVolumeAnomalies` function for seamless API communication.
    -   **Location**: `apps/web/src/lib/api.ts`

-   **UI Integration**:
    -   **Description**:
        -   Exported new components from `apps/web/src/components/dashboard/index.ts`.
        -   Added a new "Khối Lượng" (Volume) tab to `stock-detail-tabs.tsx`.
        -   Integrated `VolumeTabContent` into `stock-detail-client.tsx`.
    -   **Locations**:
        -   `apps/web/src/components/dashboard/index.ts`
        -   `apps/web/src/components/dashboard/stock-detail-tabs.tsx`
        -   `apps/web/src/components/dashboard/stock-detail-client.tsx`

### 2. Features Added:

-   Volume anomaly bar chart displayed in 5-minute intervals (72 bars).
-   Color-coded representation of anomaly levels: normal, elevated, high, and very high.
-   Overlay baseline average line for easy comparison.
-   Interactive hover tooltips displaying volume, ratio, and anomaly status.
-   User-selectable baseline average (10/20/30/60 days).
-   Robust loading skeletons and error state handling.
-   Full Vietnamese localization for the user interface.

## Recent Updates (Phase 01: Backend API Enhancement of Volume Anomaly Detection)

The following core components have been introduced or modified:

### 1. API Endpoints

-   **`/api/v1/stocks/{symbol}/volume-anomalies` (GET)**:
    -   **Description**: This new endpoint retrieves volume anomaly detection results for a given stock symbol.
    -   **Location**: `apps/api/src/stocks/price/router.py`

### 2. Core Logic & Schemas

-   **Volume Anomaly Detection Logic**:
    -   **Method**: `detect_volume_anomalies()`
    -   **Location**: `apps/api/src/stocks/intraday_collector.py`
    -   **Description**: This method is responsible for identifying significant deviations in trading volume for a stock.

-   **Data Models (Pydantic Schemas)**:
    -   **`VolumeAnomalyLevel`**: Defines different levels or categories of volume anomalies.
    -   **`VolumeTimeSlot`**: Represents a specific time interval within which volume anomalies are detected.
    -   **`VolumeAnomalyResponse`**: Structures the response returned by the volume anomaly detection API, including anomaly levels and time slots.
    -   **Location**: `apps/api/src/stocks/schemas/price.py`

### 3. Dependencies

-   **`greenlet`**: Added to `apps/api/requirements.txt`.
-   **`pandas`**: Added to `apps/api/requirements.txt`.
    -   **Purpose**: These libraries are crucial for data manipulation and potentially for asynchronous operations within the volume anomaly detection process.

## Overall Structure

The codebase is structured into `apps/api` (for backend services) and `apps/web` (for the frontend). The `docs` directory contains project documentation.

## Top 5 Files by Token Count (as per Repomix)

1.  `apps/web/tsconfig.tsbuildinfo` (61,455 tokens)
2.  `apps/web/src/components/dashboard/finance-tab-content.tsx` (8,532 tokens)
3.  `apps/web/src/components/ui/sidebar.tsx` (6,104 tokens)
4.  `plans/reports/tester-251220-1450-volume-anomaly-frontend-integration.md` (4,911 tokens)
5.  `apps/web/src/components/dashboard/sector-performance.tsx` (2,424 tokens)

This summary will be updated periodically to reflect the latest state of the codebase.