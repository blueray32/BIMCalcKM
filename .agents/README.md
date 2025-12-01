# BIMCalcKM Agent Rules & Templates

This directory contains global development rules, templates, and guidelines for AI coding agents working on the BIMCalcKM project.

## Structure

```
.agents/
├── rules/
│   └── sections/           # Modular rule sections
│       ├── 01_core_principles.md
│       ├── 02_tech_stack.md
│       ├── 03_architecture.md
│       ├── 04_code_style.md
│       ├── 05_logging.md
│       ├── 06_testing.md
│       ├── 07_api_contracts.md
│       ├── 08_dev_commands.md
│       ├── 09_common_patterns.md
│       └── 10_ai_instructions.md  ⭐ ULTRATHINK guidelines
│
└── templates/
    └── ULTRATHINK.md       # Planning template for high-impact changes
```

## ULTRATHINK Framework

**ULTRATHINK** is a mandatory planning phase for high-impact changes to prevent the issues seen in recent commits:
- Database schema conflicts (duplicate indexes)
- Integration failures (crail4, docker)
- Large refactors needed to fix initial structure

### When to Use ULTRATHINK

Execute ULTRATHINK **before writing code** for:

#### 🔴 CRITICAL (Must Have)
- Database schema changes
- New feature phases (Phase 8, 9, 10, etc.)
- External system integrations

#### 🟡 HIGH VALUE (Recommended)
- Refactoring files >500 lines
- Cross-cutting concerns (auth, compliance, multi-tenancy)
- Performance-critical paths

#### 🟢 MEDIUM VALUE (Consider)
- Complex UI features
- Data pipeline changes

#### ⚪ Skip ULTRATHINK For
- Bug fixes in single files
- Configuration changes
- Documentation updates
- UI styling tweaks

### Quick Start

1. **Check if ULTRATHINK applies**:
   ```bash
   # Ask yourself:
   # - Is this a database change?
   # - Is this a new feature phase?
   # - Is this an external integration?
   # - Am I refactoring >500 lines?
   ```

2. **Create planning document**:
   ```bash
   cp .agents/templates/ULTRATHINK.md planning/ULTRATHINK-{feature}-{date}.md
   ```

3. **Fill in the template**:
   - Impact analysis
   - Current state review
   - Approach design
   - Risk assessment
   - Testing strategy
   - Implementation plan

4. **Proceed with implementation** after planning is complete

## Integration with PRP Workflow

The `/generate-BIMCALC-prp` and `/execute-BIMCALC-prp` commands **already embody ULTRATHINK**:
- Research phase = ULTRATHINK
- Architecture planning = ULTRATHINK
- Implementation blueprint = ULTRATHINK

For **ad-hoc work outside PRPs**, use the ULTRATHINK guidelines in `rules/sections/10_ai_instructions.md`.

## BIMCalc-Specific Patterns

Key patterns documented in `rules/sections/09_common_patterns.md`:

1. **Classification-First Blocking** - Trust hierarchy drives matching
2. **Canonical Key Generation** - Deterministic, normalized keys
3. **SCD Type-2 Mapping** - One active row, temporal history
4. **Risk Flag Engine** - Critical-Veto vs Advisory
5. **Trust Hierarchy** - Omni/Uni → curated → category → heuristic → unknown
6. **Two-Pass Matching** - First pass creates mappings, second uses them
7. **Repository Pattern** - Separate data access from business logic
8. **Configuration Management** - Centralized env-based config

## Evidence from Commit History

ULTRATHINK would have prevented:

| Issue | Commit | Root Cause | ULTRATHINK Would Have |
|-------|--------|------------|----------------------|
| Duplicate index | "Fix duplicate index..." | No schema analysis before migration | Checked existing indexes |
| Docker failures | "docker fix" | No integration testing plan | Designed error handling upfront |
| Large refactor | 5cf6f65 (+5,094/-997) | Initial structure didn't scale | Designed scalable structure from start |
| Crail4 issues | "crail4 fix" | Integration added without retry logic | Planned retry/fallback behavior |

## Daily Workflow

For **regular development**:
```bash
# Standard changes (no ULTRATHINK needed)
git pull
docker-compose up -d
# Make changes
pytest
black . && ruff check --fix && mypy bimcalc
git commit
```

For **high-impact changes** (ULTRATHINK required):
```bash
# 1. Create ULTRATHINK document
cp .agents/templates/ULTRATHINK.md planning/ULTRATHINK-{feature}.md

# 2. Fill in planning document
# (Analyze impact, design approach, assess risks)

# 3. Review with team if needed

# 4. Implement following the plan

# 5. Validate against plan
pytest --cov=bimcalc
```

## Resources

- **AI Instructions**: `.agents/rules/sections/10_ai_instructions.md`
- **Common Patterns**: `.agents/rules/sections/09_common_patterns.md`
- **ULTRATHINK Template**: `.agents/templates/ULTRATHINK.md`
- **Global Rules**: `CLAUDE.md` (references all sections)

## Contributing

When adding new patterns or discovering new complexity thresholds:

1. Document the pattern in the appropriate section
2. Add to ULTRATHINK triggers if it's a new complexity category
3. Reference specific commits that motivate the guideline
4. Update this README if structure changes

---

**Last Updated**: 2025-01-01 (Initial ULTRATHINK implementation)
