"""Configuration loader for pipeline data sources.

Loads source configurations from YAML and instantiates appropriate importers.
Supports dynamic loading of importer classes based on config type.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import yaml

from bimcalc.pipeline.base_importer import BaseImporter

logger = logging.getLogger(__name__)


# Importer registry (maps type to class)
IMPORTER_REGISTRY = {}


def register_importer(importer_type: str):
    """Decorator to register importer classes.

    Usage:
        @register_importer("csv")
        class CSVFileImporter(BaseImporter):
            ...
    """

    def decorator(cls):
        IMPORTER_REGISTRY[importer_type] = cls
        return cls

    return decorator


def load_pipeline_config(config_path: Path) -> List[BaseImporter]:
    """Load pipeline configuration and instantiate importers.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        List of configured importer instances

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if not config or "sources" not in config:
        raise ValueError("Invalid pipeline config: missing 'sources' section")

    importers = []

    for source_config in config["sources"]:
        if not source_config.get("enabled", True):
            logger.info(f"Skipping disabled source: {source_config.get('name')}")
            continue

        try:
            importer = _create_importer(source_config)
            importers.append(importer)
            logger.info(f"Loaded importer: {importer.source_name} ({source_config['type']})")

        except Exception as e:
            logger.error(f"Failed to load source {source_config.get('name')}: {e}")
            continue

    logger.info(f"Loaded {len(importers)} importers from config")

    return importers


def _create_importer(source_config: dict) -> BaseImporter:
    """Create importer instance from config.

    Args:
        source_config: Source configuration dict

    Returns:
        Configured importer instance

    Raises:
        ValueError: If importer type is unknown
    """
    importer_type = source_config.get("type")
    source_name = source_config.get("name")

    if not importer_type:
        raise ValueError(f"Source {source_name} missing 'type' field")

    # Dynamic import based on type
    if importer_type == "csv":
        from bimcalc.pipeline.importers.csv_importer import CSVFileImporter

        return CSVFileImporter(source_name, source_config["config"])

    elif importer_type == "api":
        from bimcalc.pipeline.importers.api_importer import APIImporter

        return APIImporter(source_name, source_config["config"])

    elif importer_type == "rs_components":
        from bimcalc.pipeline.importers.api_importer import RSComponentsImporter

        return RSComponentsImporter(source_name, source_config["config"])

    elif importer_type == "demo_api":
        from bimcalc.pipeline.importers.demo_api_importer import DemoAPIImporter

        return DemoAPIImporter(source_name, source_config["config"])

    else:
        raise ValueError(f"Unknown importer type: {importer_type}")
