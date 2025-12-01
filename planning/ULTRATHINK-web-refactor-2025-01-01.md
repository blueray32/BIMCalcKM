# ULTRATHINK Planning Document

**Feature**: Web Application Refactoring (app_enhanced.py modularization)
**Date**: 2025-01-01
**Author**: Claude Code (AI Agent)
**Trigger**: Large Refactoring (>500 lines) - **5,726 lines**

---

## 1. Overview

### What are we building/changing?

Refactor the monolithic `bimcalc/web/app_enhanced.py` (5,726 lines, 139 routes, 143 functions) into a modular, maintainable route-based architecture. The file has grown beyond manageable size and contains:
- Authentication and session management
- 15+ functional areas (ingestion, matching, review, reports, analytics, compliance, etc.)
- Multiple Pydantic models
- Complex business logic mixed with route handlers
- Template rendering
- API endpoints
- Integration points (Crail4, ACC, Intelligence)

This refactoring will improve:
- **Maintainability**: Easier to find and modify code
- **Testability**: Isolated route modules can be tested independently
- **Performance**: Faster module loading
- **Developer Experience**: Clear separation of concerns
- **Scalability**: Adding new features won't bloat a single file

### Why is ULTRATHINK needed?

- [x] **Large refactoring (>500 lines)** - 5,726 lines qualifies as HIGH VALUE trigger
- [ ] Database schema change
- [ ] New feature phase
- [ ] External integration
- [x] **Cross-cutting concern** - Affects entire web layer
- [ ] Performance-critical path
- [x] **Complex UI feature** - 139 routes across 15+ functional areas

**Risk Level**: HIGH - This touches the entire web UI, all routes, and user-facing functionality.

---

## 2. Impact Analysis

### Affected Modules

**Primary Changes:**
- `bimcalc/web/app_enhanced.py` - **SPLIT** into modular routes
- `bimcalc/web/` - New router modules will be created here

**Secondary Changes:**
- `bimcalc/web/auth.py` - May need adjustments for dependency injection
- `bimcalc/web/templates/` - Template paths may need updates (minimal)
- `tests/` - Test structure needs to align with new modules
- Documentation - API docs will reflect new structure

**Unaffected (explicitly protected):**
- `bimcalc/db/` - No database changes
- `bimcalc/matching/` - No matching logic changes
- `bimcalc/ingestion/` - No ingestion logic changes
- Business logic modules - Only route organization changes

### Affected Files (Detailed)

| File Path | Change Type | Lines Affected | Risk Level |
|-----------|-------------|----------------|------------|
| `bimcalc/web/app_enhanced.py` | Refactor/Split | ~5,726 → ~200 | HIGH |
| `bimcalc/web/routes/auth.py` | Create | ~150 | Low |
| `bimcalc/web/routes/ingestion.py` | Create | ~300 | Medium |
| `bimcalc/web/routes/matching.py` | Create | ~200 | Medium |
| `bimcalc/web/routes/review.py` | Create | ~250 | Medium |
| `bimcalc/web/routes/items.py` | Create | ~300 | Medium |
| `bimcalc/web/routes/mappings.py` | Create | ~150 | Low |
| `bimcalc/web/routes/reports.py` | Create | ~400 | Medium |
| `bimcalc/web/routes/pipeline.py` | Create | ~250 | Medium |
| `bimcalc/web/routes/analytics.py` | Create | ~500 | Medium |
| `bimcalc/web/routes/compliance.py` | Create | ~300 | Medium |
| `bimcalc/web/routes/projects.py` | Create | ~800 | High |
| `bimcalc/web/routes/documents.py` | Create | ~300 | Medium |
| `bimcalc/web/routes/classifications.py` | Create | ~200 | Low |
| `bimcalc/web/routes/crail4.py` | Create | ~300 | Medium |
| `bimcalc/web/routes/scenarios.py` | Create | ~150 | Low |
| `bimcalc/web/routes/risk.py` | Create | ~200 | Low |
| `bimcalc/web/routes/dashboard.py` | Create | ~300 | Medium |
| `bimcalc/web/models.py` | Create | ~200 | Low |
| `bimcalc/web/__init__.py` | Update | ~50 | Low |
| `tests/integration/test_web_*.py` | Create/Update | ~1,000 | Medium |

**Total New Lines**: ~5,500 (reorganized, not new code)
**Net Change**: Minimal (mostly moving code)

### Dependency Graph

