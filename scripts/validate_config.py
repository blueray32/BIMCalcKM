#!/usr/bin/env python
"""
Validate BIMCalc pipeline configuration before running.
Usage: python scripts/validate_config.py
"""

import os
import sys
from pathlib import Path

import yaml


def validate_config():
    """Validate pipeline_sources.yaml configuration."""

    print("=" * 50)
    print("BIMCalc Pipeline Configuration Validator")
    print("=" * 50)
    print()

    config_path = Path("config/pipeline_sources.yaml")

    # Check config file exists
    if not config_path.exists():
        print(f"❌ ERROR: Configuration file not found: {config_path}")
        print("   Copy config/pipeline_sources_examples.yaml to get started")
        return False

    print(f"✅ Configuration file found: {config_path}")

    # Load and parse YAML
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"❌ ERROR: Invalid YAML syntax: {e}")
        return False

    print("✅ Configuration YAML is valid")

    # Check sources structure
    if "sources" not in config:
        print("❌ ERROR: No 'sources' key in configuration")
        return False

    sources = config["sources"]
    if not isinstance(sources, list):
        print("❌ ERROR: 'sources' must be a list")
        return False

    if len(sources) == 0:
        print("⚠️  WARNING: No sources configured")
        return True

    print(f"✅ Found {len(sources)} source(s) configured")
    print()

    # Validate each source
    errors = []
    warnings = []
    enabled_count = 0

    for idx, source in enumerate(sources):
        source_num = idx + 1
        print(f"Source {source_num}: {source.get('name', 'UNNAMED')}")
        print("-" * 40)

        # Required fields
        required_fields = ["name", "type", "enabled", "config"]
        for field in required_fields:
            if field not in source:
                errors.append(f"Source {source_num}: Missing required field '{field}'")
                print(f"  ❌ Missing required field: {field}")

        if "name" in source:
            name = source["name"]
            print(f"  Name: {name}")

            # Check for duplicate names
            names = [s.get("name") for s in sources]
            if names.count(name) > 1:
                errors.append(f"Source {source_num}: Duplicate source name '{name}'")
                print(f"  ❌ Duplicate source name: {name}")

        if "type" in source:
            source_type = source["type"]
            print(f"  Type: {source_type}")

            valid_types = ["csv", "api", "scraper", "ftp", "email_attachment"]
            if source_type not in valid_types:
                warnings.append(
                    f"Source {source_num}: Unrecognized type '{source_type}' "
                    f"(valid: {', '.join(valid_types)})"
                )
                print(f"  ⚠️  Unrecognized source type: {source_type}")

        if "enabled" in source:
            enabled = source["enabled"]
            print(f"  Enabled: {enabled}")
            if enabled:
                enabled_count += 1

        if "config" in source:
            config_obj = source["config"]

            # Type-specific validation
            if source.get("type") == "csv":
                # Check required CSV config
                if "file_path" not in config_obj:
                    errors.append(f"Source {source_num}: CSV source missing 'file_path'")
                    print("  ❌ Missing 'file_path'")
                else:
                    file_path = Path(config_obj["file_path"])
                    print(f"  File: {file_path}")

                    # Check file exists if enabled
                    if source.get("enabled") and not file_path.exists():
                        errors.append(
                            f"Source {source_num}: File not found: {file_path}"
                        )
                        print(f"  ❌ File not found: {file_path}")
                    elif file_path.exists():
                        size = file_path.stat().st_size
                        print(f"  ✅ File exists ({size:,} bytes)")

                if "region" not in config_obj:
                    errors.append(f"Source {source_num}: Missing 'region'")
                    print("  ❌ Missing 'region'")
                else:
                    print(f"  Region: {config_obj['region']}")

                if "column_mapping" not in config_obj:
                    errors.append(f"Source {source_num}: CSV source missing 'column_mapping'")
                    print("  ❌ Missing 'column_mapping'")
                else:
                    mapping = config_obj["column_mapping"]
                    print(f"  Column mapping: {len(mapping)} columns")

                    # Check required mapped fields
                    required_fields = [
                        "item_code",
                        "description",
                        "classification_code",
                        "unit_price",
                    ]
                    for field in required_fields:
                        if field not in mapping.values():
                            warnings.append(
                                f"Source {source_num}: Column mapping missing recommended field '{field}'"
                            )
                            print(f"  ⚠️  Column mapping missing: {field}")

            elif source.get("type") == "api":
                # Check required API config
                if "api_url" not in config_obj:
                    errors.append(f"Source {source_num}: API source missing 'api_url'")
                    print("  ❌ Missing 'api_url'")
                else:
                    print(f"  API URL: {config_obj['api_url']}")

                if "api_key_env" in config_obj:
                    env_var = config_obj["api_key_env"]
                    print(f"  API Key Env: {env_var}")

                    # Check environment variable is set
                    if source.get("enabled") and env_var not in os.environ:
                        errors.append(
                            f"Source {source_num}: Environment variable not set: {env_var}"
                        )
                        print(f"  ❌ Environment variable not set: {env_var}")
                    elif env_var in os.environ:
                        # Don't print the actual key
                        key_len = len(os.environ[env_var])
                        print(f"  ✅ API key found ({key_len} characters)")

                if "region" not in config_obj:
                    errors.append(f"Source {source_num}: Missing 'region'")
                    print("  ❌ Missing 'region'")
                else:
                    print(f"  Region: {config_obj['region']}")

                # Check rate limiting
                if "rate_limit" in config_obj:
                    rate = config_obj["rate_limit"]
                    print(f"  Rate Limit: {rate} req/s")
                    if rate > 100:
                        warnings.append(
                            f"Source {source_num}: Very high rate limit ({rate} req/s) - verify with provider"
                        )
                        print(f"  ⚠️  Very high rate limit: {rate} req/s")

        print()

    # Summary
    print("=" * 50)
    print("Validation Summary")
    print("=" * 50)
    print(f"Total sources: {len(sources)}")
    print(f"Enabled sources: {enabled_count}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    print()

    if errors:
        print("❌ ERRORS:")
        for error in errors:
            print(f"  - {error}")
        print()

    if warnings:
        print("⚠️  WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    if errors:
        print("❌ Configuration validation FAILED")
        print("   Fix errors before running pipeline")
        return False

    if enabled_count == 0:
        print("⚠️  No sources enabled")
        print("   Set 'enabled: true' for at least one source")
        return True

    print("✅ Configuration validation PASSED")
    print(f"   Ready to run pipeline with {enabled_count} enabled source(s)")
    return True


if __name__ == "__main__":
    success = validate_config()
    sys.exit(0 if success else 1)
