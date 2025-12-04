"""Project management CLI commands."""

import asyncio
import json
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel, LaborRateOverride

project_cli = typer.Typer(help="Manage projects and settings")
console = Console()


@project_cli.command("list")
def list_projects():
    """List all projects."""

    async def _list():
        async with get_session() as session:
            result = await session.execute(
                select(ProjectModel).order_by(ProjectModel.created_at.desc())
            )
            projects = result.scalars().all()

            table = Table(title="Projects")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="green")
            table.add_column("Project ID", style="magenta")
            table.add_column("Region")
            table.add_column("Status")

            for p in projects:
                table.add_row(
                    str(p.id), p.display_name, p.project_id, p.region, p.status
                )

            console.print(table)

    asyncio.run(_list())


@project_cli.command("settings")
def get_settings(project_id: str):
    """Get settings for a project."""

    async def _get():
        try:
            p_uuid = UUID(project_id)
        except ValueError:
            console.print(f"[red]Invalid project UUID: {project_id}[/red]")
            return

        async with get_session() as session:
            result = await session.execute(
                select(ProjectModel).where(ProjectModel.id == p_uuid)
            )
            project = result.scalar_one_or_none()

            if not project:
                console.print(f"[red]Project not found: {project_id}[/red]")
                return

            console.print(f"[bold]Settings for {project.display_name}:[/bold]")
            console.print_json(data=project.settings)

    asyncio.run(_get())


@project_cli.command("update-settings")
def update_settings(
    project_id: str,
    key: str = typer.Option(..., help="Setting key (e.g. blended_labor_rate)"),
    value: str = typer.Option(..., help="Setting value"),
    is_json: bool = typer.Option(False, help="Parse value as JSON"),
):
    """Update a specific project setting."""

    async def _update():
        try:
            p_uuid = UUID(project_id)
        except ValueError:
            console.print(f"[red]Invalid project UUID: {project_id}[/red]")
            return

        # Parse value
        parsed_value = value
        if is_json:
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                console.print(f"[red]Invalid JSON value: {value}[/red]")
                return
        else:
            # Try to infer type
            if value.lower() == "true":
                parsed_value = True
            elif value.lower() == "false":
                parsed_value = False
            else:
                try:
                    parsed_value = float(value)
                    if parsed_value.is_integer():
                        parsed_value = int(parsed_value)
                except ValueError:
                    pass  # Keep as string

        async with get_session() as session:
            result = await session.execute(
                select(ProjectModel).where(ProjectModel.id == p_uuid)
            )
            project = result.scalar_one_or_none()

            if not project:
                console.print(f"[red]Project not found: {project_id}[/red]")
                return

            current_settings = dict(project.settings)
            current_settings[key] = parsed_value
            project.settings = current_settings

            await session.commit()
            console.print(f"[green]Updated {key} to {parsed_value}[/green]")

    asyncio.run(_update())


@project_cli.command("list-rates")
def list_labor_rates(project_id: str):
    """List labor rate overrides."""

    async def _list():
        try:
            p_uuid = UUID(project_id)
        except ValueError:
            console.print(f"[red]Invalid project UUID: {project_id}[/red]")
            return

        async with get_session() as session:
            result = await session.execute(
                select(LaborRateOverride).where(LaborRateOverride.project_id == p_uuid)
            )
            rates = result.scalars().all()

            if not rates:
                console.print("[yellow]No labor rate overrides found.[/yellow]")
                return

            table = Table(title="Labor Rate Overrides")
            table.add_column("Category", style="cyan")
            table.add_column("Rate", style="green")

            for r in rates:
                table.add_row(r.category, f"{r.rate:.2f}")

            console.print(table)

    asyncio.run(_list())


@project_cli.command("set-rate")
def set_labor_rate(
    project_id: str,
    category: str = typer.Option(..., help="Category name"),
    rate: float = typer.Option(..., help="Labor rate"),
):
    """Set labor rate override for a category."""

    async def _set():
        try:
            p_uuid = UUID(project_id)
        except ValueError:
            console.print(f"[red]Invalid project UUID: {project_id}[/red]")
            return

        async with get_session() as session:
            # Check existing
            result = await session.execute(
                select(LaborRateOverride).where(
                    LaborRateOverride.project_id == p_uuid,
                    LaborRateOverride.category == category,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.rate = rate
                console.print(f"[green]Updated rate for {category} to {rate}[/green]")
            else:
                override = LaborRateOverride(
                    project_id=p_uuid, category=category, rate=rate
                )
                session.add(override)
                console.print(f"[green]Created rate for {category}: {rate}[/green]")

            await session.commit()

    asyncio.run(_set())
