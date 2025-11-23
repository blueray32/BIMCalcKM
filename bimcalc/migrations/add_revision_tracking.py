"""Migration: Add revision tracking and ingest logging tables.

This migration adds:
1. item_revisions table - Track field-level changes across Revit imports
2. ingest_logs table - Track import operations with statistics

Enables:
- Revision delta reports
- Change detection between imports
- Ingest history viewing
- Import performance monitoring

Usage:
    python -m bimcalc.migrations.add_revision_tracking --execute
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
-- ============================================================================
-- Step 1: Create item_revisions table
-- ============================================================================
CREATE TABLE IF NOT EXISTS item_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Links to item and import
    item_id UUID NOT NULL,
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,

    -- Ingest metadata
    ingest_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    source_filename TEXT,

    -- Change tracking
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    change_type TEXT NOT NULL CHECK (change_type IN ('added', 'modified', 'deleted', 'unchanged')),

    -- Audit
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Indexes for item_revisions
CREATE INDEX IF NOT EXISTS idx_revisions_item_id
ON item_revisions (item_id);

CREATE INDEX IF NOT EXISTS idx_revisions_org_id
ON item_revisions (org_id);

CREATE INDEX IF NOT EXISTS idx_revisions_project_id
ON item_revisions (project_id);

CREATE INDEX IF NOT EXISTS idx_revisions_ingest_timestamp
ON item_revisions (ingest_timestamp);

CREATE INDEX IF NOT EXISTS idx_revisions_field_name
ON item_revisions (field_name);

CREATE INDEX IF NOT EXISTS idx_revisions_change_type
ON item_revisions (change_type);

CREATE INDEX IF NOT EXISTS idx_revisions_item_field
ON item_revisions (item_id, field_name);

CREATE INDEX IF NOT EXISTS idx_revisions_org_project_timestamp
ON item_revisions (org_id, project_id, ingest_timestamp);

-- ============================================================================
-- Step 2: Create ingest_logs table
-- ============================================================================
CREATE TABLE IF NOT EXISTS ingest_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,

    -- Import details
    filename TEXT NOT NULL,
    file_hash TEXT,

    -- Statistics
    items_total INTEGER NOT NULL DEFAULT 0,
    items_added INTEGER NOT NULL DEFAULT 0,
    items_modified INTEGER NOT NULL DEFAULT 0,
    items_unchanged INTEGER NOT NULL DEFAULT 0,
    items_deleted INTEGER NOT NULL DEFAULT 0,

    -- Error tracking
    errors INTEGER NOT NULL DEFAULT 0,
    warnings INTEGER NOT NULL DEFAULT 0,
    error_details JSONB DEFAULT '{}'::jsonb,

    -- Performance
    processing_time_ms INTEGER,

    -- Status
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),

    -- Audit
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_by TEXT NOT NULL DEFAULT 'system'
);

-- Indexes for ingest_logs
CREATE INDEX IF NOT EXISTS idx_ingest_org_id
ON ingest_logs (org_id);

CREATE INDEX IF NOT EXISTS idx_ingest_project_id
ON ingest_logs (project_id);

CREATE INDEX IF NOT EXISTS idx_ingest_status
ON ingest_logs (status);

CREATE INDEX IF NOT EXISTS idx_ingest_started_at
ON ingest_logs (started_at);

CREATE INDEX IF NOT EXISTS idx_ingest_org_project_started
ON ingest_logs (org_id, project_id, started_at);

-- ============================================================================
-- Step 3: Create helpful views for common queries
-- ============================================================================

-- View: Latest revisions per item
CREATE OR REPLACE VIEW latest_item_revisions AS
SELECT DISTINCT ON (item_id, field_name)
    ir.*
FROM item_revisions ir
ORDER BY item_id, field_name, ingest_timestamp DESC;

-- View: Recent ingest summary
CREATE OR REPLACE VIEW recent_ingests AS
SELECT
    il.id,
    il.org_id,
    il.project_id,
    il.filename,
    il.started_at,
    il.completed_at,
    il.status,
    il.items_total,
    il.items_added,
    il.items_modified,
    il.items_unchanged,
    il.errors,
    il.warnings,
    il.processing_time_ms,
    CASE
        WHEN il.completed_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (il.completed_at - il.started_at)) * 1000
        ELSE NULL
    END as actual_duration_ms
FROM ingest_logs il
ORDER BY il.started_at DESC;
"""

