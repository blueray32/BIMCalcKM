# AI Coding Assistant Instructions

## ULTRATHINK: Strategic Planning Checkpoints

ULTRATHINK is a mandatory planning phase for high-impact changes. Execute ULTRATHINK **before writing any code** when working on items in the CRITICAL or HIGH VALUE categories below.

### What is ULTRATHINK?

ULTRATHINK is a structured thinking process where the AI agent must:

1. **Analyze Impact** - Map all affected modules, files, and dependencies
2. **Review Patterns** - Check existing codebase patterns and ADRs
3. **Design Approach** - Create detailed implementation plan with alternatives
4. **Validate Against Constraints** - Check database schema, API contracts, performance
5. **Document Decision** - Capture rationale for chosen approach

**Output**: Create a planning document in `planning/` before implementation.

---

## ULTRATHINK Trigger Matrix

### 🔴 CRITICAL (Must Execute ULTRATHINK)

#### 1. Database Schema Changes
**Trigger When:**
- Adding new tables or modifying existing schemas
- Changing column types, constraints, or indexes
- Implementing SCD Type-2 temporal tracking
- Migration affects 3+ tables

**Why:** Schema changes cascade through models → repositories → services → UI. Recent evidence: duplicate index fix, SCD2 mapping refactors.

**ULTRATHINK Must Address:**
- Migration strategy (up/down paths)
- Impact on existing queries and indexes
- ORM model changes needed
- API contract impacts
- Data migration for existing records
- Performance implications (query plans, index strategy)

#### 2. New Feature Phases
**Trigger When:**
- Implementing a new "Phase" (like Phase 8, 9, 10)
- Feature spans 3+ existing modules
- Adding cross-cutting concerns (compliance, multi-region, intelligence)

**Why:** Incremental phase additions without upfront design caused integration issues. Evidence: Phase 9/10 additions required extensive fixes.

**ULTRATHINK Must Address:**
- Module boundaries and responsibilities
- Cross-module data flow
- Database schema extensions needed
- API endpoint design
- UI integration points
- Impact on existing features

#### 3. External System Integrations
**Trigger When:**
- Adding new external API (Crail4, OpenAI, AWS SES, etc.)
- Modifying integration contracts
- Adding authentication/authorization to integrations

**Why:** Integration issues caused multiple fix commits. Evidence: "crail4 fix", "docker fix".

**ULTRATHINK Must Address:**
- API contract definition (request/response)
- Error handling and retry strategy
- Rate limiting and timeouts
- Authentication and credentials management
- Testing strategy (mocking, fixtures)
- Fallback behavior on failure
- Data transformation boundaries

---

### 🟡 HIGH VALUE (Execute ULTRATHINK)

#### 4. Large File Refactoring
**Trigger When:**
- Refactoring files >500 lines
- Breaking apart monolithic modules
- Extracting shared utilities

**Why:** app_enhanced.py is 5,726 lines. Large refactors without planning cause breakage.

**ULTRATHINK Must Address:**
- New module structure and boundaries
- Import dependency graph
- Shared state management
- Testing strategy for refactored code
- Migration path (can it be incremental?)

#### 5. Cross-Cutting Concerns
**Trigger When:**
- Adding authentication/authorization
- Implementing audit logging
- Adding compliance checks
- Multi-tenancy or org-scoping changes

**Why:** These affect all layers. Evidence: org_id scoping issues required fixes.

**ULTRATHINK Must Address:**
- Where concern is enforced (middleware, decorator, base class?)
- Impact on all existing endpoints/functions
- Database model changes needed
- Performance overhead
- Testing approach

#### 6. Performance-Critical Paths
**Trigger When:**
- Optimizing matching pipeline
- Improving candidate generation
- Speeding up report queries
- Adding caching layers

**Why:** Performance changes can introduce subtle bugs or make things worse.

**ULTRATHINK Must Address:**
- Current performance baseline (metrics)
- Bottleneck identification (profiling)
- Optimization approach with trade-offs
- Testing strategy (load tests, benchmarks)
- Rollback plan if optimization fails

---

### 🟢 MEDIUM VALUE (Consider ULTRATHINK)

#### 7. Complex UI Features
**Trigger When:**
- Adding multi-step workflows
- Complex state management
- Real-time updates or websockets
- Large data tables with pagination/filtering

**ULTRATHINK Must Address:**
- State management approach
- API endpoint design
- Error handling and loading states
- Performance (re-renders, data loading)

#### 8. Data Pipeline Changes
**Trigger When:**
- Modifying ingestion logic
- Changing validation rules
- Adding transformation steps
- Updating classification logic

**ULTRATHINK Must Address:**
- Data flow through pipeline
- Validation and error handling
- Idempotency and retry logic
- Testing with real data samples

---

## ⚪ Skip ULTRATHINK For

These changes are low-risk and don't require formal planning:

- **Bug fixes** in single files with clear scope
- **Configuration changes** (environment variables, settings)
- **Documentation updates** (README, comments, docstrings)
- **UI tweaks** within existing components (styling, labels)
- **Minor utility functions** that don't change architecture
- **Test additions** for existing code
- **Logging improvements** that don't change logic

---

## ULTRATHINK Execution Process

When ULTRATHINK is triggered:

### Step 1: Create Planning Document

```bash
# Create planning file
mkdir -p planning/
touch planning/ULTRATHINK-{feature-name}-{date}.md
```

### Step 2: Complete ULTRATHINK Template

Use the template at `.agents/templates/ULTRATHINK.md` (see below).

