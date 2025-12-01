# ULTRATHINK Planning Document

**Feature**: [Feature Name]
**Date**: [YYYY-MM-DD]
**Author**: [AI Agent / Human Name]
**Trigger**: [Database Change / New Phase / Integration / Refactor / etc.]

---

## 1. Overview

### What are we building/changing?
[1-2 paragraph description of the feature or change]

### Why is ULTRATHINK needed?
- [ ] Database schema change
- [ ] New feature phase
- [ ] External integration
- [ ] Large refactoring (>500 lines)
- [ ] Cross-cutting concern
- [ ] Performance-critical path
- [ ] Complex UI feature
- [ ] Data pipeline change

---

## 2. Impact Analysis

### Affected Modules
List all modules that will be modified or impacted:

- `bimcalc/[module]/` - [Why/How affected]
- `tests/[module]/` - [New tests needed]
- `alembic/versions/` - [Migrations needed]
- [Other modules...]

### Affected Files (Detailed)
| File Path | Change Type | Lines Affected | Risk Level |
|-----------|-------------|----------------|------------|
| `bimcalc/...` | Modify | ~50-100 | Medium |
| `tests/...` | Add | ~200 | Low |
| `alembic/...` | Add | ~30 | High |

### Dependency Graph
```
[Module A] ─depends on─> [Module B]
     │
     └─> [Module C] ─uses─> [External API]
```

---

## 3. Current State Analysis

### Existing Patterns
**Pattern 1**: [Name]
- **Location**: [file:line]
- **How it works**: [Brief explanation]
- **Relevance**: [How this change relates]

**Pattern 2**: [Name]
- **Location**: [file:line]
- **How it works**: [Brief explanation]
- **Relevance**: [How this change relates]

### Relevant Code Review
```python
# Key existing code snippet
# Location: file.py:123-145
def existing_function():
    # Snippet showing current implementation
    pass
```

### Gaps/Issues in Current Implementation
1. **Gap 1**: [Description]
   - **Evidence**: [Commit/file/behavior]
   - **Impact**: [What breaks or is limited]

2. **Gap 2**: [Description]
   - **Evidence**: [Commit/file/behavior]
   - **Impact**: [What breaks or is limited]

---

## 4. Constraints & Requirements

### Technical Constraints
- **Database**: [PostgreSQL version, existing schema constraints]
- **Performance**: [Latency/throughput requirements]
- **Dependencies**: [Library versions, API compatibility]
- **Backward Compatibility**: [What must not break]

### Business Constraints
- **EU Compliance**: [GDPR, VAT, etc.]
- **Data Integrity**: [SCD2 invariants, no data loss]
- **User Experience**: [No breaking changes to UI]

### BIMCalc Invariants (Must Not Violate)
- [ ] Classification trust hierarchy respected
- [ ] SCD2 one active row invariant maintained
- [ ] Critical-Veto flags block auto-accept
- [ ] Canonical keys remain deterministic
- [ ] Reports are reproducible via as-of queries

---

## 5. Approach Design

### Chosen Approach
**Name**: [e.g., "Add SCD2 Mapping to Classification Module"]

**High-Level Design**:
1. [Step 1]
2. [Step 2]
3. [Step 3]
4. [Step 4]

**Detailed Design**:

#### Component 1: [Name]
- **Responsibility**: [What it does]
- **Interface**:
  ```python
  def new_function(param: Type) -> ReturnType:
      """Docstring."""
      pass
  ```
- **Dependencies**: [What it uses]
- **Error Handling**: [How failures are handled]

#### Component 2: [Name]
- **Responsibility**: [What it does]
- **Interface**: [Code signature]
- **Dependencies**: [What it uses]
- **Error Handling**: [How failures are handled]

#### Database Changes
```sql
-- Migration: alembic/versions/XXXX_description.py
CREATE TABLE new_table (
    id SERIAL PRIMARY KEY,
    canonical_key VARCHAR(255) NOT NULL,
    effective_date DATE NOT NULL,
    end_date DATE,
    -- Enforce SCD2 invariant
    CONSTRAINT one_active_row EXCLUDE USING gist (
        canonical_key WITH =,
        daterange(effective_date, end_date, '[]') WITH &&
    ) WHERE (end_date IS NULL)
);

CREATE INDEX idx_canonical_key ON new_table(canonical_key);
CREATE INDEX idx_effective_date ON new_table(effective_date);
```

#### API Changes
```python
# New endpoints
POST /api/v1/new-resource
GET /api/v1/new-resource/{id}

# Request/Response contracts
class NewResourceRequest(BaseModel):
    field: str
    ...

class NewResourceResponse(BaseModel):
    id: int
    field: str
    ...
```

### Alternatives Considered

#### Alternative 1: [Name]
**Pros**:
- [Pro 1]
- [Pro 2]

**Cons**:
- [Con 1]
- [Con 2]

**Why Rejected**: [Rationale]

#### Alternative 2: [Name]
**Pros**:
- [Pro 1]

**Cons**:
- [Con 1]

**Why Rejected**: [Rationale]

---

## 6. Risk Assessment

