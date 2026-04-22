from __future__ import annotations

import json
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from codemind.core.orchestrator import Orchestrator

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Harness-DB-CodeMind: Enterprise AI Code Intelligence Infrastructure"""
    pass


@main.command()
@click.argument("repo_path")
@click.option("--language", "-l", default="sql", help="Primary language (sql/java/python)")
@click.option("--output", "-o", default="", help="Output file path for results")
def index(repo_path: str, language: str, output: str) -> None:
    """Index a repository and build code graph"""
    console.print(f"[bold blue]Indexing repository:[/] {repo_path}")

    orch = Orchestrator()
    result = orch.index_repository(repo_path, language)

    if result["success"]:
        console.print("[bold green]✓ Indexing completed![/]")
        table = Table(title="Index Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Nodes", str(result["node_count"]))
        table.add_row("Edges", str(result["edge_count"]))
        table.add_row("Token Estimate", str(result["token_estimate"]))
        table.add_row("Neo4j Stored", str(result.get("neo4j_stored", 0)))
        table.add_row("Embedding Indexed", str(result.get("embedding_indexed", 0)))
        table.add_row("Elapsed (ms)", str(result["elapsed_ms"]))
        console.print(table)
    else:
        console.print(f"[bold red]✗ Indexing failed:[/] {result.get('error', 'Unknown error')}")
        sys.exit(1)

    if output:
        with open(output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        console.print(f"Results saved to: {output}")


@main.command()
@click.argument("query_text")
@click.option("--repo", "-r", default="", help="Repository path (will index if needed)")
@click.option("--language", "-l", default="sql", help="Primary language")
@click.option("--budget", "-b", default=0, type=int, help="Token budget")
@click.option("--output", "-o", default="", help="Output file path")
def query(query_text: str, repo: str, language: str, budget: int, output: str) -> None:
    """Query the code intelligence system"""
    orch = Orchestrator()

    if repo:
        console.print(f"[bold blue]Indexing repository:[/] {repo}")
        index_result = orch.index_repository(repo, language)
        if not index_result["success"]:
            console.print(f"[bold red]✗ Indexing failed:[/] {index_result.get('error')}")
            sys.exit(1)
        console.print(f"[green]✓ Indexed {index_result['node_count']} nodes[/]")

    console.print(f"\n[bold blue]Query:[/] {query_text}")
    result = orch.query(query_text, budget)

    if not result["success"]:
        console.print(f"[bold red]✗ Query failed:[/] {result.get('error')}")
        sys.exit(1)

    console.print(f"[bold]Intent:[/] {result.get('intent', 'UNKNOWN')}")
    console.print(f"[bold]Entities:[/] {', '.join(result.get('entities', []))}")
    console.print(f"[bold]Budget Strategy:[/] {result.get('budget_strategy', 'NORMAL')}")

    if "impact" in result:
        impact = result["impact"]
        console.print(Panel(
            f"Total Affected: [bold]{impact.get('total_affected', 0)}[/]\n"
            f"Max Depth: [bold]{impact.get('max_depth', 0)}[/]\n"
            f"Avg Confidence: [bold]{impact.get('avg_confidence', 0):.2f}[/]",
            title="Impact Analysis",
            border_style="yellow",
        ))

        if impact.get("impacts"):
            table = Table(title="Affected Nodes")
            table.add_column("Node", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Depth", style="green")
            table.add_column("Confidence", style="yellow")
            table.add_column("Path", style="dim")
            for imp in impact["impacts"][:20]:
                table.add_row(
                    imp.get("node_name", ""),
                    imp.get("node_type", ""),
                    str(imp.get("depth", "")),
                    f"{imp.get('confidence', 0):.2f}",
                    " → ".join(imp.get("path", [])),
                )
            console.print(table)

    if "risk" in result:
        risk = result["risk"]
        level_color = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red", "CRITICAL": "bold red"}
        color = level_color.get(risk.get("level", ""), "white")
        console.print(Panel(
            f"Score: [{color}]{risk.get('score', 0)}[/{color}]/100\n"
            f"Level: [{color}]{risk.get('level', 'UNKNOWN')}[/{color}]\n"
            f"Factors: {json.dumps(risk.get('factors', {}), indent=2)}",
            title="Risk Assessment",
            border_style="red",
        ))

    if "lineage" in result:
        lineage = result["lineage"]
        console.print(Panel(
            f"Lineage Edges: [bold]{lineage.get('lineage_count', 0)}[/]\n"
            f"Statements: [bold]{lineage.get('statement_count', 0)}[/]",
            title="Data Lineage",
            border_style="blue",
        ))

        if lineage.get("lineage_edges"):
            table = Table(title="Lineage Edges")
            table.add_column("Source", style="cyan")
            table.add_column("Target", style="green")
            table.add_column("Transform", style="yellow")
            table.add_column("Via", style="magenta")
            for le in lineage["lineage_edges"][:20]:
                table.add_row(
                    le.get("source", ""),
                    le.get("target", ""),
                    le.get("transformation", ""),
                    le.get("via", ""),
                )
            console.print(table)

    if "explanation" in result:
        console.print(Panel(
            result["explanation"],
            title="AI Explanation",
            border_style="green",
        ))

    console.print(f"\n[dim]Elapsed: {result.get('elapsed_ms', 0):.2f}ms[/]")

    if output:
        with open(output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        console.print(f"Results saved to: {output}")


@main.command()
@click.argument("repo_path")
@click.option("--language", "-l", default="sql", help="Primary language")
def stats(repo_path: str, language: str) -> None:
    """Show graph statistics"""
    orch = Orchestrator()
    result = orch.index_repository(repo_path, language)

    if not result["success"]:
        console.print(f"[bold red]✗ Failed:[/] {result.get('error')}")
        sys.exit(1)

    stats = orch.get_graph_stats()

    table = Table(title="Graph Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total Nodes", str(stats.get("node_count", 0)))
    table.add_row("Total Edges", str(stats.get("edge_count", 0)))
    table.add_row("Token Estimate", str(stats.get("token_estimate", 0)))

    for ntype, count in stats.get("node_types", {}).items():
        table.add_row(f"  Node: {ntype}", str(count))

    for etype, count in stats.get("edge_types", {}).items():
        table.add_row(f"  Edge: {etype}", str(count))

    console.print(table)


@main.command()
@click.option("--host", default="0.0.0.0", help="Server host")
@click.option("--port", default=8000, type=int, help="Server port")
def serve(host: str, port: int) -> None:
    """Start the API server"""
    console.print(f"[bold green]Starting server at http://{host}:{port}[/]")
    import uvicorn
    uvicorn.run("codemind.api.server:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
