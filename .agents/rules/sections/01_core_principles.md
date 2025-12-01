# Core Principles

## BIMCalcKM Development Philosophy

### 1. Classification-First Approach
- Trust hierarchy drives all matching decisions
- Escape hatch for unknown classifications
- Deterministic, reproducible results

### 2. Temporal Data Integrity
- SCD Type-2 for all mapping history
- As-of queries for point-in-time reporting
- One active row invariant

### 3. Risk-Aware Automation
- Critical-Veto flags prevent auto-accept
- Advisory flags inform but don't block
- Human review for high-risk matches

### 4. European Market Focus
- EUR as default currency
- Explicit VAT handling
- Localized formatting and compliance

### 5. Simplicity Over Cleverness
- Clear, maintainable code
- Minimal abstractions
- Documented decisions (ADRs)

### 6. Data-Driven Validation
- Comprehensive test coverage
- Real-world data samples
- Performance benchmarks

---

**Note**: Expand this section with specific principles as they emerge from the codebase.
