# INITIAL

## FEATURE
Deliver the **BIMCalc MVP**: a production-ready cost-matching engine and companion agent, built around the researched architecture:
- **Classification‑first blocking** (trust hierarchy, mandatory candidate filter)
- **Canonical key + Mapping Memory** (project‑agnostic; O(1) auto‑match on repeats)
- **Business Risk Flags** with **UI enforcement** (Critical‑Veto vs Advisory)
- **Immutable SCD Type‑2 mapping history** (bit‑for‑bit reproducible reports)
- A lightweight **RAG/Graph QA agent** to query BIMCalc docs, price books, and mappings

The engine ingests **Revit schedules (CSV/XLSX)** and **vendor price lists**, matches items to prices, computes €/m or €/ea, and outputs **auditable reports** (EU locale: EUR + explicit VAT).

---

## EXAMPLES (copy these exactly; keep structure)
- `examples/rag_pipeline/` — **RAG ingestion + SQL/Graph utils** (must copy as is)
- `examples/main_agent_reference/` — Reference CLI & provider patterns
- `examples/basic_chat_agent/`, `examples/tool_enabled_agent/`, `examples/structured_output_agent/`, `examples/testing_examples/`
- BIMCalc demo data: `examples/revit_schedule.csv`, `examples/pricebook.csv`

**Required copy command (preserve structure):**
```bash
cp -R examples/rag_pipeline ./bimcalc_agent/rag_pipeline
```

Review `bimcalc_agent/rag_pipeline/sql/schema.sql` and **use the provided SQL functions** for vector & hybrid searches.

---

## DOCUMENTATION
- **ADR**: `docs/ADRs/adr-0001-bimcalc-cost-matching-overhaul.md` (classification‑first, mapping memory, flags, SCD2)
- **Roadmap**: BIMCalc Architectural Upgrades — Implementation Roadmap (4‑Week MVP) (canvas doc; mirror into `docs/ROADMAP.md` during implementation)
- Pydantic AI: https://ai.pydantic.dev/  
  Agents: https://ai.pydantic.dev/agents/  
  Tools: https://ai.pydantic.dev/tools/  
  Testing: https://ai.pydantic.dev/testing/  
  Models: https://ai.pydantic.dev/models/
- Use **Archon MCP** to pull Pydantic AI + Graphiti examples/refs as needed.

---

## TOOLS (BIMCalc Engine)
**Matching & Pricing**
- `classify_item(row) -> int|None`: Assign internal `classification_code` via trust hierarchy (Omni/Uni → curated list → Revit category/system → heuristics → Unknown).
- `canonical_key(row) -> str`: Normalized composite key `{class,family_slug,type_slug,width,height,dn,angle,material,unit}`.
- `mapping_lookup(canonical_key) -> Optional[PriceItemRef]`: O(1) read from Mapping Memory (SCD2 active row).
- `mapping_write(canonical_key, price_item_id, reason) -> MappingVersion`: Insert SCD2 row (close previous with `end_ts`).
- `generate_candidates(classification_code) -> Iterable[PriceItem]`: Class‑blocked price candidates (indexed by class).
- `fuzzy_rank(item, candidates, k=10) -> List[MatchCandidate]`: RapidFuzz within class, with numeric/attribute pre‑filters.
- `compute_flags(item_attrs, price_attrs) -> List[Flag]`: Critical‑Veto (Unit/Size/Angle/Material/Class) and Advisory (Stale Price, Currency/VAT).
- `auto_route(confidence_band, flags) -> {"auto": bool, "reason": str}`: Auto‑accept only if **High** and **no flags**.
- `generate_report(project_id, run_ts) -> CSV/XLSX/PDF`: Deterministic report joining SCD2 mappings **valid at run_ts**.

**RAG/Graph Agent**
- `vector_search(query, limit=10) -> List[Chunk]` (pgvector; from schema.sql)
- `hybrid_search(query, limit=10, text_weight=0.3) -> List[Chunk]` (pgvector + TSVector)
- `graph_search(query) -> List[Fact]` (Neo4j/Graphiti)
- `perform_comprehensive_search(query, use_vector=True, use_graph=True, limit=10) -> Dict`
- `get_document(document_id) -> Dict`, `list_documents(...) -> List[Doc]`
- `get_entity_relationships(entity_name, depth=2) -> List[Rel]`, `get_entity_timeline(entity, start, end) -> List[Fact]`