```
app_enhanced.py (main app)
  │
  ├─> routes/auth.py ─────────> bimcalc.web.auth
  ├─> routes/dashboard.py ────> [templates, db.models]
  ├─> routes/ingestion.py ────> bimcalc.ingestion.*
  ├─> routes/matching.py ─────> bimcalc.matching.orchestrator
  ├─> routes/review.py ───────> bimcalc.review
  ├─> routes/items.py ────────> bimcalc.db.models
  ├─> routes/mappings.py ─────> bimcalc.db.models
  ├─> routes/reports.py ──────> bimcalc.reporting.*
  ├─> routes/pipeline.py ─────> bimcalc.pipeline.orchestrator
  ├─> routes/analytics.py ────> bimcalc.db.models (complex queries)
  ├─> routes/compliance.py ───> bimcalc.intelligence.compliance
  ├─> routes/projects.py ─────> bimcalc.db.models (multi-project)
  ├─> routes/documents.py ────> bimcalc.intelligence.document_processor
  ├─> routes/classifications.py > bimcalc.integration.classification_mapper
  ├─> routes/crail4.py ───────> bimcalc.integration.crail4_transformer
  ├─> routes/scenarios.py ────> bimcalc.db.models
  └─> routes/risk.py ─────────> bimcalc.intelligence.*

All routes depend on:
  - bimcalc.config
  - bimcalc.db.connection
  - bimcalc.web.auth (for @require_auth dependency)
```

---

## 3. Current State Analysis

### Existing Patterns

**Pattern 1: FastAPI Route Organization**
- **Location**: `bimcalc/intelligence/routes.py:1-200`
- **How it works**: Intelligence features already use APIRouter for modularization
  ```python
  from fastapi import APIRouter
  router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])
  # Routes defined on router, not app
  ```
- **Relevance**: We should follow this same pattern for all route modules

**Pattern 2: Dependency Injection for Auth**
- **Location**: `bimcalc/web/app_enhanced.py:234-355`
- **How it works**: Routes use `Depends(require_auth)` for authentication
  ```python
  @app.get("/", response_class=HTMLResponse)
  async def dashboard(
      request: Request,
      user_id: str = Depends(require_auth),
      db = Depends(get_db),
  ):
  ```
- **Relevance**: All protected routes must maintain this dependency pattern

**Pattern 3: Template Rendering**
- **Location**: `bimcalc/web/app_enhanced.py:86` (templates initialization)
- **How it works**: Jinja2Templates instance shared across all routes
  ```python
  templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
  return templates.TemplateResponse("dashboard.html", {...})
  ```
- **Relevance**: Templates instance must be importable by all route modules

**Pattern 4: Pydantic Request/Response Models**
- **Location**: `bimcalc/web/app_enhanced.py:826-900` (inline models)
- **How it works**: Models defined inline near their usage
  ```python
  class BulkUpdateRequest(BaseModel):
      match_ids: List[int]
      action: Literal["approve", "reject"]
  ```
- **Relevance**: Move all Pydantic models to `bimcalc/web/models.py`

### Relevant Code Review

**Key existing code snippet - Intelligence Router (already modularized):**
```python
# Location: bimcalc/intelligence/routes.py:1-50
from fastapi import APIRouter, Depends
from bimcalc.web.auth import require_auth

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])

@router.get("/recommendations")
async def get_recommendations(
    user_id: str = Depends(require_auth),
    db = Depends(get_db),
):
    # Implementation
    pass
```

**Main app including router:**
```python
# Location: bimcalc/web/app_enhanced.py:96-99
from bimcalc.intelligence.routes import router as intelligence_router

config = get_config()
if config.enable_rag or config.enable_risk_scoring:
    app.include_router(intelligence_router)
```

**This is our blueprint**: Follow the same pattern for all functional areas.

### Gaps/Issues in Current Implementation

1. **Gap 1: No Route Organization**
   - **Evidence**: All 139 routes in single file (app_enhanced.py:149-5726)
   - **Impact**: Hard to find routes, difficult to test, slow IDE performance, merge conflicts

2. **Gap 2: Mixed Concerns**
   - **Evidence**: Business logic, route handlers, models, utilities all in one file
   - **Impact**: Violates single responsibility principle, hard to reuse logic

3. **Gap 3: Inline Pydantic Models**
   - **Evidence**: 8+ BaseModel classes scattered throughout file (lines 826, 2464, 4901, etc.)
   - **Impact**: Hard to import/reuse models, duplicated definitions

4. **Gap 4: No Clear API Versioning**
   - **Evidence**: Mix of `/api/*` and non-prefixed routes
   - **Impact**: Future API versioning will be difficult

5. **Gap 5: 5 TODOs Indicating Incomplete Features**
   - **Evidence**: Grep found TODOs at lines 305, 220, 1125, 1700, 5596
   - **Impact**: Some features incomplete (SCD2 temporal reporting, PDF handling, alerting)

