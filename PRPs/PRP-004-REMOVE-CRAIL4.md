# PRP-004: Remove Crail4 and Rename to Price Scout

## 1. Context & Objectives
**Goal:** Remove the legacy "Crail4" branding and code, consolidating everything under "Price Scout".
**Problem:** The codebase contains mixed naming (`crail4`, `price_scout`), and unused legacy code (`Crail4Client`).
**Success Criteria:**
- [ ] `Crail4Client` deleted.
- [ ] Routes renamed from `/crail4-config` to `/price-scout`.
- [ ] Files renamed (`crail4.py` -> `price_scout.py`, etc.).
- [ ] Application starts without errors.

## 2. Technical Approach
**Renaming Strategy:**
- `bimcalc/integration/crail4_client.py` -> **DELETE**
- `bimcalc/web/routes/crail4.py` -> `bimcalc/web/routes/price_scout.py`
- `bimcalc/web/templates/crail4_config.html` -> `bimcalc/web/templates/price_scout.html`
- `bimcalc/integration/crail4_sync.py` -> `bimcalc/integration/price_scout_sync.py`

**Code Updates:**
- Update `bimcalc/web/app_enhanced.py` to include the new router.
- Update `bimcalc/web/templates/base.html` navigation links.
- Update internal imports and route handlers.

## 3. Implementation Plan
### Phase 1: File Operations
- [ ] Delete legacy client.
- [ ] Rename route, template, and sync files.

### Phase 2: Code Refactoring
- [ ] Update imports in `app_enhanced.py`.
- [ ] Update route paths in `price_scout.py` (e.g., `@router.get("/price-scout")`).
- [ ] Update template references in `price_scout.html` (HTMX targets).
- [ ] Update navigation in `base.html`.

## 4. Verification Strategy
- [ ] Manual Check: Navigate to `/price-scout` and verify "Quick Scout" still works.
