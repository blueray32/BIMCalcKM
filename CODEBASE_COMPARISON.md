# Codebase Comparison: Engineering the AI Codebase

This document compares the current `BIMCalc` codebase against the principles outlined in *Engineering the AI Codebase*.

## Executive Summary

The `BIMCalc` codebase is well-positioned with modern **Tooling** and **Observability** that align closely with AI-ready standards. However, the **Architecture** follows a traditional Layered/Modular Monolith hybrid rather than the strict **Vertical Slice Architecture (VSA)** advocated in the reference. Transitioning to VSA would significantly improve the codebase's "digestibility" for AI agents by increasing context isolation.

## Detailed Comparison

### 1. Architecture: Vertical Slices vs. Layers

| Feature | PDF Recommendation (VSA) | BIMCalc Current State | Alignment |
| :--- | :--- | :--- | :--- |
| **Feature Organization** | All code for a feature (Routes, DB, Logic) is in one folder. | Logic is modular (`bimcalc/reporting`), but Web/UI is centralized (`bimcalc/web`). | ⚠️ **Partial** |
| **Web Layer** | `app/feature/routes.py` | `bimcalc/web/routes/*.py` (Centralized) | ❌ **Divergent** |
| **Context Isolation** | High. Agent sees everything in one dir. | Medium. Agent must jump between `web/routes`, `web/templates`, and `core/logic`. | ⚠️ **Partial** |

**Analysis**:
The codebase uses a "Modular Monolith" approach where business logic is separated into domains (`ingestion`, `matching`, `reporting`), which is good. However, the interface layer (`web`) is completely decoupled and centralized.
*   **Reference**: "Trying to use powerful AI agents in a traditional layered codebase is like running a diesel generator to charge a Tesla."
*   **Impact**: To modify the "Ingestion" feature, an agent currently needs to touch:
    1.  `bimcalc/ingestion/*` (Logic)
    2.  `bimcalc/web/routes/ingestion.py` (Routes)
    3.  `bimcalc/web/templates/ingestion/*.html` (UI)
    This increases "context switching" and token usage.

### 2. Infrastructure Pillars

The PDF outlines 7 pillars for AI-ready infrastructure. Here is how BIMCalc scores:

| Pillar | Status | Notes |
| :--- | :--- | :--- |
| **Grep-ability** | ✅ **Good** | Code uses clear naming conventions. |
| **Glob-ability** | ✅ **Good** | Predictable structure, though layered. |
| **Architectural Boundaries** | ⚠️ **Partial** | No strict linting rules enforcing layer boundaries (e.g. `import-linter`) observed yet. |
| **Security** | ✅ **Good** | `ruff` includes security checks (e.g. `S` rules, though some ignored). |
| **Testability** | ⚠️ **Divergent** | Tests are in a central `tests/` directory. PDF advocates collocating tests with code (`app/feature/tests/`) for context. |
| **Observability** | ✅ **Excellent** | Uses `structlog` with JSON support configured in `bimcalc/core/logging.py`. |
| **Documentation** | ❌ **Gap** | **Zero** `README.md` files found inside feature directories (`bimcalc/*`). PDF requires a README for *every* feature slice to explain intent to agents. |

### 3. Tooling

| Tool | PDF Recommendation | BIMCalc Usage |
| :--- | :--- | :--- |
| **Linting** | `ruff` | ✅ Used (`pyproject.toml`) |
| **Typing** | `mypy` (strict) | ✅ Used (`pyproject.toml`) |
| **Package Manager** | `uv` | ❓ Not explicit, but compatible. |

## Recommendations for "AI-Readiness"

To align with the *Engineering the AI Codebase* standard, the following steps are recommended:

1.  **Migrate to Vertical Slices**:
    *   Move `bimcalc/web/routes/ingestion.py` -> `bimcalc/ingestion/routes.py`.
    *   Move `bimcalc/web/templates/ingestion/` -> `bimcalc/ingestion/templates/`.
    *   Update `main.py` (or `app.py`) to dynamically include routers from feature modules.

2.  **Add Context Documentation**:
    *   Add a `README.md` to every major folder (`bimcalc/matching`, `bimcalc/reporting`, etc.) describing **what** it does and **how** it interacts with other modules. This is the highest ROI change for AI performance.

3.  **Collocate Tests**:
    *   Move `tests/unit/test_ingestion.py` -> `bimcalc/ingestion/tests/test_unit.py`.

4.  **Enforce Boundaries**:
    *   Configure `ruff` or `import-linter` to forbid `bimcalc/ingestion` from importing `bimcalc/reporting` (if that is a rule), ensuring clean DAG dependencies.
