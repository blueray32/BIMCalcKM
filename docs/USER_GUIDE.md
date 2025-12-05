# BIMCalc User Guide

Welcome to BIMCalc, the automated cost-matching engine for BIM projects.

## Getting Started

### Login
Access BIMCalc at `http://localhost:8000` (or your organization's URL). Log in using your credentials.

### Dashboard
The dashboard provides an overview of your projects, recent matches, and cost trends.
- **Key Metrics**: Total matched items, pending reviews, total project value.
- **Recent Activity**: See the latest actions taken by you and your team.

## Core Features

### 1. Ingestion
Upload your Revit schedules (CSV/XLSX) to start the matching process.
- Navigate to **Ingestion**.
- Select your file and project.
- Click **Upload**.

### 2. Matching
BIMCalc automatically matches your Revit items to vendor price books.
- **Auto-Match**: High-confidence matches are approved automatically.
- **Review Queue**: Items with low confidence or flags (e.g., size mismatch) appear here for manual review.

### 3. Review
Review pending matches in the **Review** tab.
- **Approve**: Confirm a suggested match.
- **Reject**: Discard a match and search manually.
- **Flags**: Pay attention to warnings like "Size Mismatch" or "Unit Conflict".

### 4. Search
Use the **Search** bar to find items, prices, or documents.
- **Natural Language**: Type queries like "fire rated doors" or "DN100 elbows".
- **Filters**: Narrow down results by category, vendor, or project.

### 5. Reporting
Generate detailed cost reports.
- Navigate to **Reports**.
- Select your project and report type (e.g., "Cost Summary").
- Download as PDF or Excel.

## Support
For assistance, contact your internal BIMCalc administrator or email support@bimcalc.com.
