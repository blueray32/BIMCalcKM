# Smart Price Scout - Compliance & Stability (Phase 1)

**Status:** ✅ Complete
**Version:** 1.0.0
**Date:** 2025-12-04

---

## Overview

Smart Price Scout Phase 1 implements legal and ethical compliance for web scraping, ensuring BIMCalc operates responsibly when extracting price data from supplier websites.

### Key Features

- ✅ **robots.txt Compliance** - Respects supplier site policies
- ✅ **Rate Limiting** - Prevents server overload
- ✅ **Retry Logic** - Resilient to transient failures
- ✅ **Price Validation** - Catches invalid/suspicious prices
- ✅ **Configurable** - All settings via environment variables

---

## Legal & Ethical Standards

### What We Do

1. **Check robots.txt** before accessing any URL
2. **Enforce rate limits** (minimum 2 seconds between requests)
3. **Respect crawl-delay** directives from suppliers
4. **Use realistic user-agent** identifying BIMCalc
5. **Handle errors gracefully** (fail-open when appropriate)
6. **Validate data quality** before importing

### Compliance Matrix

| Requirement | Implementation | Default Behavior |
|-------------|---------------|------------------|
| **robots.txt** | Pre-flight check | Block disallowed URLs |
| **Rate Limiting** | Per-domain throttling | 2s delay (configurable) |
| **User-Agent** | Custom identification | `BIMCalc PriceScout/1.0` |
| **Crawl-Delay** | Auto-detected | Overrides default if higher |
| **Server Load** | Single request/page | Minimal impact |
| **Error Handling** | Fail-open strategy | Allow if robots.txt unavailable |

---

## Configuration

All settings configurable via environment variables:

### Compliance Settings

```bash
# Enable/disable robots.txt checking (default: true)
PRICE_SCOUT_RESPECT_ROBOTS=true

# Custom user agent (default: BIMCalc PriceScout/1.0)
PRICE_SCOUT_USER_AGENT="BIMCalc PriceScout/1.0 (Contact: support@bimcalc.com)"
```

### Rate Limiting

```bash
# Default delay between requests in seconds (default: 2.0)
PRICE_SCOUT_RATE_LIMIT=2.0

# Max parallel sources to scrape (default: 5)
PRICE_SCOUT_MAX_SOURCES=5
```

### Retry Logic

```bash
# Number of retry attempts (default: 3)
PRICE_SCOUT_RETRY_ATTEMPTS=3

# Browser timeout in milliseconds (default: 60000)
PRICE_SCOUT_TIMEOUT_MS=60000
```

### Price Validation

```bash
# Minimum acceptable price (default: 0.01)
PRICE_SCOUT_MIN_PRICE=0.01

# Maximum acceptable price (default: 100000.00)
PRICE_SCOUT_MAX_PRICE=100000.00
```

### Browser Settings

```bash
# Remote browser CDP URL (optional)
PLAYWRIGHT_CDP_URL=ws://browser:3000
```

---

## Usage

### Basic Extraction

```python
from bimcalc.intelligence.price_scout import SmartPriceScout

async with SmartPriceScout() as scout:
    # Automatically checks compliance, applies rate limits, validates
    result = await scout.extract("https://supplier.com/products/widget")

    print(f"Page type: {result['page_type']}")
    print(f"Products found: {len(result['products'])}")

    for product in result["products"]:
        print(f"{product['vendor_code']}: €{product['unit_price']}")
```

### Error Handling

```python
from bimcalc.intelligence.price_scout import SmartPriceScout

async with SmartPriceScout() as scout:
    try:
        result = await scout.extract(url)
    except ValueError as e:
        # Compliance errors (robots.txt disallows, invalid URL)
        print(f"Compliance check failed: {e}")
    except Exception as e:
        # Other errors (network, LLM, timeout)
        print(f"Extraction failed after retries: {e}")
```

### Custom Rate Limits

```python
from bimcalc.intelligence.rate_limiter import DomainRateLimiter

# Create rate limiter with custom delays per domain
rate_limiter = DomainRateLimiter(default_delay=2.0)

# Set slower rate for specific supplier
rate_limiter.set_domain_delay("slow-supplier.com", 5.0)

# Use in your code
await rate_limiter.acquire("https://slow-supplier.com/page")
```

