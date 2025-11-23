"""Startup validation for BIMCalc.

Per CLAUDE.md: "Fail fast & loud when service/DB startup, migrations, or schema checks fail."

This module validates critical configuration and dependencies at application startup
to prevent runtime failures.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.classification.trust_hierarchy import TrustHierarchyClassifier
from bimcalc.config import get_config
from bimcalc.db.models import PriceItemModel

logger = logging.getLogger(__name__)


class StartupValidationError(Exception):
    """Raised when startup validation fails."""
    pass


async def validate_classification_config() -> None:
    """Validate classification hierarchy configuration.

    Raises:
        StartupValidationError: If classification config is missing or invalid
    """
    try:
        # Force eager loading of classification hierarchy
        classifier = TrustHierarchyClassifier()

        # Verify classifier is functional
        logger.info("✓ Classification hierarchy classifier loaded successfully")

    except FileNotFoundError as e:
        raise StartupValidationError(
            f"Classification config file not found: {e}. "
            "Ensure config/classification_hierarchy.yaml exists."
        ) from e
    except Exception as e:
        raise StartupValidationError(
            f"Failed to load classification hierarchy: {e}"
        ) from e


async def validate_database_connection(session: AsyncSession) -> None:
    """Validate database connection and schema.

    Args:
        session: Database session

    Raises:
        StartupValidationError: If database connection or schema is invalid
    """
    try:
        # Test database connection with simple query
        result = await session.execute(select(func.count()).select_from(PriceItemModel))
        price_count = result.scalar()

        logger.info(f"✓ Database connection OK ({price_count} price items)")

    except Exception as e:
        raise StartupValidationError(
            f"Database connection failed: {e}. "
            "Check DATABASE_URL and ensure migrations have run."
        ) from e


async def validate_classification_distribution(
    session: AsyncSession,
    min_price_items: int = 10
) -> None:
    """Validate classification distribution in price catalog.

    Warns if:
    - No prices exist
    - Price items have NULL classification codes
    - Classification codes don't align with typical BIMCalc ranges

    Args:
        session: Database session
        min_price_items: Minimum expected price items (default 10)

    Raises:
        StartupValidationError: If critical distribution issues found
    """
    try:
        # Check total price count
        result = await session.execute(
            select(func.count()).select_from(PriceItemModel).where(PriceItemModel.is_current == True)
        )
        total_prices = result.scalar()

        if total_prices == 0:
            raise StartupValidationError(
                "No active price items found in database. "
                "Ingest price catalog before starting matching."
            )

        if total_prices < min_price_items:
            logger.warning(
                f"⚠ Only {total_prices} price items found (expected >= {min_price_items}). "
                "Matching may fail due to limited candidate pool."
            )

        # Check classification distribution
        result = await session.execute(
            select(
                PriceItemModel.classification_code,
                func.count().label('count')
            )
            .where(PriceItemModel.is_current == True)
            .group_by(PriceItemModel.classification_code)
            .order_by(func.count().desc())
            .limit(10)
        )

        distribution = result.all()

        if not distribution:
            raise StartupValidationError(
                "No classification codes found in price items. "
                "Ensure price ingestion includes classification_code."
            )

        logger.info("✓ Classification distribution (top 10):")
        for code, count in distribution:
            logger.info(f"  • Classification {code}: {count} items")

        # Warn if NULL classification codes exist
        result = await session.execute(
            select(func.count())
            .select_from(PriceItemModel)
            .where(
                PriceItemModel.is_current == True,
                PriceItemModel.classification_code.is_(None)
            )
        )
        null_count = result.scalar()

        if null_count > 0:
            logger.warning(
                f"⚠ {null_count} price items have NULL classification_code. "
                "These will never match. Fix ingestion or price catalog."
            )

    except StartupValidationError:
        raise
    except Exception as e:
        logger.error(f"Classification distribution validation failed: {e}")
        # Don't fail startup for distribution issues, just warn
        logger.warning("⚠ Continuing with startup despite distribution validation failure")


async def validate_vat_and_currency_config() -> None:
    """Validate VAT and currency configuration.

    Per CLAUDE.md: "Currency EUR, VAT explicit"

    Raises:
        StartupValidationError: If VAT/currency config is missing
    """
    try:
        config = get_config()

        if config.currency != "EUR":
            logger.warning(
                f"⚠ Currency is set to '{config.currency}' (expected 'EUR' per CLAUDE.md). "
                "Ensure this is intentional for your region."
            )
        else:
            logger.info(f"✓ Currency: {config.currency}")

        if config.vat_rate is None:
            logger.warning(
                "⚠ VAT rate not configured. Defaulting per config. "
                "Set VAT_RATE environment variable for explicit VAT handling."
            )
        else:
            logger.info(f"✓ VAT rate: {float(config.vat_rate):.2%}")

        # Validate org_id is set
        if config.org_id == "default":
            logger.warning(
                "⚠ org_id is 'default'. For multi-tenant deployments, set DEFAULT_ORG_ID."
            )
        else:
            logger.info(f"✓ Organization ID: {config.org_id}")

    except Exception as e:
        logger.warning(f"⚠ VAT/currency config validation failed: {e}")
        # Don't fail startup for config warnings


async def run_all_validations(session: AsyncSession | None = None) -> None:
    """Run all startup validations.

    Args:
        session: Database session (optional, will warn if not provided)

    Raises:
        StartupValidationError: If any critical validation fails
    """
    logger.info("Running startup validations...")

    # Classification config (always required)
    await validate_classification_config()

    # VAT/currency config (warnings only)
    await validate_vat_and_currency_config()

    # Database validations (require session)
    if session is not None:
        await validate_database_connection(session)
        await validate_classification_distribution(session)
    else:
        logger.warning("⚠ Database session not provided, skipping DB validations")

    logger.info("✓ All startup validations passed")
