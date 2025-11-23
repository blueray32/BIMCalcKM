"""SQLite-specific migration: Upgrade PriceItem to SCD Type-2.

This migration transforms the price_items table for SQLite databases.
For PostgreSQL, use upgrade_to_scd2.py instead.

IMPORTANT: Backup your database before running.

Usage:
    python -m bimcalc.migrations.upgrade_to_scd2_sqlite --execute
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import typer
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

app = typer.Typer()


def get_db_path() -> Path:
    """Get SQLite database path from environment or default."""
    import os

    db_url = os.environ.get("DATABASE_URL", "sqlite:///./bimcalc.db")

    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        if db_path.startswith("./"):
            db_path = db_path[2:]
        return Path(db_path)

    raise ValueError(f"Not a SQLite database URL: {db_url}")


def run_migration_sqlite(db_path: Path, dry_run: bool = False) -> None:
    """Execute SQLite migration."""

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")
        console.print(f"[bold]Would migrate database:[/bold] {db_path}")
        return

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    console.print(f"[bold]Migrating SQLite database:[/bold] {db_path}")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Step 1: Check if migration already applied
        cursor.execute("PRAGMA table_info(price_items)")
        columns = [row[1] for row in cursor.fetchall()]

        if "is_current" in columns:
            console.print("[yellow]Migration already applied (is_current column exists)[/yellow]")
            console.print("[yellow]Skipping migration[/yellow]")
            return

        console.print("\n[bold]Step 1:[/bold] Creating new price_items table with SCD Type-2 schema")

        # Step 2: Rename old table
        cursor.execute("ALTER TABLE price_items RENAME TO price_items_old")

        # Step 3: Create new table with enhanced schema
        cursor.execute("""
            CREATE TABLE price_items (
                id TEXT PRIMARY KEY,
                item_code TEXT NOT NULL,
                region TEXT NOT NULL DEFAULT 'UK',
                classification_code INTEGER NOT NULL,
                vendor_id TEXT,
                sku TEXT NOT NULL,
                description TEXT NOT NULL,
                unit TEXT NOT NULL,
                unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
                currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
                vat_rate NUMERIC(5, 2),
                width_mm FLOAT,
                height_mm FLOAT,
                dn_mm FLOAT,
                angle_deg FLOAT,
                material TEXT,
                source_name TEXT NOT NULL,
                source_currency VARCHAR(3) NOT NULL,
                original_effective_date TIMESTAMP,
                valid_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                valid_to TIMESTAMP,
                is_current BOOLEAN NOT NULL DEFAULT 1,
                last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                vendor_note TEXT,
                attributes JSON NOT NULL DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (valid_to IS NULL OR valid_to > valid_from)
            )
        """)

        console.print("[green]✓[/green] New table created")

        # Step 4: Migrate data from old to new
        console.print("\n[bold]Step 2:[/bold] Migrating existing price records")

        cursor.execute("""
            INSERT INTO price_items (
                id, item_code, region, classification_code, vendor_id, sku,
                description, unit, unit_price, currency, vat_rate,
                width_mm, height_mm, dn_mm, angle_deg, material,
                source_name, source_currency, valid_from, is_current,
                last_updated, vendor_note, attributes, created_at
            )
            SELECT
                id,
                sku as item_code,  -- Use SKU as item_code
                'UK' as region,    -- Default region
                classification_code,
                vendor_id,
                sku,
                description,
                unit,
                unit_price,
                currency,
                vat_rate,
                width_mm,
                height_mm,
                dn_mm,
                angle_deg,
                material,
                COALESCE(vendor_id, 'legacy_import') as source_name,
                currency as source_currency,
                created_at as valid_from,
                1 as is_current,
                COALESCE(last_updated, created_at) as last_updated,
                vendor_note,
                COALESCE(attributes, '{}') as attributes,
                created_at
            FROM price_items_old
        """)

        migrated_count = cursor.rowcount
        console.print(f"[green]✓[/green] Migrated {migrated_count} price records")

        # Step 5: Create indexes
        console.print("\n[bold]Step 3:[/bold] Creating indexes")

        indexes = [
            ("idx_price_class", "CREATE INDEX IF NOT EXISTS idx_price_class ON price_items (classification_code)"),
            ("idx_price_item_code", "CREATE INDEX IF NOT EXISTS idx_price_item_code ON price_items (item_code)"),
            ("idx_price_region", "CREATE INDEX IF NOT EXISTS idx_price_region ON price_items (region)"),
            ("idx_price_current", "CREATE INDEX IF NOT EXISTS idx_price_current ON price_items (item_code, region, is_current)"),
            ("idx_price_temporal", "CREATE INDEX IF NOT EXISTS idx_price_temporal ON price_items (item_code, region, valid_from, valid_to)"),
            ("idx_price_source", "CREATE INDEX IF NOT EXISTS idx_price_source ON price_items (source_name, last_updated)"),
        ]

        for idx_name, idx_sql in indexes:
            cursor.execute(idx_sql)
            console.print(f"  [green]✓[/green] Created {idx_name}")

        # Step 6: Create data_sync_log table
        console.print("\n[bold]Step 4:[/bold] Creating data_sync_log table")

        cursor.execute("""
            CREATE TABLE data_sync_log (
                id TEXT PRIMARY KEY,
                run_timestamp TIMESTAMP NOT NULL,
                source_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'PARTIAL_SUCCESS', 'SKIPPED')),
                records_updated INTEGER NOT NULL DEFAULT 0 CHECK (records_updated >= 0),
                records_inserted INTEGER NOT NULL DEFAULT 0 CHECK (records_inserted >= 0),
                records_failed INTEGER NOT NULL DEFAULT 0 CHECK (records_failed >= 0),
                message TEXT,
                error_details JSON,
                duration_seconds FLOAT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_run ON data_sync_log (run_timestamp, source_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_failures ON data_sync_log (status, run_timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_source_health ON data_sync_log (source_name, status, run_timestamp)")

        console.print("[green]✓[/green] data_sync_log table created")

        # Step 7: Drop old table
        console.print("\n[bold]Step 5:[/bold] Cleaning up")
        cursor.execute("DROP TABLE price_items_old")
        console.print("[green]✓[/green] Old table removed")

        # Commit all changes
        conn.commit()

        console.print("\n[bold green]✓ Migration completed successfully![/bold green]")
        console.print(f"[bold green]✓[/bold green] {migrated_count} price records migrated")
        console.print("[bold green]✓[/bold green] All indexes created")
        console.print("[bold green]✓[/bold green] data_sync_log table ready")

    except Exception as e:
        conn.rollback()
        console.print(f"\n[bold red]✗ Migration failed:[/bold red] {e}")
        console.print("\n[yellow]Database rolled back - your data is safe[/yellow]")
        console.print("[yellow]The backup file can be restored if needed[/yellow]")
        raise

    finally:
        conn.close()


def run_rollback_sqlite(db_path: Path, dry_run: bool = False) -> None:
    """Rollback migration (DESTRUCTIVE - loses SCD Type-2 history)."""

    if dry_run:
        console.print("[yellow]DRY RUN MODE[/yellow]\n")
        console.print("[bold red]Would rollback migration (DESTRUCTIVE)[/bold red]")
        return

    console.print("[bold red]WARNING: Rollback will DESTROY SCD Type-2 history![/bold red]")
    console.print("[yellow]This cannot be undone![/yellow]\n")

    confirm = typer.confirm("Are you absolutely sure you want to rollback?")
    if not confirm:
        console.print("[yellow]Rollback cancelled[/yellow]")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Check if new schema exists
        cursor.execute("PRAGMA table_info(price_items)")
        columns = [row[1] for row in cursor.fetchall()]

        if "is_current" not in columns:
            console.print("[yellow]Migration not applied - nothing to rollback[/yellow]")
            return

        console.print("[bold]Rolling back migration...[/bold]")

        # Create old schema table
        cursor.execute("ALTER TABLE price_items RENAME TO price_items_new")

        cursor.execute("""
            CREATE TABLE price_items (
                id TEXT PRIMARY KEY,
                classification_code INTEGER NOT NULL,
                vendor_id TEXT,
                sku TEXT NOT NULL,
                description TEXT NOT NULL,
                unit TEXT NOT NULL,
                unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
                currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
                vat_rate NUMERIC(5, 2),
                width_mm FLOAT,
                height_mm FLOAT,
                dn_mm FLOAT,
                angle_deg FLOAT,
                material TEXT,
                last_updated TIMESTAMP,
                vendor_note TEXT,
                attributes JSON NOT NULL DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Copy back only current records
        cursor.execute("""
            INSERT INTO price_items
            SELECT
                id, classification_code, vendor_id, sku, description,
                unit, unit_price, currency, vat_rate,
                width_mm, height_mm, dn_mm, angle_deg, material,
                last_updated, vendor_note, attributes, created_at
            FROM price_items_new
            WHERE is_current = 1
        """)

        rollback_count = cursor.rowcount

        # Drop new tables
        cursor.execute("DROP TABLE price_items_new")
        cursor.execute("DROP TABLE IF EXISTS data_sync_log")

        conn.commit()

        console.print("[bold green]✓[/bold green] Rollback completed")
        console.print(f"[yellow]⚠[/yellow] Kept {rollback_count} current records (history lost)")

    except Exception as e:
        conn.rollback()
        console.print(f"[bold red]✗[/bold red] Rollback failed: {e}")
        raise

    finally:
        conn.close()


@app.command()
def migrate(
    execute: bool = typer.Option(False, "--execute", help="Execute migration (default: dry-run)"),
    rollback: bool = typer.Option(False, "--rollback", help="Rollback migration (DESTRUCTIVE)"),
):
    """Upgrade SQLite database to SCD Type-2 schema."""

    try:
        db_path = get_db_path()

        if rollback:
            run_rollback_sqlite(db_path, dry_run=not execute)
        else:
            run_migration_sqlite(db_path, dry_run=not execute)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