### Manual Compliance Check

```python
from bimcalc.intelligence.scraping_compliance import ComplianceChecker

checker = ComplianceChecker()

# Check if URL is allowed
is_allowed, reason = checker.check_url("https://example.com/products")

if not is_allowed:
    print(f"Cannot scrape: {reason}")
else:
    # Get recommended delay
    delay = checker.get_recommended_delay("https://example.com/products")
    print(f"Recommended delay: {delay}s")
```

---

## Architecture

### Component Overview

```
SmartPriceScout
├── ComplianceChecker (scraping_compliance.py)
│   ├── robots.txt validation
│   ├── URL scheme checking
│   └── Crawl-delay detection
│
├── DomainRateLimiter (rate_limiter.py)
│   ├── Per-domain throttling
│   ├── Custom delay configuration
│   └── Async-safe locking
│
├── Retry Logic (tenacity)
│   ├── Exponential backoff
│   ├── 3 attempts by default
│   └── Configurable
│
└── Price Validation
    ├── Min/max threshold checking
    ├── Negative price detection
    └── Format validation
```

### Data Flow

```
1. extract(url) called
   ↓
2. ComplianceChecker.check_url(url)
   ├─ robots.txt check
   ├─ URL scheme validation
   └─ PASS or RAISE ValueError
   ↓
3. RateLimiter.acquire(url)
   ├─ Check last request time
   ├─ Apply domain-specific delay
   └─ Wait if needed
   ↓
4. Fetch page (with retry)
   ├─ Playwright browser automation
   ├─ Retry on failure (3x)
   └─ Exponential backoff: 2s, 4s, 8s
   ↓
5. Analyze with LLM
   ├─ GPT-4 extraction
   └─ Structured JSON output
   ↓
6. Validate prices
   ├─ Check min/max thresholds
   ├─ Detect negative prices
   ├─ Invalidate bad data
   └─ Log warnings
   ↓
7. Return result
```

---

## Testing

### Run Unit Tests

```bash
# All unit tests
pytest tests/unit/test_scraping_compliance.py -v
pytest tests/unit/test_rate_limiter.py -v
pytest tests/unit/test_price_scout_validation.py -v

# With coverage
pytest tests/unit/test_scraping_compliance.py --cov=bimcalc.intelligence.scraping_compliance
```

### Run Integration Tests

```bash
# Integration tests (includes mocking)
pytest tests/integration/test_price_scout_compliance.py -v

# Specific test
pytest tests/integration/test_price_scout_compliance.py::TestComplianceIntegration::test_compliant_url_extraction_succeeds -v
```

### Test Coverage

Target coverage: **>80%** for new modules

```bash
pytest tests/unit/test_*compliance*.py tests/unit/test_rate_limiter.py tests/unit/test_price_scout_validation.py --cov=bimcalc.intelligence --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html
```

---

## Troubleshooting

### Common Issues

#### Issue: "Disallowed by robots.txt"

**Cause:** Supplier's robots.txt blocks the URL

**Solutions:**
1. Check robots.txt manually: `curl https://supplier.com/robots.txt`
2. Verify you're accessing allowed paths
3. Contact supplier for permission
4. Use alternative data source (manual CSV import)

**Workaround (testing only):**
```bash
PRICE_SCOUT_RESPECT_ROBOTS=false
```

#### Issue: "Rate limit delays too long"

**Cause:** Supplier specifies high crawl-delay in robots.txt

**Solutions:**
1. Accept the delay (ethical approach)
2. Reduce scraping frequency
3. Use bulk import instead of web scraping

**Check crawl-delay:**
```python
from bimcalc.intelligence.scraping_compliance import get_crawl_delay

delay = get_crawl_delay("https://supplier.com/products")
print(f"Required delay: {delay}s")
```

#### Issue: "Extraction fails with timeout"

**Cause:** Page loads slowly or browser automation issues

