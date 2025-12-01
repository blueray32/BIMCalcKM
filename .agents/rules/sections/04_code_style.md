# Code Style

## Python Style Guidelines

### Formatting Tools
- **Black** for code formatting (enforced)
- **Ruff** for linting (enforced)
- **Mypy** for type checking (enforced)

### General Rules

#### Imports
```python
# Standard library
import os
from datetime import datetime

# Third-party
import pandas as pd
from pydantic import BaseModel

# Local
from bimcalc.config import get_config
from bimcalc.db.models import ItemMapping
```

#### Type Hints
Always use type hints for function signatures:

```python
def classify_item(
    description: str,
    category: str | None = None
) -> Classification:
    """Classify an item using trust hierarchy."""
    ...
```

#### Docstrings
Use Google-style docstrings:

```python
def canonical_key(item: dict[str, Any]) -> str:
    """Generate canonical key for an item.

    Args:
        item: Item dictionary with description, category, etc.

    Returns:
        Normalized canonical key string.

    Raises:
        ValueError: If required fields are missing.
    """
    ...
```

#### Naming Conventions
- **Functions/methods**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`
- **Modules**: `lowercase` or `snake_case`

#### Line Length
- **88 characters** (Black default)
- Break long lines logically

#### File Organization
1. Module docstring
2. Imports
3. Constants
4. Classes
5. Functions
6. `if __name__ == "__main__":` block (if applicable)

### Pydantic Models

```python
from pydantic import BaseModel, Field

class ItemMatch(BaseModel):
    """Match between schedule item and pricebook item."""

    schedule_item_id: int
    pricebook_item_id: int
    confidence: float = Field(ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)
```

### Error Handling

```python
# Specific exceptions
try:
    result = risky_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
except Exception as e:
    logger.exception("Unexpected error")
    raise RuntimeError("Operation failed") from e
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed diagnostic info")
logger.info("General informational messages")
logger.warning("Warning messages")
logger.error("Error messages")
logger.exception("Error with traceback")
```

---

**Enforcement**: Run `ruff check --fix && black . && mypy bimcalc` before committing.
