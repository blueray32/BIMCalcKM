"""Migration: Add org_id to PriceItem for multi-tenant isolation.

This migration adds org_id field to price_items table to support:
1. Multi-tenant price catalog isolation
2. Organization-specific pricing
3. Proper candidate filtering by org

CRITICAL: This enforces multi-tenant scoping as required by CLAUDE.md

Usage:
    python -m bimcalc.migrations.add_org_id_to_prices --execute
"""

from __future__ import annotations

import asyncio
import logging

import typer
from rich.console import Console
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.connection import get_session

logger = logging.getLogger(__name__)
console = Console()

app = typer.Typer()


MIGRATION_SQL = """
-- Step 1: Add org_id column to price_items table
ALTER TABLE price_items
ADD COLUMN IF NOT EXISTS org_id TEXT;

-- Step 2: Populate org_id with 'default' for existing records
-- (In production, you may want to update this based on actual org data)
UPDATE price_items
SET org_id = 'default'
WHERE org_id IS NULL;

-- Step 3: Make org_id NOT NULL after populating
ALTER TABLE price_items
ALTER COLUMN org_id SET NOT NULL;

-- Step 4: Create index for org_id (critical for multi-tenant queries)
CREATE INDEX IF NOT EXISTS idx_price_org
ON price_items (org_id);

-- Step 5: Drop existing unique index and recreate with org_id
DROP INDEX IF EXISTS idx_price_active_unique;

CREATE UNIQUE INDEX idx_price_active_unique
ON price_items (org_id, item_code, region)
WHERE is_current = true;

-- Step 6: Drop existing temporal and current indexes and recreate with org_id
DROP INDEX IF EXISTS idx_price_temporal;
CREATE INDEX idx_price_temporal
ON price_items (org_id, item_code, region, valid_from, valid_to);

DROP INDEX IF EXISTS idx_price_current;
CREATE INDEX idx_price_current
ON price_items (org_id, item_code, region, is_current);
"""

ROLLBACK_SQL = """
-- WARNING: This rollback will remove org_id and lose multi-tenant isolation

-- Step 1: Recreate indexes without org_id
DROP INDEX IF EXISTS idx_price_active_unique;
CREATE UNIQUE INDEX idx_price_active_unique
ON price_items (item_code, region)
WHERE is_current = true;

DROP INDEX IF EXISTS idx_price_temporal;
CREATE INDEX idx_price_temporal
ON price_items (item_code, region, valid_from, valid_to);

DROP INDEX IF EXISTS idx_price_current;
CREATE INDEX idx_price_current
ON price_items (item_code, region, is_current);

-- Step 2: Drop org_id index
DROP INDEX IF EXISTS idx_price_org;

-- Step 3: Remove org_id column
ALTER TABLE price_items
DROP COLUMN IF EXISTS org_id;
"""


async def run_migration(session: AsyncSession, dry_run: bool = False) -> None:
    """Execute migration SQL."""
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")
        console.print("[bold]Migration SQL:[/bold]")
        console.print(MIGRATION_SQL)
        return

    console.print("[bold]Executing migration to add org_id to price_items...[/bold]")

    try:
        # Run migration in a transaction
        await session.execute(text(MIGRATION_SQL))
        await session.commit()

        console.print("[bold green]✓[/bold green] Migration completed successfully!")

        # Verify org_id column exists
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = 'price_items' AND column_name = 'org_id'"
            )
        )
        count = result.scalar()

        if count == 1:
            console.print("[bold green]✓[/bold green] org_id column added to price_items")
        else:
            console.print("[bold red]✗[/bold red] org_id column not found")

        # Count price records by org
        result = await session.execute(
            text("SELECT org_id, COUNT(*) FROM price_items WHERE is_current = true GROUP BY org_id")
        )
        org_counts = result.all()
        console.print("[bold green]✓[/bold green] Price records by org:")
        for org_id, count in org_counts:
            console.print(f"  • {org_id}: {count} active prices")

    except Exception as e:
        await session.rollback()
        console.print(f"[bold red]✗[/bold red] Migration failed: {e}")
        raise


async def run_rollback(session: AsyncSession, dry_run: bool = False) -> None:
    """Execute rollback SQL."""
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")
        console.print("[bold red]Rollback SQL (REMOVES MULTI-TENANT ISOLATION):[/bold red]")
        console.print(ROLLBACK_SQL)
        return

    console.print("[bold red]WARNING: This will remove multi-tenant isolation![/bold red]")
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
    rollback: bool = typer.Option(False, "--rollback", help="Rollback migration (REMOVES MULTI-TENANT ISOLATION)"),
):
    """Add org_id to price_items for multi-tenant isolation."""

    async def _run():
        async with get_session() as session:
            if rollback:
                await run_rollback(session, dry_run=not execute)
            else:
                await run_migration(session, dry_run=not execute)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
