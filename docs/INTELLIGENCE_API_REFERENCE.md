# BIMCalc Intelligence API Reference

**Version:** 1.0  
**Base URL:** `http://localhost:8003`  
**Authentication:** Session-based (inherited from main app)

---

## 📊 Analytics APIs

### Get Classification Breakdown

Returns item count by classification code.

**Endpoint:**
```http
GET /api/analytics/classification-breakdown
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| org | string | Yes | Organization ID |
| project | string | Yes | Project ID |

**Response:**
```json
{
  "labels": ["2601", "2602", "2801"],
  "values": [45, 32, 18]
}
```

**Caching:** 10 minutes

**Example:**
```bash
curl "http://localhost:8003/api/analytics/classification-breakdown?org=demo-org&project=tritex24-229"
```

---

### Get Compliance Timeline

Returns QA completion percentage over time (weekly).

**Endpoint:**
```http
GET /api/analytics/compliance-timeline
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| org | string | Yes | Organization ID |
| project | string | Yes | Project ID |

**Response:**
```json
{
  "dates": ["2025-W01", "2025-W02", "2025-W03"],
  "percentages": [20.5, 45.2, 68.9]
}
```

**Caching:** 10 minutes

---

### Get Cost Distribution

Returns total cost by classification.

**Endpoint:**
```http
GET /api/analytics/cost-distribution
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| org | string | Yes | Organization ID |
| project | string | Yes | Project ID |

**Response:**
```json
{
  "labels": ["Electrical", "HVAC", "Plumbing"],
  "values": [125000.50, 98000.25, 67500.00]
}
```

**Caching:** 10 minutes

---

### Get Document Coverage Matrix

Returns heatmap data showing document coverage by classification.

**Endpoint:**
```http
GET /api/analytics/document-coverage
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| org | string | Yes | Organization ID |
| project | string | Yes | Project ID |

**Response:**
```json
{
  "matrix": [
    [5, 3, 0],
    [2, 8, 1]
  ],
  "row_labels": ["Quality Docs", "Safety Docs"],
  "col_labels": ["2601", "2602", "2801"]
}
```

**Caching:** 10 minutes

---

## 🎯 Risk Scoring APIs

### Get Item Risk Score

Calculate risk score for a single item.

**Endpoint:**
```http
GET /api/items/{item_id}/risk
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| item_id | UUID | Yes | Item identifier |

**Response:**
```json
{
  "item_id": "123e4567-e89b-12d3-a456-426614174000",
  "score": 75.0,
  "level": "High",
  "factors": {
    "doc_coverage": {
      "score": 40,
      "status": "No documents"
    },
    "classification": {
      "score": 15,
      "status": "Complex (2601)"
    },
    "age": {
      "score": 20,
      "status": "95 days old (very old)"
    },
    "match_confidence": {
      "score": 0,
      "status": "No match data"
    }
  },
  "recommendations": [
    "🚨 URGENT: Immediate attention required",
    "🔗 Link relevant quality and safety documents",
    "⏰ Priority review - item significantly overdue"
  ]
}
```

**Caching:** 1 hour

**Example:**
```bash
curl "http://localhost:8003/api/items/123e4567-e89b-12d3-a456-426614174000/risk"
```

---

### Get High-Risk Items

Get all items above a risk threshold.

**Endpoint:**
```http
GET /api/items/high-risk
```

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| org | string | Yes | - | Organization ID |
| project | string | Yes | - | Project ID |
| threshold | integer | No | 61 | Minimum risk score (0-100) |
| limit | integer | No | 50 | Max items to return (1-200) |

**Response:**
```json
{
  "threshold": 61,
  "count": 12,
  "items": [
    {
      "item_id": "123e4567-e89b-12d3-a456-426614174000",
      "family": "Fire Alarm Panel",
      "type_name": "Type A",
      "classification_code": "2601",
      "risk_score": 85.0,
      "risk_level": "High",
      "recommendations": [
        "🔗 Link quality documents",
        "⏰ Priority review - 95 days old"
      ]
    }
  ]
}
```

**Example:**
```bash
curl "http://localhost:8003/api/items/high-risk?org=demo-org&project=tritex24-229&threshold=70&limit=10"
```

---

## 🧪 Checklist APIs

### Generate Checklist

Generate QA checklist for an item using AI.

**Endpoint:**
```http
POST /api/items/{item_id}/generate-checklist
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| item_id | UUID | Yes | Item identifier |

**Request Body:** None

**Response:**
```json
{
  "checklist_id": "abc-def-123",
  "item_id": "123e4567-e89b-12d3-a456-426614174000",
  "items": [
    {
      "id": 1,
      "requirement": "Visual inspection: No physical damage",
      "category": "Inspection",
      "priority": "High",
      "estimated_time_minutes": 5,
      "completed": false,
      "notes": ""
    }
  ],
  "source_docs": [
    {
      "id": "doc-123",
      "title": "Fire Safety Standard BS 5839",
      "type": "quality"
    }
  ],
  "completion_percent": 0.0
}
```

**Processing Time:** ~10 seconds

**Error Responses:**
- `400`: No relevant documents found
- `500`: Failed to generate checklist

**Example:**
```bash
curl -X POST "http://localhost:8003/api/items/123e4567-e89b-12d3-a456-426614174000/generate-checklist"
```

---

