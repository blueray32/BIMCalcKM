# Ingestion Module

This module handles the ingestion of data into BIMCalc, including:
- Revit Schedules (CSV/XLSX)
- Supplier Price Books (CSV/XLSX)

## Architecture
This module follows the Vertical Slice Architecture. All components related to ingestion are co-located here.

### Components
- `routes.py`: FastAPI routes for UI and API endpoints.
- `templates/`: Jinja2 templates for the ingestion UI.
- `schedules.py`: Logic for parsing and ingesting Revit schedules.
- `pricebooks.py`: Logic for parsing and ingesting price books.

## Usage
The main entry point is the `/ingest` route, which provides the file upload UI.
