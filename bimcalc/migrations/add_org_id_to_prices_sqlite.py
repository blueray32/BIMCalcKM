"""SQLite-specific migration: Add org_id to PriceItem for multi-tenant isolation.

SQLite doesn't support ALTER COLUMN, so we use a table recreation approach.

Usage:
    python -m bimcalc.migrations.add_org_id_to_prices_sqlite --execute
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
-- SQLite Migration: Add org_id to price_items

-- Step 1: Add org_id column (SQLite allows adding columns with DEFAULT)
ALTER TABLE price_items ADD COLUMN org_id TEXT DEFAULT 'default' NOT NULL;

-- Step 2: Create index for org_id
CREATE INDEX IF NOT EXISTS idx_price_org ON price_items(org_id);

-- Step 3: Drop and recreate idx_price_active_unique with org_id
-- Note: SQLite doesn't support partial indexes in the same way, but we can recreate it
DROP INDEX IF EXISTS idx_price_active_unique;
CREATE UNIQUE INDEX idx_price_active_unique
ON price_items(org_id, item_code, region)
WHERE is_current = 1;

-- Step 4: Drop and recreate temporal index with org_id
DROP INDEX IF EXISTS idx_price_temporal;
CREATE INDEX idx_price_temporal
ON price_items(org_id, item_code, region, valid_from, valid_to);

-- Step 5: Drop and recreate current index with org_id
DROP INDEX IF EXISTS idx_price_current;
CREATE INDEX idx_price_current
ON price_items(org_id, item_code, region, is_current);
"""

ROLLBACK_SQL = """
-- SQLite Rollback: Remove org_id (requires table recreation)

-- WARNING: This is a complex rollback for SQLite
-- Recommended: Restore from backup instead

BEGIN TRANSACTION;

-- Recreate indexes without org_id
DROP INDEX IF EXISTS idx_price_active_unique;
CREATE UNIQUE INDEX idx_price_active_unique
ON price_items(item_code, region)
WHERE is_current = 1;

DROP INDEX IF EXISTS idx_price_temporal;
CREATE INDEX idx_price_temporal
ON price_items(item_code, region, valid_from, valid_to);

DROP INDEX IF EXISTS idx_price_current;
CREATE INDEX idx_price_current
ON price_items(item_code, region, is_current);

DROP INDEX IF EXISTS idx_price_org;

-- SQLite doesn't support DROP COLUMN easily
-- You'll need to recreate the table without org_id
-- This is complex and data-destructive - restore from backup instead

COMMIT;
"""


async def run_migration(session: AsyncSession, dry_run: bool = False) -> None:
    """Execute SQLite migration."""
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")
        console.print("[bold]Migration SQL:[/bold]")
        console.print(MIGRATION_SQL)
        return

    console.print(
        "[bold]Executing SQLite migration to add org_id to price_items...[/bold]"
    )
    console.print("[yellow]⚠ Creating backup is recommended before proceeding[/yellow]")

    try:
        # SQLite requires executing statements one at a time
        statements = [
            s.strip()
            for s in MIGRATION_SQL.split(";")
            if s.strip() and not s.strip().startswith("--")
        ]

        for stmt in statements:
            if stmt:
                console.print(f"[dim]Executing: {stmt[:50]}...[/dim]")
                await session.execute(text(stmt))

        await session.commit()

        console.print("[bold green]✓[/bold green] Migration completed successfully!")

        # Verify org_id column exists
        result = await session.execute(text("PRAGMA table_info(price_items)"))
        columns = result.fetchall()
        has_org_id = any(col[1] == "org_id" for col in columns)

        if has_org_id:
            console.print(
                "[bold green]✓[/bold green] org_id column added to price_items"
            )
        else:
            console.print("[bold red]✗[/bold red] org_id column not found")

        # Count price records by org
        result = await session.execute(
            text(
                "SELECT org_id, COUNT(*) FROM price_items WHERE is_current = 1 GROUP BY org_id"
            )
        )
        org_counts = result.fetchall()

        if org_counts:
            console.print("[bold green]✓[/bold green] Price records by org:")
            for org_id, count in org_counts:
                console.print(f"  • {org_id}: {count} active prices")
        else:
            console.print("[yellow]⚠[/yellow] No active price records found")

    except Exception as e:
        await session.rollback()
        console.print(f"[bold red]✗[/bold red] Migration failed: {e}")
        raise


async def run_rollback(session: AsyncSession, dry_run: bool = False) -> None:
    """Execute rollback (limited for SQLite)."""
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")
        console.print(
            "[bold red]Rollback SQL (LIMITED - BACKUP RESTORE RECOMMENDED):[/bold red]"
        )
        console.print(ROLLBACK_SQL)
        return

    console.print("[bold red]WARNING: SQLite rollback is limited![/bold red]")
    console.print("[yellow]Recommended: Restore from backup instead[/yellow]")

    confirm = typer.confirm(
        "This will only restore indexes, not remove org_id column. Continue?"
    )

    if not confirm:
        console.print("[yellow]Rollback cancelled[/yellow]")
        return

    console.print("[bold]Executing limited rollback...[/bold]")

    try:
        await session.execute(text(ROLLBACK_SQL))
        await session.commit()
        console.print(
            "[bold yellow]⚠[/bold yellow] Partial rollback completed (indexes only)"
        )
        console.print("[yellow]To fully remove org_id, restore from backup[/yellow]")

    except Exception as e:
        await session.rollback()
        console.print(f"[bold red]✗[/bold red] Rollback failed: {e}")
        raise


@app.command()
def migrate(
    execute: bool = typer.Option(
        False, "--execute", help="Execute migration (default: dry-run)"
    ),
    rollback: bool = typer.Option(
        False, "--rollback", help="Limited rollback (index changes only)"
    ),
):
    """Add org_id to price_items for multi-tenant isolation (SQLite version)."""

    async def _run():
        async with get_session() as session:
            if rollback:
                await run_rollback(session, dry_run=not execute)
            else:
                await run_migration(session, dry_run=not execute)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
