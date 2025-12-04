# Reporting Module

This module handles report generation, executive dashboards, and project statistics.

## Architecture
This module follows the Vertical Slice Architecture.

### Components
- `routes.py`: FastAPI routes for reports and statistics.
- `templates/`: Jinja2 templates for reporting UI.
- `builder.py`: Logic for building reports.
- `financial_metrics.py`: Financial calculations.
- `dashboard_metrics.py`: Executive dashboard metrics.
- `analytics.py`: Analytics engine.

## Routes
- `/reports`: Main reports page.
- `/reports/statistics`: Statistics dashboard.
- `/reports/generate`: Download reports.
