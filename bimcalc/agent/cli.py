"""BIMCalc Agent CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown

from bimcalc.agent.rag import RAGService
from bimcalc.db.connection import get_session

agent_cli = typer.Typer(help="BIMCalc RAG Agent")
console = Console()


@agent_cli.command("ingest")
def ingest_cmd(
    file_path: Path = typer.Argument(..., help="Path to text/markdown file"),
    title: str | None = typer.Option(None, help="Document title (defaults to filename)"),
    doc_type: str = typer.Option("general", help="Document type (e.g., guide, adr, prp)"),
):
    """Ingest a document into the knowledge base."""
    if not file_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    doc_title = title or file_path.stem
    content = file_path.read_text(encoding="utf-8")

    async def _ingest():
        async with get_session() as session:
            service = RAGService(session)
            console.print(f"Ingesting [bold]{doc_title}[/bold]...")
            doc = await service.ingest_document(
                title=doc_title,
                content=content,
                doc_type=doc_type,
                source_file=str(file_path),
            )
            console.print(f"[green]✓ Ingested document ID: {doc.id}[/green]")

    asyncio.run(_ingest())


@agent_cli.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(5, help="Number of results"),
):
    """Search the knowledge base."""
    async def _search():
        async with get_session() as session:
            service = RAGService(session)
            results = await service.search(query, limit=limit)
            
            if not results:
                console.print("[yellow]No results found.[/yellow]")
                return

            console.print(f"[bold]Found {len(results)} results:[/bold]\n")
            for i, doc in enumerate(results, 1):
                console.print(f"{i}. [bold cyan]{doc.title}[/bold cyan] ({doc.doc_type})")
                console.print(f"   {doc.content[:150]}...")
                console.print()

    asyncio.run(_search())


@agent_cli.command("chat")
def chat_cmd():
    """Interactive chat with the agent."""
    console.print("[bold green]BIMCalc Agent[/bold green] (type 'exit' to quit)")
    
    async def _chat_loop():
        async with get_session() as session:
            service = RAGService(session)
            
            while True:
                query = typer.prompt("You")
                if query.lower() in ("exit", "quit"):
                    break
                
                response = await service.chat(query)
                console.print("\n[bold blue]Agent:[/bold blue]")
                console.print(Markdown(response))
                console.print()

    asyncio.run(_chat_loop())