### Get Checklist

Retrieve existing checklist for an item.

**Endpoint:**
```http
GET /api/items/{item_id}/checklist
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| item_id | UUID | Yes | Item identifier |

**Response:**
```json
{
  "checklist_id": "abc-def-123",
  "item_id": "123e4567-e89b-12d3-a456-426614174000",
  "items": [...],
  "source_docs": [...],
  "completion_percent": 60.0,
  "generated_at": "2025-11-24T12:00:00Z",
  "completed_at": null
}
```

**Error Responses:**
- `404`: No checklist found for this item

---

### Update Checklist

Mark checklist items as complete/incomplete.

**Endpoint:**
```http
PATCH /api/items/{item_id}/checklist
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| item_id | UUID | Yes | Item identifier |

**Request Body:**
```json
{
  "item_id": 1,
  "completed": true,
  "notes": "Verified on site"
}
```

**Response:**
```json
{
  "checklist_id": "abc-def-123",
  "items": [...],
  "completion_percent": 80.0,
  "completed_at": null
}
```

**Auto-completion:** When completion_percent reaches 100%, `completed_at` is set automatically.

**Example:**
```bash
curl -X PATCH "http://localhost:8003/api/items/123e4567-e89b-12d3-a456-426614174000/checklist" \
  -H "Content-Type: application/json" \
  -d '{"item_id": 1, "completed": true}'
```

---

## 🤖 Recommendations API

### Get Document Recommendations

Get AI-recommended documents for an item.

**Endpoint:**
```http
GET /api/items/{item_id}/recommendations
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| item_id | UUID | Yes | Item identifier |

**Response:** HTML partial (for HTMX)
```html
<div>
  <div style="...">
    <div>Fire Safety Standard BS 5839</div>
    <div style="color: #38a169;">Relevance: 95%</div>
  </div>
  ...
</div>
```

**Caching:** 24 hours

**Note:** Returns top 5 documents with relevance scores. Designed for HTMX lazy-loading.

---

## 🔄 Common Patterns

### Pagination
Not currently implemented. Use `limit` parameter where available.

### Error Handling

All endpoints return consistent error format:
```json
{
  "detail": "Error message here"
}
```

**HTTP Status Codes:**
- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Not found
- `500`: Server error

### Caching

**Cache Headers:**
All cached responses include:
```
X-Cache-Status: HIT|MISS
Cache-Control: max-age={seconds}
```

**Cache Invalidation:**
- Manual: Restart Redis or use FLUSHDB
- Auto: TTL expires

---

## 📝 Usage Examples

### Python

```python
import requests

# Analytics
response = requests.get(
    "http://localhost:8003/api/analytics/classification-breakdown",
    params={"org": "demo-org", "project": "tritex24-229"}
)
data = response.json()

# Risk Scoring
response = requests.get(
    f"http://localhost:8003/api/items/{item_id}/risk"
)
risk = response.json()

# Generate Checklist
response = requests.post(
    f"http://localhost:8003/api/items/{item_id}/generate-checklist"
)
checklist = response.json()

# Update Checklist
response = requests.patch(
    f"http://localhost:8003/api/items/{item_id}/checklist",
    json={"item_id": 1, "completed": True}
)
```

### JavaScript

```javascript
// Analytics
const response = await fetch(
  `/api/analytics/classification-breakdown?org=${org}&project=${project}`
);
const data = await response.json();

// Generate Checklist
const response = await fetch(
  `/api/items/${itemId}/generate-checklist`,
  { method: 'POST' }
);
const checklist = await response.json();

// Update Checklist
await fetch(`/api/items/${itemId}/checklist`, {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ item_id: 1, completed: true })
});
```

### cURL

```bash
# Get high-risk items
curl "http://localhost:8003/api/items/high-risk?org=demo-org&project=tritex24-229&threshold=61"

# Generate checklist
curl -X POST "http://localhost:8003/api/items/{item-id}/generate-checklist"

# Update checklist item
curl -X PATCH "http://localhost:8003/api/items/{item-id}/checklist" \
  -H "Content-Type: application/json" \
  -d '{"item_id": 1, "completed": true}'
```

---

## 🎯 Rate Limits

**OpenAI API:**
- Embeddings: ~3000 requests/min
- Checklists: ~20 requests/min (GPT-4o-mini tier dependent)

**Application:**
- No explicit rate limiting
- Consider implementing for production

---

## 🔐 Authentication

Currently uses session-based auth from main application.

**Required:**
- Valid session cookie
- Proper org/project access

**Future:**
- API key authentication
- OAuth2 support

---

## 📊 Response Times (Typical)

| Endpoint | Cached | Uncached |
|----------|--------|----------|
| Analytics | <100ms | <2s |
| Risk Score | <50ms | <200ms |
| Recommendations | <50ms | <500ms |
| Generate Checklist | N/A | ~10s |
| Get Checklist | <50ms | <50ms |
| Update Checklist | <100ms | <100ms |

---

## 🔗 Related Resources

- **User Guide:** `/docs/INTELLIGENCE_USER_GUIDE.md`
- **Admin Guide:** `/docs/INTELLIGENCE_ADMIN_GUIDE.md`
- **Quick Start:** `/docs/INTELLIGENCE_QUICKSTART.md`

---

**Version:** 1.0  
**Last Updated:** November 2025
