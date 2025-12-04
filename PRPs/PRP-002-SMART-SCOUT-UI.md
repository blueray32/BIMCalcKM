# PRP-002: Smart Price Scout UI Enhancements

## 1. Context & Objectives
**Goal:** Transform the "Smart Price Scout" page from a static configuration screen into an interactive tool for ad-hoc price discovery.
**Problem:** The current page still contains legacy "Crail4" fields (Base URL) and only allows background syncs. Users cannot easily test the agent on a specific URL without triggering a full job.
**Success Criteria:**
- [ ] Legacy "Base URL" field removed.
- [ ] New "Quick Scout" section added.
- [ ] Users can paste a URL and see extracted price data immediately.
- [ ] UI looks modern and "AI-powered".

## 2. Technical Approach
**Architecture:**
- Use **HTMX** to submit the "Quick Scout" form without reloading.
- Update `bimcalc/web/routes/crail4.py` to handle the quick scout request using `SmartPriceScout`.
- Render the result as a partial HTML template.

**Key Components:**
- `bimcalc/web/templates/crail4_config.html`: Remove legacy fields, add Quick Scout UI.
- `bimcalc/web/routes/crail4.py`: Add `POST /crail4-config/scout` endpoint.

## 3. Implementation Plan
### Phase 1: Cleanup
- [ ] Remove `CRAIL4_BASE_URL` from template and routes.
- [ ] Rename route tag from `crail4` to `price-scout` (optional, but good for consistency).

### Phase 2: Interactive Features
- [ ] Add "Quick Scout" card to `crail4_config.html`.
- [ ] Implement `POST /crail4-config/scout` in `routes/crail4.py`.
- [ ] Create extraction result template (or inline HTML).

## 4. Verification Strategy
- [ ] Manual Check: Enter a TLC Direct URL into "Quick Scout" and verify JSON/Table output.