ROLLBACK_SQL = """
-- WARNING: This will delete all revision and ingest log data

-- Drop views
DROP VIEW IF EXISTS recent_ingests;
DROP VIEW IF EXISTS latest_item_revisions;

-- Drop tables
DROP TABLE IF EXISTS ingest_logs CASCADE;
DROP TABLE IF EXISTS item_revisions CASCADE;
"""


async def check_table_exists(session: AsyncSession, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = await session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = :table_name
            )
        """
        ),
        {"table_name": table_name},
    )
    return result.scalar()


async def run_migration(session: AsyncSession, dry_run: bool = False):
    """Execute the migration."""
    console.print("\n[bold cyan]═══ Revision Tracking Migration ═══[/bold cyan]\n")

    # Check existing state
    revisions_exist = await check_table_exists(session, "item_revisions")
    logs_exist = await check_table_exists(session, "ingest_logs")

    console.print("[yellow]Current state:[/yellow]")
    console.print(f"  • item_revisions table: {'✓ exists' if revisions_exist else '✗ missing'}")
    console.print(f"  • ingest_logs table: {'✓ exists' if logs_exist else '✗ missing'}")

    if revisions_exist and logs_exist:
        console.print("\n[green]✓ Tables already exist - migration not needed[/green]")
        return

    if dry_run:
        console.print("\n[bold yellow]DRY RUN MODE - SQL that would be executed:[/bold yellow]")
        console.print(MIGRATION_SQL)
        return

    console.print("\n[bold yellow]Executing migration...[/bold yellow]")

    try:
        # Split SQL into individual statements and execute separately
        # PostgreSQL async doesn't support multiple statements in one call
        statements = [stmt.strip() for stmt in MIGRATION_SQL.split(';') if stmt.strip() and not stmt.strip().startswith('--')]

        for i, stmt in enumerate(statements, 1):
            if stmt:
                console.print(f"  [dim]Executing statement {i}/{len(statements)}...[/dim]")
                await session.execute(text(stmt))

        await session.commit()
        console.print("\n[bold green]✓ Migration completed successfully![/bold green]\n")

        # Verify
        revisions_exist = await check_table_exists(session, "item_revisions")
        logs_exist = await check_table_exists(session, "ingest_logs")

        console.print("[cyan]Verification:[/cyan]")
        console.print(f"  • item_revisions: {'✓' if revisions_exist else '✗'}")
        console.print(f"  • ingest_logs: {'✓' if logs_exist else '✗'}")

    except Exception as e:
        await session.rollback()
        console.print(f"\n[bold red]✗ Migration failed: {e}[/bold red]")
        raise


async def run_rollback(session: AsyncSession, dry_run: bool = False):
    """Rollback the migration."""
    console.print("\n[bold red]═══ Rollback Revision Tracking Migration ═══[/bold red]\n")
    console.print("[yellow]WARNING: This will delete all revision and ingest log data![/yellow]\n")

    if dry_run:
        console.print("[bold yellow]DRY RUN MODE - SQL that would be executed:[/bold yellow]")
        console.print(ROLLBACK_SQL)
        return

    console.print("[bold yellow]Executing rollback...[/bold yellow]")

    try:
        await session.execute(text(ROLLBACK_SQL))
        await session.commit()
        console.print("\n[bold green]✓ Rollback completed successfully![/bold green]\n")
    except Exception as e:
        await session.rollback()
        console.print(f"\n[bold red]✗ Rollback failed: {e}[/bold red]")
        raise


@app.command()
def migrate(
    execute: bool = typer.Option(False, "--execute", help="Actually run the migration (default is dry-run)"),
    rollback: bool = typer.Option(False, "--rollback", help="Rollback the migration"),
):
    """Run or rollback the revision tracking migration."""

    async def _run():
        async with get_session() as session:
            if rollback:
                await run_rollback(session, dry_run=not execute)
            else:
                await run_migration(session, dry_run=not execute)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