---

## DEPENDENCIES
- **Core**: Python 3.11+, `pandas`, `rapidfuzz`, `pydantic`, `typer`, `rich`, `PyYAML`
- **DBs**: `asyncpg` (PostgreSQL + **pgvector**), `neo4j` (or Graphiti client)
- **Embeddings**: OpenAI‑compatible embeddings client
- **Env (.env.example)**:
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/bimcalc
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
EMBEDDINGS_MODEL=text-embedding-3-large
LLM_MODEL=gpt-4.1
ARCHON_SERVER=http://localhost:7007
EU_LOCALE=1
```

---

## SYSTEM PROMPT(S)
You are the **BIMCalc assistant**. You can (1) answer questions using RAG/Graph search and (2) orchestrate the BIMCalc matching pipeline.

**Rules**
- For **costing questions**, first run the **matching pipeline**: map via Mapping Memory; else class‑blocked fuzzy; apply flags; do **not** auto‑accept if any Critical‑Veto flags.
- For **documentation/architecture questions**, use **hybrid_search**; use **graph_search** only when relationships or timelines are requested.
- **Cite** document titles and facts. Prefer the newest valid data. EU formatting (EUR, VAT explicit).

---

## CLI REQUIREMENTS
Provide a Typer CLI with subcommands (pattern from `examples/main_agent_reference`):
- `bimcalc ingest schedules <path>`: Load Revit schedules (CSV/XLSX).
- `bimcalc ingest pricebook <path>`: Load vendor price list (requires `classification_code`).  
- `bimcalc match run --project <id>`: Execute classification‑first matching; write SCD2 mappings.
- `bimcalc review ui`: Launch review UI (web or TUI) with flags/chips/filters; **disable Accept** on Critical‑Veto.
- `bimcalc report build --project <id> [--as-of <ts>]`: Generate deterministic report using SCD2 as‑of join.
- `agent chat` / `agent search "<query>"` / `agent doc <id>`: RAG/Graph agent.
- Global: `--model`, `--verbose`, `--dry-run`, `--limit`.

---

## ACCEPTANCE CRITERIA (from research)
- **Blocking performance**: ≥ **20×** candidate reduction; **p95 < 0.5 s/item** on N≈500 × M≈5,000 benchmark.
- **Learning**: Two‑pass demo: Project A approve → Project B instant auto‑match (same canonical key). Auto‑match ≥ **30–50%** on repeats.
- **Safety**: **0** accepted items with Critical‑Veto flags.
- **Auditability**: Reports **reproducible bit‑for‑bit** by `run_ts` using SCD2 mapping rows.
- **UX**: Review table supports filters: Unit Conflict / Size / Angle / Material / Stale Price / Currency/VAT.

---

## OTHER CONSIDERATIONS
- **Classification trust hierarchy** order is mandatory; log overrides and unknowns, feed back into curated lists.
- **SCD2 invariants**: at most one active row per `(org_id, canonical_key)`; transactional writes; as‑of reads for reports.
- **EU locale** by default (€, VAT explicit). Currency conversions & VAT treatment must be explicit when non‑EUR occurs.
- **Testing**: Unit tests for classifier, canonicalizer, flags; integration tests for two‑pass demo & as‑of reporting; performance test harness.
- **Security/Tenancy**: Scope mappings by `org_id`; optional global defaults; auditing (`created_by`, `reason`).

---

## TASKS (Jira‑ready outline)
1. **Schema & Migrations**: add `classification_code`, `canonical_key`; create `item_mapping` (SCD2) + indices
2. **Classifier** (YAML‑driven trust hierarchy) + backfill pricebook classification
3. **Canonicalization/Parsing** (normalize; extract size/angle/material/unit)
4. **Candidate Generator** (class‑blocked) + **Fuzzy Matcher**
5. **Flags Engine** + **UI gating**
6. **Mapping Memory API** (SCD2 writes; as‑of reads) + Two‑pass demo
7. **Report Builder** (as‑of join; EU formatting)
8. **Agent** (copy `rag_pipeline`; wire vector/hybrid/graph tools; minimal CLI)
9. **Benchmarks & Telemetry** (p50/p95 latency; candidate counts; flag stats)
10. **Docs**: README, ROADMAP, ADR references; `.env.example`; Makefile targets

