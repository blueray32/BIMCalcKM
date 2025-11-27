# Project Intelligence Admin Guide

This guide covers setup and administration of BIMCalc's Project Intelligence features.

## Prerequisites

- PostgreSQL with `pgvector` extension
- OpenAI API key (for RAG/AI linking features)
- Docker Compose environment

## Initial Setup

### 1. Environment Variables

Add to your `.env`:
```bash
OPENAI_API_KEY=sk-...  # Required for RAG and AI linking
```

### 2. Database Migration

Apply the latest migrations:
```bash
docker compose exec app alembic upgrade head
```

This creates:
- `documents` table with vector embedding support
- `document_links` table for item-document relationships
- `project_classification_mappings` table for custom codes

## Data Ingestion

### Schedule Data

Ingest project schedules first:
```bash
docker compose exec app python scripts/ingest_tritex_schedules.py
```

### Documents

Ingest project documents (PDF, DOCX, TXT):
```bash
docker compose exec app python scripts/ingest_documents.py "data/your-project/Documents"
```

**Features:**
- Extracts text content
- Generates embeddings (requires OpenAI API key)
- Auto-tags based on folder structure
- Links to items via filename matching

### AI Document Linking

Enhance linking with AI-powered ID extraction:
```bash
# Test mode (first 10 docs)
docker compose exec app python scripts/ai_link_documents.py --test

# Full run
docker compose exec app python scripts/ai_link_documents.py
```

## Configuration

### Classification Mappings

**Option 1: UI** (Recommended)
1. Navigate to `/classifications`
2. Add mappings via form

**Option 2: Seed Script**
```python
from bimcalc.db.models import ProjectClassificationMappingModel

mapping = ProjectClassificationMappingModel(
    org_id="your-org",
    project_id="your-project",
    local_code="61",
    standard_code="2601",
    description="Custom mapping"
)
```

### Document Auto-Tagging

Tags are generated from folder paths:
```
data/Project/Contracts/       → #Contract
data/Project/Manuals/Elec/    → #Manual, #Electrical
data/Project/Quality/         → #Quality
```

Customize in `scripts/ingest_documents.py`:
```python
def generate_tags(file_path: str) -> list[str]:
    # Your custom logic
```

## Maintenance

### Monitoring Document Count

```bash
docker compose exec app python scripts/count_documents.py
```

### Re-indexing Documents

If you update document content or need to regenerate embeddings:
1. Delete documents: `DELETE FROM documents WHERE project_id = 'your-project'`
2. Re-run ingestion script

### Performance Tuning

**Database Indexes:**
Already created by migrations. For large datasets, consider:
```sql
CREATE INDEX CONCURRENTLY idx_documents_vector 
ON documents USING ivfflat (embedding vector_cosine_ops);
```

**Query Caching:**
See `PERFORMANCE_OPTIMIZATION.md` for caching strategies.

## Troubleshooting

### "Relation does not exist" Error
Run migrations: `docker compose exec app alembic upgrade head`

### Documents Not Linking
- Check item `type_name` matches document filename patterns
- Run AI linking script for content-based matching
- Review `document_links` table for existing links

### Embeddings Not Generated
- Verify `OPENAI_API_KEY` is set
- Check OpenAI API quota/limits
- Review logs for API errors

### Compliance Metrics Incorrect
- Verify document ingestion completed
- Check `document_links` table for relationships
- Ensure QA documents have appropriate tags

## Security Notes

- **API Keys**: Never commit `.env` to version control
- **Access Control**: Implement org/project-level permissions
- **Data Privacy**: Consider on-premises embedding models for sensitive data

## Next Steps

- **Performance**: Implement caching (see Performance Guide)
- **Advanced Features**: Custom classification rules, automated QA workflows
- **Integration**: Connect to external document management systems