**Solutions:**
1. Increase timeout:
   ```bash
   PRICE_SCOUT_TIMEOUT_MS=120000  # 2 minutes
   ```
2. Check browser CDP connection:
   ```bash
   docker logs browser  # If using remote browser
   ```
3. Verify network connectivity

#### Issue: "All prices invalidated"

**Cause:** Price format doesn't match expectations or threshold too strict

**Solutions:**
1. Check logs for specific validation errors
2. Adjust thresholds:
   ```bash
   PRICE_SCOUT_MIN_PRICE=0.001
   PRICE_SCOUT_MAX_PRICE=1000000.00
   ```
3. Verify supplier's price format (currency symbol, decimals)

---

## Best Practices

### 1. Start with Manual Imports

For new suppliers, prefer manual CSV imports initially:
- Faster than scraping
- No compliance concerns
- Validates supplier data format

Use Price Scout for:
- Regular price updates
- Monitoring price changes
- Large catalogs (1000+ items)

### 2. Monitor Logs

Enable detailed logging:
```python
import logging
logging.getLogger("bimcalc.intelligence").setLevel(logging.DEBUG)
```

Look for:
- `"Robots.txt disallows"` - Compliance issues
- `"Rate limiting"` - Delay enforcement
- `"Suspicious price"` - Validation warnings
- `"Retry attempt"` - Network issues

### 3. Respect Supplier Policies

- **Always** check robots.txt first
- **Never** disable compliance in production
- **Contact** suppliers for permission if unsure
- **Document** any agreements in audit trail

### 4. Test Before Production

Test with small batches first:
```bash
# Test single URL
python -m bimcalc.cli price-scout test --url "https://supplier.com/product"

# Test compliance
python -m bimcalc.cli price-scout check-compliance --url "https://supplier.com/"
```

### 5. Fallback Strategy

Always have a fallback:
1. Try Price Scout (automated)
2. Fall back to manual CSV import
3. Use cached/historical data if fresh data unavailable

---

## Compliance Checklist

Before deploying to production:

- [ ] robots.txt checking enabled (`PRICE_SCOUT_RESPECT_ROBOTS=true`)
- [ ] Rate limiting configured (≥2 seconds)
- [ ] User-agent properly identifies BIMCalc
- [ ] Retry attempts set reasonably (≤3)
- [ ] Price validation thresholds reviewed
- [ ] Logging configured for audit trail
- [ ] Supplier permission documented (if required)
- [ ] Error handling tested
- [ ] Fallback to manual import available
- [ ] Team trained on compliance features

---

## Future Enhancements (Phase 2+)

Planned improvements:

- **Multi-Source Orchestration** - Compare prices across 3-5 suppliers
- **Redis Caching** - Cache extraction results (24hr TTL)
- **Price Alerts** - Notify on price changes >10%
- **Competitive Intelligence** - Best deal recommendations
- **Proxy Rotation** - Residential proxies for scale
- **API Integration** - Use 1build/ENR APIs where available

See: [ULTRATHINK-SmartPriceScout-Review-2025-12-04.md](../planning/ULTRATHINK-SmartPriceScout-Review-2025-12-04.md)

---

## References

### Legal/Ethical Guidelines

- [Is Web Scraping Legal in 2025?](https://www.browserless.io/blog/is-web-scraping-legal)
- [Ethical Price Scraping Best Practices](https://www.promptcloud.com/blog/ensuring-ethical-price-scraping-best-practices-and-guidelines/)
- [robots.txt Specification](https://www.robotstxt.org/)

### Code References

- **Compliance:** `bimcalc/intelligence/scraping_compliance.py`
- **Rate Limiter:** `bimcalc/intelligence/rate_limiter.py`
- **Price Scout:** `bimcalc/intelligence/price_scout.py`
- **Config:** `bimcalc/config.py:PriceScoutConfig`
- **Tests:** `tests/unit/test_scraping_compliance.py`

---

## Support

For issues or questions:

1. Check logs for error details
2. Review troubleshooting section above
3. Consult ULTRATHINK document for architecture
4. File issue with logs and reproduction steps

**Contact:** support@bimcalc.com