### Step 3: Review Existing Patterns

**Required Reading:**
- `docs/ADRs/` - Architecture decision records
- Similar code in `bimcalc/` modules
- Database schema in `alembic/versions/`
- Tests in `tests/` showing expected behavior

### Step 4: Document Decisions

The planning document must include:
- **Approach**: Chosen solution with rationale
- **Alternatives Considered**: Other options and why they were rejected
- **Impact Analysis**: All affected files and modules
- **Risks**: What could go wrong?
- **Rollback Plan**: How to undo if needed
- **Testing Strategy**: How to validate the change

### Step 5: Get Approval (if needed)

For CRITICAL changes, consider asking the user:
- "I've created a plan at `planning/ULTRATHINK-{name}.md`. Should I proceed with this approach?"

---

## Integration with PRP Workflow

The PRP commands already have ULTRATHINK built in:

### In `/generate-BIMCALC-prp`:
- Research phase **is** ULTRATHINK
- Codebase analysis step **is** ULTRATHINK
- Architecture planning **is** ULTRATHINK

### In `/execute-BIMCALC-prp`:
- Phase 1 (PRP Loading) includes ULTRATHINK directive
- Phase 2 (Parallel Development) uses planning from ULTRATHINK
- Phase 3 (Implementation) executes the ULTRATHINK plan

**Key Point:** PRPs already embody ULTRATHINK. For ad-hoc work outside PRPs, use this document's guidelines.

---

## Evidence from BIMCalcKM History

These issues would have been prevented by ULTRATHINK:

### Database Schema
- **Issue**: "Fix duplicate index creation in migration"
- **Root Cause**: Migration created without analyzing existing indexes
- **ULTRATHINK Would Have**: Checked existing schema before adding new index

### Integration
- **Issue**: "crail4 fix", "docker fix" commits
- **Root Cause**: Integration added without comprehensive error handling plan
- **ULTRATHINK Would Have**: Designed retry logic and fallback behavior upfront

### Refactoring
- **Issue**: 126 files changed (+5,094/-997) in reorganization refactor
- **Root Cause**: Initial structure didn't scale, required major rework
- **ULTRATHINK Would Have**: Designed scalable module structure from start

### Phase Development
- **Issue**: Phase 8/9/10 additions caused integration issues
- **Root Cause**: Features added incrementally without system-wide design
- **ULTRATHINK Would Have**: Mapped cross-module impacts before implementation

---

## Quick Reference Card

```markdown
┌─────────────────────────────────────────────────────────────┐
│ ULTRATHINK DECISION TREE                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Is this a database schema change?          → YES → 🔴 ULTRATHINK
│ Is this a new feature phase?              → YES → 🔴 ULTRATHINK
│ Is this an external integration?          → YES → 🔴 ULTRATHINK
│                                                             │
│ Is this refactoring >500 lines?           → YES → 🟡 ULTRATHINK
│ Is this a cross-cutting concern?          → YES → 🟡 ULTRATHINK
│ Is this performance-critical?             → YES → 🟡 ULTRATHINK
│                                                             │
│ Is this a complex UI feature?             → YES → 🟢 Consider
│ Is this a data pipeline change?           → YES → 🟢 Consider
│                                                             │
│ Is this a bug fix/config/docs/styling?    → YES → ⚪ Skip
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## BIMCalc-Specific Patterns to Follow

When executing ULTRATHINK, always consider these established patterns:

### 1. Classification-First Blocking
- Trust hierarchy: Omni/Uni → curated → category/system → heuristics → Unknown
- Escape hatch for "Unknown" classification
- Classification drives blocking strategy

### 2. Canonical Key Generation
- Normalized attribute parsing (size/angle/material/unit)
- Unicode normalization (× vs x)
- Deterministic key generation
- Used for matching and deduplication

### 3. Mapping Memory with SCD2
- **One active row per canonical key** (invariant)
- `effective_date` and `end_date` for temporal tracking
- As-of joins for historical reporting
- Deterministic reruns using as-of dates

### 4. Critical-Veto vs Advisory Flags
- **Critical-Veto**: Blocks auto-accept, disables Accept button in UI
- **Advisory**: Shows warning, allows accept
- Flags are deterministic and logged
- UI enforcement is mandatory

### 5. EU Locale Defaults
- EUR currency by default
- Explicit VAT handling
- EU-specific formatting for reports

---

## AI Agent Behavior Guidelines

### When to Ask vs. Proceed

**Ask the User:**
- Multiple valid approaches with significant trade-offs
- Destructive operations (data deletion, schema drops)
- Changes to external integrations (might affect live systems)
- Performance changes that could degrade experience

**Proceed Autonomously:**
- Clear best practice exists
- Following established codebase patterns
- Non-destructive additions
- Internal refactoring with good test coverage

### Communication Style

- **Be concise**: Users prefer brevity over verbose explanations
- **Show, don't tell**: Provide file paths with line numbers (e.g., `bimcalc/mapping/dictionary.py:47`)
- **Surface issues early**: If ULTRATHINK reveals problems, say so immediately
- **Provide options**: When multiple approaches exist, present 2-3 with trade-offs

---

## Continuous Improvement

This document should evolve as the codebase grows. When adding new patterns or encountering new complexity thresholds:

1. **Document the pattern** in this file
2. **Add to ULTRATHINK triggers** if it's a new complexity category
3. **Update the quick reference** to keep it current
4. **Reference specific commits** that motivate the guideline

**Last Updated**: 2025-01-01 (Initial version based on codebase analysis)
