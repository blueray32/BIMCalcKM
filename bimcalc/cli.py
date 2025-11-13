"""BIMCalc CLI - Full implementation with async commands.

Commands:
- init: Initialize database schema
- ingest-schedules: Import Revit schedules (CSV/XLSX)
- ingest-prices: Import vendor price books (CSV/XLSX)
- match: Run matching pipeline on project
- report: Generate cost report with as-of query
- stats: Show project statistics
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select, func

from bimcalc.config import get_config
from bimcalc.db.connection import get_engine, get_session
from bimcalc.db.match_results import record_match_result
from bimcalc.db.models import Base, ItemModel, ItemMappingModel, MatchResultModel, PriceItemModel
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
    org_id: Optional[str] = typer.Option(None, "--org", help="Organization ID"),
    project_id: Optional[str] = typer.Option(None, "--project", help="Project ID"),
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
    org_id: Optional[str] = typer.Option(None, "--org", help="Organization ID"),
    project_id: Optional[str] = typer.Option(None, "--project", help="Project ID"),
    created_by: str = typer.Option("cli", "--by", help="Created by user/system"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit items to match"),
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
            console.print(f"\n[bold]Summary:[/bold]")
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
    org_id: Optional[str] = typer.Option(None, "--org", help="Organization ID"),
    project_id: Optional[str] = typer.Option(None, "--project", help="Project ID"),
    reviewer: Optional[str] = typer.Option(
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
    org_id: Optional[str] = typer.Option(None, "--org", help="Organization ID"),
    project_id: Optional[str] = typer.Option(None, "--project", help="Project ID"),
    as_of: Optional[str] = typer.Option(None, "--as-of", help="As-of timestamp (ISO format)"),
    output: Optional[Path] = typer.Option(None, "--out", "-o", help="Output CSV file"),
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

            console.print(f"\n[bold]Report Summary:[/bold]")
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
    org_id: Optional[str] = typer.Option(None, "--org", help="Organization ID"),
    project_id: Optional[str] = typer.Option(None, "--project", help="Project ID"),
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


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