### High Risks
1. **Risk**: [Description]
   - **Probability**: High/Medium/Low
   - **Impact**: High/Medium/Low
   - **Mitigation**: [How we'll prevent/handle]

2. **Risk**: [Description]
   - **Probability**: High/Medium/Low
   - **Impact**: High/Medium/Low
   - **Mitigation**: [How we'll prevent/handle]

### Medium Risks
1. **Risk**: [Description]
   - **Mitigation**: [How we'll handle]

### What Could Go Wrong?
- **Scenario 1**: [Description]
  - **Detection**: [How we'll know]
  - **Recovery**: [How we'll fix]

- **Scenario 2**: [Description]
  - **Detection**: [How we'll know]
  - **Recovery**: [How we'll fix]

---

## 7. Rollback Plan

### Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Migration tested on staging database
- [ ] Performance benchmarks meet targets
- [ ] Code review completed
- [ ] Documentation updated

### Rollback Triggers
Roll back if:
- [ ] Critical functionality broken
- [ ] Performance degraded >20%
- [ ] Data integrity issues detected
- [ ] Migration fails on production

### Rollback Procedure
1. **Stop**: [What to stop]
2. **Revert**:
   ```bash
   # Database
   alembic downgrade -1

   # Code
   git revert <commit-hash>
   ```
3. **Verify**: [What to check]
4. **Communicate**: [Who to notify]

---

## 8. Testing Strategy

### Unit Tests
**File**: `tests/unit/test_[feature].py`

**Test Cases**:
1. `test_[happy_path]` - [Description]
2. `test_[edge_case_1]` - [Description]
3. `test_[error_handling]` - [Description]
4. `test_[scd2_invariant]` - Verify one active row (if applicable)
5. `test_[flag_behavior]` - Verify Critical-Veto blocks accept (if applicable)

**Coverage Target**: >95% for new code

### Integration Tests
**File**: `tests/integration/test_[feature]_integration.py`

**Test Cases**:
1. `test_[end_to_end_workflow]` - [Description]
2. `test_[database_integration]` - [Description]
3. `test_[external_api_integration]` - [Description] (if applicable)

**Coverage Target**: >80%

### Performance Tests
**Benchmark**: [What to measure]

**Baseline**: [Current performance]

**Target**: [Acceptable performance]

**Test Procedure**:
```python
def test_performance():
    start = time.time()
    # Run operation N times
    elapsed = time.time() - start
    assert elapsed < TARGET_SECONDS
```

### Manual Testing
1. **Test Case 1**: [Description]
   - **Steps**: [1, 2, 3...]
   - **Expected**: [Result]

2. **Test Case 2**: [Description]
   - **Steps**: [1, 2, 3...]
   - **Expected**: [Result]

---

## 9. Implementation Plan

### Phase 1: Database Schema
**Duration**: [Estimate]
- [ ] Create migration
- [ ] Test migration up/down
- [ ] Add indexes
- [ ] Verify constraints

**Files**:
- `alembic/versions/XXXX_[description].py`

**Validation**:
```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

### Phase 2: Domain Models
**Duration**: [Estimate]
- [ ] Update ORM models
- [ ] Add validators
- [ ] Update repositories

**Files**:
- `bimcalc/db/models.py`
- `bimcalc/repositories/[name].py`

**Validation**:
```bash
pytest tests/unit/test_models.py
```

### Phase 3: Business Logic
**Duration**: [Estimate]
- [ ] Implement core functions
- [ ] Add error handling
- [ ] Add logging

**Files**:
- `bimcalc/[module]/[feature].py`
- `bimcalc/services/[name].py`

**Validation**:
```bash
pytest tests/unit/test_[feature].py
```

### Phase 4: API Endpoints
**Duration**: [Estimate]
- [ ] Define request/response models
- [ ] Implement endpoints
- [ ] Add validation

**Files**:
- `bimcalc/web/app_enhanced.py` (or new route file)

**Validation**:
```bash
pytest tests/integration/test_[feature]_api.py
```

### Phase 5: Integration & Testing
**Duration**: [Estimate]
- [ ] Integration tests
- [ ] Performance tests
- [ ] Manual testing

**Validation**:
```bash
pytest tests/integration
pytest --cov=bimcalc --cov-fail-under=80
```

### Phase 6: Documentation
**Duration**: [Estimate]
- [ ] Update README
- [ ] Add docstrings
- [ ] Update API docs

**Files**:
- `README.md`
- `docs/API.md`

---

## 10. Validation Checklist

Before implementation starts:
- [ ] All sections of this ULTRATHINK document completed
- [ ] Approach aligns with BIMCalc patterns
- [ ] Database schema validated (if applicable)
- [ ] Risk mitigation strategies defined
- [ ] Testing strategy covers all scenarios
- [ ] Rollback plan documented

Before marking implementation complete:
- [ ] All phases completed
- [ ] All tests passing
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Performance benchmarks met
- [ ] No BIMCalc invariants violated

---

## 11. References

### Architecture Decision Records
- [ADR-001: Cost Matching Overhaul](docs/ADRs/adr-0001-bimcalc-cost-matching-overhaul.md)
- [ADR-XXX: Relevant ADR]

### Relevant Code
- [`bimcalc/[module]/[file].py:123-456`](../bimcalc/[module]/[file].py) - [Description]
- [`tests/unit/test_[file].py:78-90`](../tests/unit/test_[file].py) - [Description]

### External Documentation
- [Library/API Docs](https://example.com/docs)
- [Related GitHub Issue](https://github.com/org/repo/issues/123)

### Previous Discussions
- [Slack/Email thread summary]
- [Design meeting notes]

---

## 12. Sign-Off

**Planning Completed**: [Date]
**Reviewed By**: [Name/AI Agent]
**Approved**: [ ] Yes [ ] No
**Ready to Implement**: [ ] Yes [ ] No

**Notes**:
[Any final notes or concerns]

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
- [ ] [Task 1]
- [ ] [Task 2]