---

## 4. Constraints & Requirements

### Technical Constraints

- **FastAPI**: Must use FastAPI routers (APIRouter) - established pattern
- **Python 3.11+**: Maintain compatibility
- **Backward Compatibility**: All existing routes must work identically (same paths, same behavior)
- **Dependencies**: No new external dependencies (use existing FastAPI, Pydantic, SQLAlchemy)
- **Templates**: Template paths must remain working (minimal changes to templates/*.html)
- **Authentication**: All protected routes must maintain `require_auth` dependency
- **Database**: No ORM model changes, no migrations
- **Performance**: Route loading should be faster (lazy loading), no regression in response times

### Business Constraints

- **Zero Downtime**: Must be deployable without service interruption
- **No Breaking Changes**: Existing API clients (if any) must continue working
- **User Experience**: UI must be identical post-refactor
- **Testing**: Must maintain or improve test coverage (currently unknown, likely low)

### BIMCalc Invariants (Must Not Violate)

- [x] Classification trust hierarchy respected (not affected by refactor)
- [x] SCD2 one active row invariant maintained (not affected)
- [x] Critical-Veto flags block auto-accept (not affected)
- [x] Canonical keys remain deterministic (not affected)
- [x] Reports are reproducible via as-of queries (not affected)

**Note**: This is a **presentation layer refactor** - no business logic changes, so invariants are safe.

---

## 5. Approach Design

### Chosen Approach

**Name**: Modular Route-Based Architecture with APIRouter

**High-Level Design**:
1. Create `bimcalc/web/routes/` directory for all route modules
2. Extract each functional area into dedicated router module
3. Move shared Pydantic models to `bimcalc/web/models.py`
4. Create `bimcalc/web/dependencies.py` for shared dependencies (templates, etc.)
5. Update `app_enhanced.py` to become thin orchestrator (include routers)
6. Maintain all existing route paths and behavior (100% compatibility)
7. Add comprehensive tests for each router module
8. Migrate incrementally (one router at a time, verify, repeat)

**Detailed Design**:

#### Component 1: Route Modules (`bimcalc/web/routes/*.py`)

**Responsibility**: Each module handles one functional area

**Structure**:
```python
# bimcalc/web/routes/ingestion.py
from fastapi import APIRouter, Depends, UploadFile
from bimcalc.web.auth import require_auth
from bimcalc.web.dependencies import get_templates
from bimcalc.ingestion.schedules import ingest_schedule

router = APIRouter(tags=["ingestion"])

@router.get("/ingest", response_class=HTMLResponse)
async def ingest_page(
    request: Request,
    user_id: str = Depends(require_auth),
    templates = Depends(get_templates),
):
    return templates.TemplateResponse("ingest.html", {"request": request})

@router.post("/ingest/schedules")
async def ingest_schedules_endpoint(
    file: UploadFile,
    user_id: str = Depends(require_auth),
    db = Depends(get_db),
):
    # Implementation (moved from app_enhanced.py)
    pass
```

**Dependencies**:
- `fastapi.APIRouter` - Route grouping
- `bimcalc.web.auth` - Authentication
- `bimcalc.web.dependencies` - Shared dependencies
- Domain modules (ingestion, matching, etc.)

**Error Handling**: HTTPException raised as current implementation

#### Component 2: Shared Models (`bimcalc/web/models.py`)

**Responsibility**: All Pydantic request/response models

**Interface**:
```python
# bimcalc/web/models.py
from pydantic import BaseModel
from typing import List, Literal

class BulkUpdateRequest(BaseModel):
    """Request for bulk match updates."""
    match_ids: List[int]
    action: Literal["approve", "reject"]
    reason: str | None = None

class BulkPriceImportRequest(BaseModel):
    """Request for bulk price import."""
    items: List[dict]
    org_id: int

class BulkPriceImportResponse(BaseModel):
    """Response for bulk price import."""
    imported_count: int
    errors: List[str]

# ... all other models
```

**Dependencies**: `pydantic`

**Error Handling**: Pydantic validation errors (automatic)

#### Component 3: Shared Dependencies (`bimcalc/web/dependencies.py`)

**Responsibility**: Provide shared dependencies to routes

**Interface**:
```python
# bimcalc/web/dependencies.py
from pathlib import Path
from fastapi.templating import Jinja2Templates

_templates = None

def get_templates() -> Jinja2Templates:
    """Get Jinja2Templates instance (singleton)."""
    global _templates
    if _templates is None:
        templates_dir = Path(__file__).parent / "templates"
        _templates = Jinja2Templates(directory=str(templates_dir))
    return _templates
```

**Dependencies**: `fastapi.templating`

**Error Handling**: None (simple getter)

#### Component 4: Main App (`bimcalc/web/app_enhanced.py` - reduced)

**Responsibility**: Application setup, router inclusion, middleware

**Interface**:
```python
# bimcalc/web/app_enhanced.py (after refactor)
from fastapi import FastAPI
from bimcalc.web.routes import (
    auth,
    dashboard,
    ingestion,
    matching,
    review,
    items,
    mappings,
    reports,
    pipeline,
    analytics,
    compliance,
    projects,
    documents,
    classifications,
    crail4,
    scenarios,
    risk,
)
from bimcalc.intelligence.routes import router as intelligence_router

app = FastAPI(
    title="BIMCalc Management Console",
    description="Web interface for managing BIMCalc pricing data",
    version="1.0.0",
)

# Include routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(ingestion.router)
app.include_router(matching.router)
app.include_router(review.router)
app.include_router(items.router)
app.include_router(mappings.router)
app.include_router(reports.router)
app.include_router(pipeline.router)
app.include_router(analytics.router)
app.include_router(compliance.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(classifications.router)
app.include_router(crail4.router)
app.include_router(scenarios.router)
app.include_router(risk.router)

# Conditional routers
config = get_config()
if config.enable_rag or config.enable_risk_scoring:
    app.include_router(intelligence_router)

# Middleware, exception handlers, startup/shutdown events
# (keep existing middleware setup)
```

**Dependencies**: All route modules

**Error Handling**: Global exception handler (existing)

#### Database Changes

**None** - This is a presentation layer refactor only.

#### API Changes

**None** - All routes maintain same paths and behavior. The refactor is internal.

### Alternatives Considered

#### Alternative 1: Blueprint-Based Organization (Flask-style)

**Pros**:
- Familiar to Flask developers
- Clear separation

**Cons**:
- FastAPI doesn't have blueprints (uses APIRouter instead)
- Would be fighting the framework
- Migration harder

**Why Rejected**: FastAPI's APIRouter is the idiomatic approach, already proven in `intelligence/routes.py`

#### Alternative 2: Keep Monolithic, Just Split Into Multiple Functions

**Pros**:
- Minimal changes
- Faster to implement

**Cons**:
- Doesn't solve the fundamental problem (5,726 line file)
- Still hard to navigate and test
- Doesn't improve modularity

**Why Rejected**: Band-aid solution, doesn't address root cause

#### Alternative 3: Microservices (Separate FastAPI Apps)

**Pros**:
- Maximum separation
- Independent deployment
- Scalability

**Cons**:
- Massive over-engineering for current scale
- Adds complexity (service discovery, distributed tracing, etc.)
- Would require database changes (separate DBs per service)
- Not in scope of refactor

**Why Rejected**: Too complex, not justified by current requirements

---

## 6. Risk Assessment

### High Risks

1. **Risk**: Breaking existing route behavior during migration
   - **Probability**: Medium
   - **Impact**: High (user-facing breakage)
   - **Mitigation**:
     - Test each route module immediately after creation
     - Run full integration test suite before merging
     - Deploy to staging first
     - Keep old app_enhanced.py as backup during migration

2. **Risk**: Import circular dependencies between route modules
   - **Probability**: Low-Medium
   - **Impact**: High (app won't start)
   - **Mitigation**:
     - Careful dependency design (models in separate file, no cross-router imports)
     - Use dependency injection instead of direct imports
     - Test imports in isolation

### Medium Risks

1. **Risk**: Template path resolution issues
   - **Probability**: Low
   - **Impact**: Medium (UI rendering broken)
   - **Mitigation**:
     - Templates dependency provides correct path resolution
     - Test all template rendering routes
     - Template paths are relative, should work regardless of module location

2. **Risk**: Performance regression (slower imports)
   - **Probability**: Low
   - **Impact**: Low (startup time slightly slower)
   - **Mitigation**:
     - Measure import time before/after
     - Use lazy imports if needed
     - FastAPI lazy-loads routes anyway

3. **Risk**: Developer confusion during transition
   - **Probability**: Medium
   - **Impact**: Low (temporarily slower development)
   - **Mitigation**:
     - Clear documentation of new structure
     - Update CLAUDE.md with new patterns
     - Add README in `routes/` directory

### What Could Go Wrong?

- **Scenario 1**: Authentication breaks on some routes
  - **Detection**: Integration tests will fail, routes return 401
  - **Recovery**: Fix `require_auth` dependency injection, ensure all routes include it

- **Scenario 2**: Pydantic model import errors
  - **Detection**: Import errors on app startup
  - **Recovery**: Fix import paths in route modules, ensure models.py exports all models

- **Scenario 3**: Middleware not applying to new routers
  - **Detection**: Metrics/logging missing, CORS errors
  - **Recovery**: Ensure middleware applied to main app (before router inclusion), not individual routers

---

## 7. Rollback Plan

### Pre-Deployment Checklist

- [ ] All route modules created and tested individually
- [ ] Integration tests passing (all routes work)
- [ ] No circular import issues
- [ ] Templates render correctly
- [ ] Authentication works on all protected routes
- [ ] Pydantic models importable and validated
- [ ] Code review completed
- [ ] Documentation updated (CLAUDE.md, README)
- [ ] Staging deployment successful
- [ ] Performance benchmarks acceptable

### Rollback Triggers

Roll back if:
- [ ] Critical routes broken (404, 500 errors)
- [ ] Authentication bypass discovered
- [ ] Template rendering fails on multiple pages
- [ ] Import errors prevent app startup
- [ ] Performance degraded >10% (response time)

### Rollback Procedure

1. **Stop**: Halt deployment if issues detected in staging
2. **Revert**:
   ```bash
   # Rollback code
   git revert <refactor-commit-hash>

   # Or restore backup
   git checkout main~1 -- bimcalc/web/app_enhanced.py
   rm -rf bimcalc/web/routes/
   ```
3. **Verify**:
   - Run pytest to ensure old version works
   - Check staging environment
   - Verify all routes return expected responses
4. **Communicate**:
   - Notify team of rollback
   - Document what failed
   - Create issue for fix

**Backup Strategy**: Before starting refactor, create branch `backup/web-refactor-2025-01-01` with current state.

---

## 8. Testing Strategy

### Unit Tests

**File**: `tests/unit/web/test_routes_*.py` (one file per router)

**Test Cases**:

**`test_routes_ingestion.py`:**
1. `test_ingest_page_requires_auth` - Verify auth dependency
2. `test_ingest_schedules_success` - Happy path file upload
3. `test_ingest_schedules_invalid_file` - Error handling
4. `test_ingest_prices_duplicate_handling` - Edge case

**`test_routes_matching.py`:**
1. `test_match_run_happy_path` - Successful matching
2. `test_match_run_no_items` - Edge case (empty schedule)
3. `test_match_run_error_handling` - Orchestrator failure

**`test_routes_review.py`:**
1. `test_fetch_pending_reviews` - Data retrieval
2. `test_approve_review_success` - State change
3. `test_approve_review_already_approved` - Idempotency
4. `test_reject_review_with_reason` - Rejection flow

**Coverage Target**: >90% for all new route modules (easier to test isolated routers)

### Integration Tests

**File**: `tests/integration/test_web_full_workflow.py`

**Test Cases**:
1. `test_end_to_end_matching_workflow` - Login → Ingest → Match → Review → Report
2. `test_all_routes_return_200_or_redirect` - Smoke test all endpoints
3. `test_authentication_flow` - Login, protected routes, logout
4. `test_template_rendering` - All HTML pages render without error
5. `test_api_endpoints_json_response` - All `/api/*` routes return valid JSON

**Coverage Target**: >80%

### Performance Tests

**Benchmark**: Route import time and first request latency

**Baseline**:
- Current app startup: ~2-3 seconds (estimated)
- Current first request: ~100-500ms per route

**Target**:
- App startup: <5 seconds (acceptable given modularization)
- First request: No regression (<10% slower)

**Test Procedure**:
```python
def test_import_performance():
    import time
    start = time.time()
    from bimcalc.web.app_enhanced import app
    elapsed = time.time() - start
    assert elapsed < 5.0  # 5 second max startup

def test_route_performance():
    # Load test each major route
    response = client.get("/dashboard")
    assert response.elapsed.total_seconds() < 0.6  # 10% margin on 500ms
```

### Manual Testing

1. **Test Case 1**: Full User Workflow
   - **Steps**:
     1. Login to web UI
     2. Navigate to Ingest page
     3. Upload schedule CSV
     4. Navigate to Match page
     5. Run matching
     6. Navigate to Review page
     7. Approve/reject matches
     8. Navigate to Reports
     9. Generate report
   - **Expected**: All pages load, all actions work identically to before refactor

2. **Test Case 2**: All Functional Areas
   - **Steps**: Click through every menu item, verify page loads
   - **Expected**: No 404s, no template errors, all pages render

3. **Test Case 3**: API Endpoints
   - **Steps**: Use Postman/curl to test all `/api/*` endpoints
   - **Expected**: Same responses as before refactor

---

## 9. Implementation Plan

### Phase 1: Setup & Preparation
**Duration**: 1-2 hours
- [x] Create ULTRATHINK planning document (this document)
- [ ] Create `bimcalc/web/routes/` directory
- [ ] Create `bimcalc/web/models.py` (empty scaffold)
- [ ] Create `bimcalc/web/dependencies.py`
- [ ] Create backup branch: `backup/web-refactor-2025-01-01`
- [ ] Set up test structure: `tests/unit/web/` and `tests/integration/`

**Files**:
- `planning/ULTRATHINK-web-refactor-2025-01-01.md` (this file)
- `bimcalc/web/routes/__init__.py`
- `bimcalc/web/models.py`
- `bimcalc/web/dependencies.py`
- `tests/unit/web/__init__.py`

**Validation**:
```bash
ls -la bimcalc/web/routes/
ls -la tests/unit/web/
git branch | grep backup/web-refactor
```

---

### Phase 2: Extract Shared Components
**Duration**: 2-3 hours

- [ ] Move all Pydantic models to `bimcalc/web/models.py`
  - [ ] BulkUpdateRequest
  - [ ] BulkPriceImportRequest/Response
  - [ ] RuleUpdate/RuleCreate
  - [ ] ConvertItemsRequest
  - [ ] ReportTemplateCreate
  - [ ] SendEmailRequest
- [ ] Implement `get_templates()` in dependencies.py
- [ ] Add `__all__` exports to models.py
- [ ] Test model imports independently

**Files**:
- `bimcalc/web/models.py` (complete)
- `bimcalc/web/dependencies.py` (complete)

**Validation**:
```bash
python -c "from bimcalc.web.models import BulkUpdateRequest; print('OK')"
python -c "from bimcalc.web.dependencies import get_templates; print('OK')"
pytest tests/unit/web/test_models.py
```

---

### Phase 3: Create Route Modules (Incremental)
**Duration**: 8-12 hours (broken into sub-phases)

**Order of migration** (low-risk to high-risk):

#### 3.1: Auth Routes (Simple, Critical)
- [ ] Create `routes/auth.py`
- [ ] Move `/login` (GET/POST), `/logout`
- [ ] Move `/favicon.ico`
- [ ] Test authentication flow
- [ ] Update app_enhanced.py to include auth router

**Validation**: `pytest tests/unit/web/test_routes_auth.py -v`

#### 3.2: Dashboard Routes (Simple, Visible)
- [ ] Create `routes/dashboard.py`
- [ ] Move `/` (dashboard), `/progress`, `/progress/export`
- [ ] Test dashboard rendering
- [ ] Update app_enhanced.py

**Validation**: Manual check - dashboard loads correctly

#### 3.3: Ingestion Routes (Medium Complexity)
- [ ] Create `routes/ingestion.py`
- [ ] Move `/ingest`, `/ingest/schedules`, `/ingest/prices`, `/ingest/history`
- [ ] Test file upload functionality
- [ ] Update app_enhanced.py

**Validation**: Upload test CSV, verify ingestion works

#### 3.4: Matching Routes
- [ ] Create `routes/matching.py`
- [ ] Move `/match`, `/match/run`
- [ ] Test matching orchestration
- [ ] Update app_enhanced.py

**Validation**: Run matching, verify results

#### 3.5: Review Routes
- [ ] Create `routes/review.py`
- [ ] Move `/review`, `/review/approve`, `/review/reject`
- [ ] Test review workflow
- [ ] Update app_enhanced.py

**Validation**: Approve/reject matches, verify state changes

#### 3.6: Items Routes
- [ ] Create `routes/items.py`
- [ ] Move `/items`, `/items/{item_id}`, `/items/export`, DELETE `/items/{item_id}`
- [ ] Test CRUD operations
- [ ] Update app_enhanced.py

**Validation**: View items, export, delete

#### 3.7: Mappings Routes
- [ ] Create `routes/mappings.py`
- [ ] Move `/mappings`, DELETE `/mappings/{mapping_id}`
- [ ] Test mapping management
- [ ] Update app_enhanced.py

**Validation**: View mappings, delete mapping

#### 3.8: Reports Routes
- [ ] Create `routes/reports.py`
- [ ] Move `/reports`, `/reports/generate`, `/reports/statistics`
- [ ] Test report generation
- [ ] Update app_enhanced.py

**Validation**: Generate report, verify Excel download

#### 3.9: Pipeline Routes
- [ ] Create `routes/pipeline.py`
- [ ] Move `/pipeline`, `/pipeline/run`, `/pipeline/sources`, `/api/pipeline/status`
- [ ] Test pipeline orchestration
- [ ] Update app_enhanced.py

**Validation**: Run pipeline, check status

#### 3.10: Analytics Routes (Complex)
- [ ] Create `routes/analytics.py`
- [ ] Move all `/api/analytics/*` routes (~10 routes)
- [ ] Test analytics queries
- [ ] Update app_enhanced.py

**Validation**: Load analytics page, verify charts

#### 3.11: Compliance Routes
- [ ] Create `routes/compliance.py`
- [ ] Move `/compliance`, `/api/compliance/*` routes
- [ ] Test compliance checks
- [ ] Update app_enhanced.py

**Validation**: Run compliance check, view results

#### 3.12: Projects Routes (High Complexity - Multi-tenant)
- [ ] Create `routes/projects.py`
- [ ] Move all `/api/projects/*` routes (~30+ routes)
- [ ] Test project CRUD, documents, analytics, exports
- [ ] Update app_enhanced.py

**Validation**: Full project workflow test

#### 3.13: Documents Routes
- [ ] Create `routes/documents.py`
- [ ] Move `/documents`, document upload/processing routes
- [ ] Test document processing
- [ ] Update app_enhanced.py

**Validation**: Upload document, process, view results

#### 3.14: Classifications Routes
- [ ] Create `routes/classifications.py`
- [ ] Move `/classifications`, `/api/classifications/*`
- [ ] Test classification mapping
- [ ] Update app_enhanced.py

**Validation**: Manage classification mappings

#### 3.15: Crail4 Routes
- [ ] Create `routes/crail4.py`
- [ ] Move all `/crail4-config/*` routes
- [ ] Test Crail4 integration
- [ ] Update app_enhanced.py

**Validation**: Configure Crail4, test sync

#### 3.16: Scenarios Routes
- [ ] Create `routes/scenarios.py`
- [ ] Move `/scenarios`, `/api/scenarios/*`
- [ ] Test scenario comparison
- [ ] Update app_enhanced.py

**Validation**: Compare scenarios, export

#### 3.17: Risk Routes
- [ ] Create `routes/risk.py`
- [ ] Move `/risk-dashboard`, risk assessment routes
- [ ] Test risk scoring
- [ ] Update app_enhanced.py

**Validation**: View risk dashboard, assess items

#### 3.18: Audit Routes
- [ ] Create `routes/audit.py`
- [ ] Move `/audit`, `/export/audit`
- [ ] Test audit log viewing
- [ ] Update app_enhanced.py

**Validation**: View audit log, export

**Files** (after Phase 3):
- `bimcalc/web/routes/auth.py`
- `bimcalc/web/routes/dashboard.py`
- `bimcalc/web/routes/ingestion.py`
- `bimcalc/web/routes/matching.py`
- `bimcalc/web/routes/review.py`
- `bimcalc/web/routes/items.py`
- `bimcalc/web/routes/mappings.py`
- `bimcalc/web/routes/reports.py`
- `bimcalc/web/routes/pipeline.py`
- `bimcalc/web/routes/analytics.py`
- `bimcalc/web/routes/compliance.py`
- `bimcalc/web/routes/projects.py`
- `bimcalc/web/routes/documents.py`
- `bimcalc/web/routes/classifications.py`
- `bimcalc/web/routes/crail4.py`
- `bimcalc/web/routes/scenarios.py`
- `bimcalc/web/routes/risk.py`
- `bimcalc/web/routes/audit.py`
- `bimcalc/web/app_enhanced.py` (now ~200 lines - just router inclusion)

**Validation** (full suite):
```bash
pytest tests/unit/web/ -v
pytest tests/integration/test_web_full_workflow.py -v
```

---

### Phase 4: Cleanup & Verification
**Duration**: 2-3 hours

- [ ] Remove old code from app_enhanced.py (now just router inclusion)
- [ ] Add docstrings to all route modules
- [ ] Update `bimcalc/web/__init__.py` exports
- [ ] Run full test suite
- [ ] Check code coverage
- [ ] Run linting/formatting

**Validation**:
```bash
# Verify app_enhanced.py is small
wc -l bimcalc/web/app_enhanced.py  # Should be ~200 lines

# Run all checks
black bimcalc/web && ruff check --fix bimcalc/web && mypy bimcalc/web
pytest tests/unit/web tests/integration -v
pytest --cov=bimcalc.web --cov-report=html
```

---

### Phase 5: Documentation
**Duration**: 1-2 hours

- [ ] Update `CLAUDE.md` with new web route patterns
- [ ] Create `bimcalc/web/routes/README.md` explaining structure
- [ ] Update `.agents/rules/sections/03_architecture.md` with web layer details
- [ ] Document route module conventions in `.agents/rules/sections/09_common_patterns.md`
- [ ] Update API docs (if separate from FastAPI auto-docs)

**Files**:
- `CLAUDE.md` (updated)
- `bimcalc/web/routes/README.md` (new)
- `.agents/rules/sections/03_architecture.md` (updated)
- `.agents/rules/sections/09_common_patterns.md` (updated)

**Validation**: Review documentation for completeness

---

### Phase 6: Deployment
**Duration**: 1-2 hours

- [ ] Deploy to staging environment
- [ ] Run smoke tests on staging
- [ ] Run manual testing checklist
- [ ] Monitor logs for errors
- [ ] Performance testing (load test)
- [ ] Get approval for production deployment
- [ ] Deploy to production
- [ ] Monitor production logs
- [ ] Verify all routes working

**Validation**:
```bash
# Staging smoke test
curl https://staging.bimcalc.com/login  # Should return 200
curl https://staging.bimcalc.com/api/projects  # Should return JSON

# Production smoke test (after deploy)
curl https://bimcalc.com/login
```

---

## 10. Validation Checklist

### Before implementation starts:
- [x] All sections of this ULTRATHINK document completed
- [x] Approach aligns with BIMCalc patterns (FastAPI routers, existing intelligence router)
- [x] Database schema validated (N/A - no schema changes)
- [x] Risk mitigation strategies defined
- [x] Testing strategy covers all scenarios
- [x] Rollback plan documented
- [ ] User approval obtained (ask user if approach looks good)

### Before marking implementation complete:
- [ ] All phases completed
- [ ] All tests passing (unit + integration)
- [ ] Code review completed (self-review + user review)
- [ ] Documentation updated (CLAUDE.md, README, architecture docs)
- [ ] Performance benchmarks met (no regression)
- [ ] No BIMCalc invariants violated (N/A for presentation layer)
- [ ] Staging deployment successful
- [ ] Production deployment successful

---

## 11. References

### Architecture Decision Records
- [ADR-001: Cost Matching Overhaul](../docs/ADRs/adr-0001-bimcalc-cost-matching-overhaul.md) - (Empty, but referenced)

### Relevant Code
- [`bimcalc/web/app_enhanced.py:1-5726`](../bimcalc/web/app_enhanced.py) - Current monolithic implementation
- [`bimcalc/intelligence/routes.py:1-200`](../bimcalc/intelligence/routes.py) - Example of modular router (pattern to follow)
- [`bimcalc/web/auth.py:1-100`](../bimcalc/web/auth.py) - Authentication utilities
- [`tests/unit/*`](../tests/unit/) - Existing test patterns

### External Documentation
- [FastAPI APIRouter Documentation](https://fastapi.tiangolo.com/tutorial/bigger-applications/) - Official guide
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/) - Dependency system
- [Jinja2 Templates in FastAPI](https://fastapi.tiangolo.com/advanced/templates/) - Template usage

### Previous Discussions
- ULTRATHINK framework discussion (2025-01-01) - Led to creation of this planning document
- Codebase analysis showing 5,726 lines, 139 routes, 143 functions

---

## 12. Sign-Off

**Planning Completed**: 2025-01-01
**Reviewed By**: Claude Code (AI Agent)
**Approved**: [ ] Yes [ ] No (pending user review)
**Ready to Implement**: [ ] Yes [ ] No (pending user approval)

**Notes**:
This is a high-value refactor that will significantly improve maintainability. The risk is manageable because:
1. We're following established patterns (intelligence router)
2. Migration is incremental (one router at a time)
3. No business logic changes (just reorganization)
4. Comprehensive testing strategy
5. Clear rollback plan

**Recommendation**: Proceed with phased implementation after user approval.

---

## 13. Post-Implementation Review

_To be filled after implementation_

**Implementation Completed**: [Date]
**Actual vs. Planned**:
- **Effort**: [Estimate] vs [Actual]
- **Surprises**: [What didn't go as planned]
- **Lessons Learned**: [What we'd do differently]

**Validation Results**:
- [ ] All tests passing
- [ ] Performance targets met
- [ ] No production issues

**Follow-Up Tasks**:
- [ ] Address remaining TODOs (5 found in codebase)
- [ ] Consider adding OpenAPI tags for better API documentation
- [ ] Evaluate API versioning strategy (mix of `/api/` and non-prefixed routes)
