# Logging

## Logging Standards

### Configuration

Use structured logging with appropriate levels:

```python
import logging

# Module-level logger
logger = logging.getLogger(__name__)
```

### Log Levels

#### DEBUG
- Detailed diagnostic information
- Variable values during execution
- Entry/exit of functions

```python
logger.debug(f"Processing item: {item_id}, confidence: {confidence}")
```

#### INFO
- General informational messages
- Major workflow steps
- Successful operations

```python
logger.info(f"Matched {matched_count} items in {elapsed:.2f}s")
```

#### WARNING
- Potentially problematic situations
- Fallback behavior triggered
- Deprecated usage

```python
logger.warning(f"Classification unknown for item {item_id}, using fallback")
```

#### ERROR
- Error events that might still allow the application to continue
- Recoverable errors
- Validation failures

```python
logger.error(f"Failed to fetch price data: {error}")
```

#### EXCEPTION
- Errors with full traceback
- Unexpected exceptions
- Use in except blocks

```python
try:
    process_data()
except Exception as e:
    logger.exception("Data processing failed")
    raise
```

### Best Practices

#### 1. Include Context
```python
# Good
logger.info(f"Matching item {item_id} with classification {classification}")

# Bad
logger.info("Matching item")
```

#### 2. Use Structured Data
```python
# For JSON logging
logger.info(
    "Match completed",
    extra={
        "item_id": item_id,
        "confidence": confidence,
        "flags": flags,
    }
)
```

#### 3. Log Performance Metrics
```python
import time

start = time.time()
result = expensive_operation()
logger.info(f"Operation completed in {time.time() - start:.2f}s")
```

#### 4. Don't Log Sensitive Data
```python
# Bad
logger.info(f"Processing user: {email}, password: {password}")

# Good
logger.info(f"Processing user: {email}")
```

### BIMCalc-Specific Logging

#### Classification Events
```python
logger.info(
    f"Classified item {item_id}: "
    f"source={source}, trust_level={trust_level}"
)
```

#### Matching Pipeline
```python
logger.debug(f"Generated {len(candidates)} candidates for item {item_id}")
logger.info(f"Best match: {match_id}, confidence={confidence:.2f}")
```

#### Flag Detection
```python
logger.warning(
    f"Critical-Veto flag raised: {flag_type} for item {item_id}"
)
```

#### SCD2 Operations
```python
logger.debug(f"Closing previous mapping: id={mapping_id}, end_date={end_date}")
logger.info(f"Created new mapping: {mapping_id}, effective_date={effective_date}")
```

---

**Configuration**: Set log level via environment variable `LOG_LEVEL` (default: INFO).
