# API Contracts

## API Design Principles

### RESTful Endpoints

Follow standard REST conventions:

```
GET    /api/items          # List items
GET    /api/items/{id}     # Get single item
POST   /api/items          # Create item
PUT    /api/items/{id}     # Update item
DELETE /api/items/{id}     # Delete item
```

### Request/Response Format

#### Standard Success Response
```json
{
  "data": {
    "id": 123,
    "name": "Cable 2.5mm²"
  },
  "meta": {
    "timestamp": "2025-01-01T12:00:00Z"
  }
}
```

#### Standard Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid item description",
    "details": {
      "field": "description",
      "reason": "Cannot be empty"
    }
  }
}
```

#### List Response with Pagination
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1234,
    "total_pages": 25
  }
}
```

### BIMCalc-Specific Endpoints

#### Matching API
```python
# POST /api/matching/run
{
  "schedule_ids": [1, 2, 3],
  "options": {
    "min_confidence": 0.7,
    "auto_accept_threshold": 0.95,
    "enable_fuzzy": true
  }
}

# Response
{
  "data": {
    "matches": [
      {
        "schedule_item_id": 1,
        "pricebook_item_id": 456,
        "confidence": 0.92,
        "flags": ["price_variance"],
        "can_auto_accept": false
      }
    ],
    "stats": {
      "total_items": 3,
      "matched": 2,
      "unmatched": 1,
      "auto_accepted": 0
    }
  }
}
```

#### Classification API
```python
# POST /api/classification/classify
{
  "description": "Cable 2.5mm² Red",
  "category": "Cables",
  "hints": {
    "omniclass": "12-34-56"
  }
}

# Response
{
  "data": {
    "classification": "12-34-56",
    "source": "omniclass",
    "trust_level": "high",
    "confidence": 0.95
  }
}
```

#### Mapping API (SCD2)
```python
# POST /api/mapping/create
{
  "canonical_key": "cable-2.5mm-red",
  "pricebook_item_id": 789,
  "effective_date": "2025-01-01"
}

# GET /api/mapping/{canonical_key}/history
{
  "data": [
    {
      "id": 1,
      "pricebook_item_id": 789,
      "effective_date": "2025-01-01",
      "end_date": null,
      "is_active": true
    },
    {
      "id": 2,
      "pricebook_item_id": 456,
      "effective_date": "2024-01-01",
      "end_date": "2024-12-31",
      "is_active": false
    }
  ]
}
```

### Validation

Use Pydantic for request/response validation:

```python
from pydantic import BaseModel, Field

class MatchRequest(BaseModel):
    """Request to run matching."""

    schedule_ids: list[int] = Field(min_length=1)
    options: MatchOptions = Field(default_factory=MatchOptions)

class MatchOptions(BaseModel):
    """Matching options."""

    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    auto_accept_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    enable_fuzzy: bool = True
```

### Error Codes

```python
# Standard error codes
VALIDATION_ERROR = "VALIDATION_ERROR"
NOT_FOUND = "NOT_FOUND"
UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
INTERNAL_ERROR = "INTERNAL_ERROR"

# BIMCalc-specific
CLASSIFICATION_FAILED = "CLASSIFICATION_FAILED"
MATCHING_FAILED = "MATCHING_FAILED"
CRITICAL_FLAG_RAISED = "CRITICAL_FLAG_RAISED"
SCD2_CONFLICT = "SCD2_CONFLICT"
```

### HTTP Status Codes

- **200 OK**: Successful GET, PUT
- **201 Created**: Successful POST
- **204 No Content**: Successful DELETE
- **400 Bad Request**: Validation error
- **401 Unauthorized**: Missing/invalid auth
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource doesn't exist
- **409 Conflict**: SCD2 conflict, duplicate
- **500 Internal Server Error**: Server error

---

**Versioning**: Use `/api/v1/` prefix for API versioning.
