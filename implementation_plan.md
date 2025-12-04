# Implementation Plan: Vertical Slice Architecture Refactoring

This plan outlines the steps to migrate the `BIMCalc` codebase to a **Vertical Slice Architecture** as recommended in *Engineering the AI Codebase*.

## Goal
Improve codebase "digestibility" for AI agents and developers by co-locating all code related to a feature (routes, logic, templates, tests) in a single directory.

## Phase 1: Pilot Migration (`ingestion` module)

We will start by migrating the `ingestion` module to validate the pattern.

### 1. File Restructuring
- [x] **Routes**: Move `bimcalc/web/routes/ingestion.py` → `bimcalc/ingestion/routes.py`
- [x] **Templates**: Move `bimcalc/web/templates/ingestion/` → `bimcalc/ingestion/templates/ingestion/`
- [x] **Documentation**: Create `bimcalc/ingestion/README.md` explaining the module's purpose and dependencies.

### 2. Application Configuration Updates
- [x] **Router Registration**: Update `bimcalc/web/app_enhanced.py` to import the ingestion router from its new location.
- [x] **Template Loading**: Update `bimcalc/web/app_enhanced.py` to include `bimcalc/ingestion/templates` in the Jinja2 template search paths.

### 3. Verification
- [x] Verify that ingestion pages (upload, history) still load correctly.
- [x] Verify that imports in `bimcalc/ingestion/routes.py` are correct (relative imports might need adjustment).

## Phase 2: Rollout (Subsequent Features)

### Reporting Module
- [x] **Routes**: Move `bimcalc/web/routes/reports.py` → `bimcalc/reporting/routes.py`
- [x] **Templates**: Move `reports.html`, `reports_executive.html`, `statistics.html`, `report_builder.html` → `bimcalc/reporting/templates/reporting/`
- [x] **Config**: Update `app_enhanced.py` and `routes/__init__.py`
- [x] **Docs**: Add `bimcalc/reporting/README.md`

### Remaining Features
- [ ] `matching`
- [ ] `compliance`

## Phase 3: Documentation & Boundaries
- [ ] Add `README.md` to all remaining top-level feature directories.
- [ ] (Optional) Configure linting rules to enforce boundaries.
