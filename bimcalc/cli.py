"""BIMCalc CLI - Full implementation with async commands.

Commands:
- init: Initialize database schema
- migrate: Run database migrations
- ingest-schedules: Import Revit schedules (CSV/XLSX)
- ingest-prices: Import vendor price books (CSV/XLSX)
- sync-prices: Run automated price synchronization pipeline
- match: Run matching pipeline on project
- report: Generate cost report with as-of query
- stats: Show project statistics
- pipeline-status: Check last pipeline run status
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from bimcalc.config import get_config
from bimcalc.db.connection import get_engine, get_session
from bimcalc.db.match_results import record_match_result
from bimcalc.db.models import Base, ItemMappingModel, ItemModel, MatchResultModel, PriceItemModel
from bimcalc.ingestion.pricebooks import ingest_pricebook
from bimcalc.ingestion.schedules import ingest_schedule
from bimcalc.matching.orchestrator import MatchOrchestrator
from bimcalc.reporting.builder import generate_report

app = typer.Typer(
    name="bimcalc",
    help="BIMCalc - Classification-first cost matching for BIM",
    no_args_is_help=True,
)
review_cli = typer.Typer(help="Review tooling")
app.add_typer(review_cli, name="review")

web_cli = typer.Typer(help="Web UI / API")
app.add_typer(web_cli, name="web")

# Register Agent CLI
from bimcalc.agent.cli import agent_cli
app.add_typer(agent_cli, name="agent")

console = Console()


@app.command()
def init(
    drop: bool = typer.Option(False, "--drop", help="Drop existing tables"),
):
    """Initialize database schema."""
    config = get_config()
    console.print(f"[bold]Initializing database:[/bold] {config.db.url}")

    async def _init():
        engine = get_engine()
        async with engine.begin() as conn:
            if drop:
                console.print("[yellow]Dropping existing tables...[/yellow]")
                await conn.run_sync(Base.metadata.drop_all)
            console.print("[green]Creating tables...[/green]")
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_init())
    console.print("[bold green]✓[/bold green] Database initialized")


@app.command(name="ingest-schedules")
def ingest_schedules_cmd(
    files: list[Path] = typer.Argument(..., help="Schedule files (CSV/XLSX)"),
    org_id: str | None = typer.Option(None, "--org", help="Organization ID"),
    project_id: str | None = typer.Option(None, "--project", help="Project ID"),
):
    """Import Revit schedules from CSV or XLSX files."""
    config = get_config()
    org_id = org_id or config.org_id
    project_id = project_id or "default"

    console.print(f"[bold]Ingesting schedules:[/bold] org={org_id}, project={project_id}")

    async def _ingest():
        total_success = 0
        total_errors = []

        async with get_session() as session:
            for file_path in files:
                console.print(f"  Processing: {file_path}")
                try:
                    success_count, errors = await ingest_schedule(
                        session, file_path, org_id, project_id
                    )
                    total_success += success_count
                    total_errors.extend(errors)
                    console.print(f"    [green]✓[/green] {success_count} items imported")
                    if errors:
                        console.print(f"    [yellow]⚠[/yellow] {len(errors)} errors")
                        for err in errors[:5]:  # Show first 5 errors
                            console.print(f"      {err}", style="dim")
                except Exception as e:
                    console.print(f"    [red]✗[/red] Failed: {e}")
                    total_errors.append(str(e))

        console.print(f"\n[bold green]✓[/bold green] Total: {total_success} items imported")
        if total_errors:
            console.print(f"[yellow]⚠[/yellow] {len(total_errors)} errors (see above)")

    asyncio.run(_ingest())


@app.command(name="ingest-prices")
def ingest_prices_cmd(
    files: list[Path] = typer.Argument(..., help="Price book files (CSV/XLSX)"),
    vendor_id: str = typer.Option("default", "--vendor", help="Vendor ID"),
):
    """Import vendor price books from CSV or XLSX files."""
    console.print(f"[bold]Ingesting price books:[/bold] vendor={vendor_id}")

    async def _ingest():
        total_success = 0
        total_errors = []

        async with get_session() as session:
            for file_path in files:
                console.print(f"  Processing: {file_path}")
                try:
                    success_count, errors = await ingest_pricebook(
                        session, file_path, vendor_id
                    )
                    total_success += success_count
                    total_errors.extend(errors)
                    console.print(f"    [green]✓[/green] {success_count} items imported")
                    if errors:
                        console.print(f"    [yellow]⚠[/yellow] {len(errors)} errors")
                        for err in errors[:5]:
                            console.print(f"      {err}", style="dim")
                except Exception as e:
                    console.print(f"    [red]✗[/red] Failed: {e}")
                    total_errors.append(str(e))

        console.print(f"\n[bold green]✓[/bold green] Total: {total_success} items imported")
        if total_errors:
            console.print(f"[yellow]⚠[/yellow] {len(total_errors)} errors (see above)")

    asyncio.run(_ingest())


@app.command()
def match(
    org_id: str | None = typer.Option(None, "--org", help="Organization ID"),
    project_id: str | None = typer.Option(None, "--project", help="Project ID"),
    created_by: str = typer.Option("cli", "--by", help="Created by user/system"),
    limit: int | None = typer.Option(None, "--limit", help="Limit items to match"),
):
    """Run matching pipeline on project items."""
    config = get_config()
    org_id = org_id or config.org_id
    project_id = project_id or "default"

    console.print(f"[bold]Running matcher:[/bold] org={org_id}, project={project_id}")

    async def _match():
        run_started = datetime.utcnow()
        processed_item_ids: list = []
        async with get_session() as session:
            # CRITICAL: Run startup validations (fail-fast per CLAUDE.md)
            from bimcalc.startup_validation import run_all_validations
            try:
                await run_all_validations(session)
            except Exception as e:
                console.print(f"[bold red]✗ Startup validation failed:[/bold red] {e}")
                console.print("[yellow]Fix configuration issues before running match.[/yellow]")
                return

            orchestrator = MatchOrchestrator(session)

            # Query items for project
            stmt = select(ItemModel).where(
                ItemModel.org_id == org_id,
                ItemModel.project_id == project_id,
            )
            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            items = result.scalars().all()

            if not items:
                console.print("[yellow]No items found for project[/yellow]")
                return

            console.print(f"Found {len(items)} items to match\n")

            auto_accepted = 0
            manual_review = 0
            instant_match = 0

            table = Table(title="Match Results")
            table.add_column("Item", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Confidence", justify="right")
            table.add_column("Flags", style="yellow")

            for item_model in items:
                # Convert model to Pydantic Item
                from bimcalc.models import Item

                item = Item(
                    id=str(item_model.id),
                    org_id=item_model.org_id,
                    project_id=item_model.project_id,
                    family=item_model.family,
                    type_name=item_model.type_name,
                    category=item_model.category,
                    system_type=item_model.system_type,
                    quantity=float(item_model.quantity) if item_model.quantity else None,
                    unit=item_model.unit,
                    width_mm=item_model.width_mm,
                    height_mm=item_model.height_mm,
                    dn_mm=item_model.dn_mm,
                    angle_deg=item_model.angle_deg,
                    material=item_model.material,
                )

                match_result, price_item = await orchestrator.match(item, created_by)

                # Persist canonical metadata generated during matching so downstream
                # reports and approval workflows have valid keys.
                item_model.canonical_key = item.canonical_key
                item_model.classification_code = item.classification_code

                await record_match_result(session, item_model.id, match_result)
                processed_item_ids.append(item_model.id)

                item_desc = f"{item.family} / {item.type_name}"

                # Map decision to display status
                from bimcalc.models import MatchDecision
                if match_result.decision == MatchDecision.AUTO_ACCEPTED:
                    status = "AUTO"
                    auto_accepted += 1
                    if "instant" in match_result.reason.lower():
                        instant_match += 1
                elif match_result.decision == MatchDecision.MANUAL_REVIEW:
                    status = "REVIEW"
                    manual_review += 1
                else:  # REJECTED
                    status = "REJECTED"
                    manual_review += 1

                confidence = f"{match_result.confidence_score:.0f}"
                flags_str = (
                    ", ".join(flag.type for flag in match_result.flags)
                    if match_result.flags
                    else "None"
                )

                table.add_row(item_desc, status, confidence, flags_str)

            console.print(table)
            console.print("\n[bold]Summary:[/bold]")
            console.print(f"  Auto-accepted: {auto_accepted}")
            console.print(f"  Instant matches: {instant_match}")
            console.print(f"  Manual review: {manual_review}")

            if processed_item_ids:
                persisted = await session.execute(
                    select(func.count())
                    .select_from(MatchResultModel)
                    .where(
                        MatchResultModel.item_id.in_(processed_item_ids),
                        MatchResultModel.timestamp >= run_started,
                    )
                )
                console.print(
                    f"  Match results persisted: {persisted.scalar_one()}"
                )

    asyncio.run(_match())


@review_cli.command("ui")
def review_ui_cmd(
    org_id: str | None = typer.Option(None, "--org", help="Organization ID"),
    project_id: str | None = typer.Option(None, "--project", help="Project ID"),
    reviewer: str | None = typer.Option(
        None, "--user", "--by", help="Reviewer name/email for audit trail"
    ),
):
    """Launch interactive review UI."""
    config = get_config()
    org_val = org_id or config.org_id
    project_val = project_id or "default"
    reviewer_val = reviewer or "review-ui"

    try:
        from bimcalc.ui.review_app import run_review_ui  # Local import to avoid heavy deps
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise typer.BadParameter(
            "textual is required for the review UI. Install with 'pip install textual'."
        ) from exc

    run_review_ui(org_val, project_val, reviewer_val)


@web_cli.command("serve")
def web_serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind"),
    port: int = typer.Option(8001, help="Port to bind"),
    reload: bool = typer.Option(False, help="Enable autoreload (dev only)"),
):
    """Run FastAPI-powered web UI (Enhanced version with full features)."""
    import uvicorn

    typer.echo(f"Starting enhanced web UI on http://{host}:{port}")
    uvicorn.run("bimcalc.web.app_enhanced:app", host=host, port=port, reload=reload, workers=1)


@app.command()
def report(
    org_id: str | None = typer.Option(None, "--org", help="Organization ID"),
    project_id: str | None = typer.Option(None, "--project", help="Project ID"),
    as_of: str | None = typer.Option(None, "--as-of", help="As-of timestamp (ISO format)"),
    output: Path | None = typer.Option(None, "--out", "-o", help="Output CSV file"),
):
    """Generate cost report with as-of temporal query."""
    config = get_config()
    org_id = org_id or config.org_id
    project_id = project_id or "default"

    as_of_dt = None
    if as_of:
        as_of_dt = datetime.fromisoformat(as_of)
    else:
        as_of_dt = datetime.utcnow()

    console.print(f"[bold]Generating report:[/bold] org={org_id}, project={project_id}")
    console.print(f"As-of: {as_of_dt.isoformat()}")

    async def _report():
        async with get_session() as session:
            df = await generate_report(session, org_id, project_id, as_of_dt)

            if df.empty:
                console.print("[yellow]No data found for report[/yellow]")
                return

            # Display summary
            total_items = len(df)
            matched_items = df["sku"].notna().sum()
            total_net = df["total_net"].sum()
            total_gross = df["total_gross"].sum()

            console.print("\n[bold]Report Summary:[/bold]")
            console.print(f"  Total items: {total_items}")
            console.print(f"  Matched items: {matched_items}")
            console.print(f"  Total net: €{total_net:,.2f}")
            console.print(f"  Total gross: €{total_gross:,.2f}")

            # Save to CSV if requested
            if output:
                df.to_csv(output, index=False)
                console.print(f"\n[green]✓[/green] Report saved to: {output}")
            else:
                # Display first 10 rows
                console.print("\n[bold]Preview (first 10 rows):[/bold]")
                console.print(df.head(10).to_string())

    asyncio.run(_report())


@app.command()
def stats(
    org_id: str | None = typer.Option(None, "--org", help="Organization ID"),
    project_id: str | None = typer.Option(None, "--project", help="Project ID"),
):
    """Show project statistics."""
    config = get_config()
    org_id = org_id or config.org_id
    project_id = project_id or "default"

    console.print(f"[bold]Project Statistics:[/bold] org={org_id}, project={project_id}")

    async def _stats():
        async with get_session() as session:
            # Count items
            items_result = await session.execute(
                select(ItemModel).where(
                    ItemModel.org_id == org_id,
                    ItemModel.project_id == project_id,
                )
            )
            items_count = len(items_result.scalars().all())

            # Count price items
            prices_result = await session.execute(select(PriceItemModel))
            prices_count = len(prices_result.scalars().all())

            # Count mappings (active)
            mappings_result = await session.execute(
                select(ItemMappingModel).where(
                    ItemMappingModel.org_id == org_id,
                    ItemMappingModel.end_ts.is_(None),
                )
            )
            mappings_count = len(mappings_result.scalars().all())

            table = Table(title="Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Count", justify="right", style="green")

            table.add_row("Revit Items", str(items_count))
            table.add_row("Price Items", str(prices_count))
            table.add_row("Active Mappings", str(mappings_count))

            console.print(table)

    asyncio.run(_stats())


@app.command()
def migrate(
    execute: bool = typer.Option(False, "--execute", help="Execute migration (default: dry-run)"),
    rollback: bool = typer.Option(False, "--rollback", help="Rollback migration (DESTRUCTIVE)"),
):
    """Run database migration to SCD Type-2 schema."""
    from bimcalc.migrations.upgrade_to_scd2 import migrate as run_migration

    run_migration(execute=execute, rollback=rollback)


@app.command(name="sync-crail4")
def sync_crail4_command(
    org_id: str = typer.Option("acme-construction", "--org", help="Organization ID"),
    target_scheme: str = typer.Option("UniClass2015", "--scheme", help="Target classification scheme"),
    full_sync: bool = typer.Option(False, "--full-sync", help="Ignore delta window and fetch all data"),
    classifications: str | None = typer.Option(
        None, "--classifications", help="Comma-separated classification codes to filter"
    ),
    region: str | None = typer.Option(None, "--region", help="Region filter (e.g., UK, IE)"),
):
    """Trigger Crail4 AI price synchronization."""
    from bimcalc.integration.crail4_sync import sync_crail4_prices

    delta_days = None if full_sync else 7
    class_filter = None
    if classifications:
        class_filter = [code.strip() for code in classifications.split(",") if code.strip()]

    console.print(
        f"[bold]Crail4 Sync:[/bold] org={org_id}, delta_days={delta_days}, target_scheme={target_scheme}"
    )

    async def _sync():
        try:
            result = await sync_crail4_prices(
                org_id=org_id,
                target_scheme=target_scheme,
                delta_days=delta_days,
                classification_filter=class_filter,
                region=region,
            )
            console.print(f"Status: {result.get('status')}")
            console.print(f"Items loaded: {result.get('items_loaded', 0)}")
            if rejection := result.get("transform_rejections"):
                console.print(f"Transform rejections: {rejection}")
            if errors := result.get("errors"):
                console.print(f"[yellow]Errors:[/yellow] {errors}")
        except Exception as exc:
            console.print(f"[red]Crail4 sync failed: {exc}[/red]")
            raise

    asyncio.run(_sync())


@app.command(name="import-csv-prices")
def import_csv_prices_command(
    file_path: Path = typer.Argument(..., help="Path to CSV or Excel file"),
    org_id: str = typer.Option("acme-construction", "--org", help="Organization ID"),
    vendor: str = typer.Option(..., "--vendor", help="Vendor/supplier name (e.g., CEF, Rexel)"),
    sheet_name: str | None = typer.Option(None, "--sheet", help="Sheet name for Excel files"),
):
    """Import supplier price list from CSV or Excel file.

    Example:
        bimcalc import-csv-prices data/prices/cef_pricelist.xlsx --vendor CEF --sheet "Cable Management"
    """
    from bimcalc.integration.csv_price_importer import import_supplier_pricelist

    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Importing CSV Prices:[/bold] {file_path}")
    console.print(f"Vendor: {vendor}, Org: {org_id}")

    async def _import():
        try:
            result = await import_supplier_pricelist(
                file_path=str(file_path),
                org_id=org_id,
                vendor_name=vendor,
                sheet_name=sheet_name,
            )

            # Display results
            console.print("\n[green]✓ Import completed successfully[/green]")
            console.print(f"Run ID: {result['run_id']}")
            console.print(f"Items received: {result['items_received']}")
            console.print(f"Items loaded: {result['items_loaded']}")
            console.print(f"Items rejected: {result['items_rejected']}")

            if result['rejection_reasons']:
                console.print("\n[yellow]Rejection reasons:[/yellow]")
                for reason, count in result['rejection_reasons'].items():
                    console.print(f"  {reason}: {count}")

        except Exception as exc:
            console.print(f"[red]CSV import failed: {exc}[/red]")
            raise

    asyncio.run(_import())


@app.command(name="sync-prices")
def sync_prices_cmd(
    config_file: Path = typer.Option(
        Path("config/pipeline_sources.yaml"),
        "--config",
        "-c",
        help="Pipeline configuration file",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate run without writing to database"),
):
    """Run automated price synchronization pipeline.

    Executes the nightly price data refresh from all configured sources.
    Each source is processed independently - failures are isolated and logged.
    """
    from bimcalc.pipeline.config_loader import load_pipeline_config
    from bimcalc.pipeline.orchestrator import run_pipeline

    console.print("[bold]Starting price synchronization pipeline[/bold]")
    console.print(f"Config: {config_file}")

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

    async def _sync():
        try:
            # Load importer configurations
            importers = load_pipeline_config(config_file)

            if not importers:
                console.print("[yellow]No importers configured or all disabled[/yellow]")
                return

            console.print(f"Loaded {len(importers)} data sources\n")

            # Run pipeline
            summary = await run_pipeline(importers)

            # Display results
            console.print("\n[bold]Pipeline Run Summary[/bold]")
            console.print(f"Run timestamp: {summary['run_timestamp']}")
            console.print(
                f"Status: {summary['successful_sources']}/{summary['total_sources']} sources successful"
            )

            # Results table
            table = Table(title="Source Results")
            table.add_column("Source", style="cyan")
            table.add_column("Status", style="bold")
            table.add_column("Inserted", justify="right")
            table.add_column("Updated", justify="right")
            table.add_column("Failed", justify="right")
            table.add_column("Duration", justify="right")

            for result in summary["results"]:
                status_style = "green" if result.success else "red"
                status_text = f"[{status_style}]{result.status.value}[/{status_style}]"

                table.add_row(
                    result.source_name,
                    status_text,
                    str(result.records_inserted),
                    str(result.records_updated),
                    str(result.records_failed),
                    f"{result.duration_seconds:.1f}s",
                )

            console.print("\n")
            console.print(table)

            # Show error messages
            if summary["failed_sources"] > 0:
                console.print("\n[bold red]Failed Sources:[/bold red]")
                for result in summary["results"]:
                    if not result.success:
                        console.print(f"  • {result.source_name}: {result.message}")

        except FileNotFoundError as e:
            console.print(f"[red]Config file not found: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Pipeline error: {e}[/red]")
            import traceback

            traceback.print_exc()

    asyncio.run(_sync())


@app.command(name="pipeline-status")
def pipeline_status_cmd(
    last_n: int = typer.Option(5, "--last", "-n", help="Show last N pipeline runs"),
):
    """Check status of recent pipeline runs."""
    from bimcalc.db.models import DataSyncLogModel

    console.print(f"[bold]Last {last_n} Pipeline Runs[/bold]\n")

    async def _status():
        async with get_session() as session:
            # Get recent runs
            stmt = (
                select(DataSyncLogModel)
                .order_by(DataSyncLogModel.run_timestamp.desc())
                .limit(last_n * 10)  # Get more rows, we'll group by run_timestamp
            )

            result = await session.execute(stmt)
            logs = result.scalars().all()

            if not logs:
                console.print("[yellow]No pipeline runs found[/yellow]")
                return

            # Group by run_timestamp
            from collections import defaultdict

            runs = defaultdict(list)
            for log in logs:
                runs[log.run_timestamp].append(log)

            # Take last N runs
            run_timestamps = sorted(runs.keys(), reverse=True)[:last_n]

            for run_ts in run_timestamps:
                run_logs = runs[run_ts]

                # Calculate statistics
                total_sources = len(run_logs)
                successful = sum(1 for log in run_logs if log.status == "SUCCESS")
                failed = sum(1 for log in run_logs if log.status == "FAILED")
                partial = sum(1 for log in run_logs if log.status == "PARTIAL_SUCCESS")

                total_inserted = sum(log.records_inserted for log in run_logs)
                total_updated = sum(log.records_updated for log in run_logs)

                # Overall status
                if failed > 0:
                    overall_status = "[red]FAILED[/red]"
                elif partial > 0:
                    overall_status = "[yellow]PARTIAL[/yellow]"
                else:
                    overall_status = "[green]SUCCESS[/green]"

                console.print(f"\n[bold]{run_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}[/bold]")
                console.print(f"Status: {overall_status}")
                console.print(
                    f"Sources: {successful} success, {failed} failed, {partial} partial"
                )
                console.print(f"Records: {total_inserted} inserted, {total_updated} updated")

                # Show failed sources
                if failed > 0 or partial > 0:
                    console.print("\nIssues:")
                    for log in run_logs:
                        if log.status in ("FAILED", "PARTIAL_SUCCESS"):
                            console.print(f"  • {log.source_name}: {log.message}")

    asyncio.run(_status())


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
