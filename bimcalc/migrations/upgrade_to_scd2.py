"""Migration: Upgrade PriceItem to SCD Type-2 with governance fields.

This migration transforms the price_items table to support:
1. Full SCD Type-2 price history tracking
2. Governance fields for data provenance and auditability
3. Composite business key (item_code + region)

IMPORTANT: This is a breaking change. Backup your database before running.

Usage:
    python -m bimcalc.migrations.upgrade_to_scd2 --execute
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import typer
from rich.console import Console
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.connection import get_engine, get_session

logger = logging.getLogger(__name__)
console = Console()

app = typer.Typer()


MIGRATION_SQL = """
-- Step 1: Add new columns to price_items table
ALTER TABLE price_items
ADD COLUMN IF NOT EXISTS item_code TEXT,
ADD COLUMN IF NOT EXISTS region TEXT DEFAULT 'UK',
ADD COLUMN IF NOT EXISTS source_name TEXT,
ADD COLUMN IF NOT EXISTS source_currency VARCHAR(3),
ADD COLUMN IF NOT EXISTS original_effective_date TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS valid_from TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS valid_to TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT TRUE;

-- Step 2: Populate item_code from SKU for existing records
UPDATE price_items
SET item_code = sku
WHERE item_code IS NULL;

-- Step 3: Populate source fields with defaults for existing records
UPDATE price_items
SET source_name = COALESCE(vendor_id, 'legacy_import'),
    source_currency = currency,
    valid_from = created_at
WHERE source_name IS NULL;

-- Step 4: Make new required fields NOT NULL
ALTER TABLE price_items
ALTER COLUMN item_code SET NOT NULL,
ALTER COLUMN region SET NOT NULL,
ALTER COLUMN source_name SET NOT NULL,
ALTER COLUMN source_currency SET NOT NULL,
ALTER COLUMN valid_from SET NOT NULL,
ALTER COLUMN is_current SET NOT NULL;

-- Step 5: Add new constraints
ALTER TABLE price_items
DROP CONSTRAINT IF EXISTS check_valid_period,
ADD CONSTRAINT check_valid_period
CHECK (valid_to IS NULL OR valid_to > valid_from);

-- Step 6: Create new indexes for SCD Type-2 queries
CREATE INDEX IF NOT EXISTS idx_price_active_unique
ON price_items (item_code, region)
WHERE is_current = true;

CREATE INDEX IF NOT EXISTS idx_price_temporal
ON price_items (item_code, region, valid_from, valid_to);

CREATE INDEX IF NOT EXISTS idx_price_current
ON price_items (item_code, region, is_current);

CREATE INDEX IF NOT EXISTS idx_price_source
ON price_items (source_name, last_updated);

-- Step 7: Create data_sync_log table
CREATE TABLE IF NOT EXISTS data_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    source_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'PARTIAL_SUCCESS', 'SKIPPED')),
    records_updated INTEGER NOT NULL DEFAULT 0 CHECK (records_updated >= 0),
    records_inserted INTEGER NOT NULL DEFAULT 0 CHECK (records_inserted >= 0),
    records_failed INTEGER NOT NULL DEFAULT 0 CHECK (records_failed >= 0),
    message TEXT,
    error_details JSONB,
    duration_seconds FLOAT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Step 8: Create indexes for data_sync_log
CREATE INDEX IF NOT EXISTS idx_sync_run
ON data_sync_log (run_timestamp, source_name);

CREATE INDEX IF NOT EXISTS idx_sync_failures
ON data_sync_log (status, run_timestamp);

CREATE INDEX IF NOT EXISTS idx_sync_source_health
ON data_sync_log (source_name, status, run_timestamp);
"""

ROLLBACK_SQL = """
-- WARNING: This rollback will DESTROY SCD Type-2 history
-- Only use if migration needs to be reverted

-- Drop new indexes
DROP INDEX IF EXISTS idx_price_active_unique;
DROP INDEX IF EXISTS idx_price_temporal;
DROP INDEX IF EXISTS idx_price_current;
DROP INDEX IF EXISTS idx_price_source;
DROP INDEX IF EXISTS idx_sync_run;
DROP INDEX IF EXISTS idx_sync_failures;
DROP INDEX IF EXISTS idx_sync_source_health;

-- Drop new table
DROP TABLE IF EXISTS data_sync_log;

-- Remove new columns (loses SCD Type-2 history)
ALTER TABLE price_items
DROP COLUMN IF EXISTS item_code,
DROP COLUMN IF EXISTS region,
DROP COLUMN IF EXISTS source_name,
DROP COLUMN IF EXISTS source_currency,
DROP COLUMN IF EXISTS original_effective_date,
DROP COLUMN IF EXISTS valid_from,
DROP COLUMN IF EXISTS valid_to,
DROP COLUMN IF EXISTS is_current;

-- Remove new constraint
ALTER TABLE price_items
DROP CONSTRAINT IF EXISTS check_valid_period;
"""


async def run_migration(session: AsyncSession, dry_run: bool = False) -> None:
    """Execute migration SQL."""
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")
        console.print("[bold]Migration SQL:[/bold]")
        console.print(MIGRATION_SQL)
        return

    console.print("[bold]Executing migration...[/bold]")

    try:
        # Run migration in a transaction
        await session.execute(text(MIGRATION_SQL))
        await session.commit()

        console.print("[bold green]✓[/bold green] Migration completed successfully!")

        # Verify data_sync_log table exists
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'data_sync_log'"
            )
        )
        count = result.scalar()

        if count == 1:
            console.print("[bold green]✓[/bold green] data_sync_log table created")
        else:
            console.print("[bold red]✗[/bold red] data_sync_log table not found")

        # Count updated records
        result = await session.execute(text("SELECT COUNT(*) FROM price_items WHERE is_current = true"))
        active_count = result.scalar()
        console.print(f"[bold green]✓[/bold green] {active_count} active price records")

    except Exception as e:
        await session.rollback()
        console.print(f"[bold red]✗[/bold red] Migration failed: {e}")
        raise


async def run_rollback(session: AsyncSession, dry_run: bool = False) -> None:
    """Execute rollback SQL."""
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")
        console.print("[bold red]Rollback SQL (DESTRUCTIVE):[/bold red]")
        console.print(ROLLBACK_SQL)
        return

    console.print("[bold red]WARNING: This will destroy SCD Type-2 history![/bold red]")
    confirm = typer.confirm("Are you sure you want to rollback?")

    if not confirm:
        console.print("[yellow]Rollback cancelled[/yellow]")
        return

    console.print("[bold]Executing rollback...[/bold]")

    try:
        await session.execute(text(ROLLBACK_SQL))
        await session.commit()
        console.print("[bold green]✓[/bold green] Rollback completed")

    except Exception as e:
        await session.rollback()
        console.print(f"[bold red]✗[/bold red] Rollback failed: {e}")
        raise


@app.command()
def migrate(
    execute: bool = typer.Option(False, "--execute", help="Execute migration (default: dry-run)"),
    rollback: bool = typer.Option(False, "--rollback", help="Rollback migration (DESTRUCTIVE)"),
):
    """Upgrade database to SCD Type-2 schema."""

    async def _run():
        async with get_session() as session:
            if rollback:
                await run_rollback(session, dry_run=not execute)
            else:
                await run_migration(session, dry_run=not execute)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
