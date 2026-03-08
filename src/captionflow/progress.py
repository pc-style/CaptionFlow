"""Progress display and summary reporting."""

from rich.console import Console
from rich.table import Table

from .models import BatchSummary, JobStatus


def print_summary(summary: BatchSummary, console: Console) -> None:
    """Print a batch processing summary table."""
    console.print()

    if summary.total == 1:
        result = summary.results[0]
        if result.status == JobStatus.SUCCESS:
            console.print(f"[green]Done.[/green] {result.input_path.name}")
            for p in result.subtitle_paths:
                console.print(f"  Subtitle: {p}")
            if result.embedded_path:
                console.print(f"  Embedded: {result.embedded_path}")
        elif result.status == JobStatus.SKIPPED:
            console.print(f"[yellow]Skipped:[/yellow] {result.input_path.name} - {result.error}")
        else:
            console.print(f"[red]Failed:[/red] {result.input_path.name} - {result.error}")
        return

    table = Table(title="Batch Summary")
    table.add_column("File", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    for result in summary.results:
        if result.status == JobStatus.SUCCESS:
            status = "[green]OK[/green]"
            details = ", ".join(p.name for p in result.subtitle_paths)
        elif result.status == JobStatus.SKIPPED:
            status = "[yellow]SKIP[/yellow]"
            details = result.error or ""
        else:
            status = "[red]FAIL[/red]"
            details = result.error or ""

        table.add_row(result.input_path.name, status, details)

    console.print(table)
    console.print(
        f"\nTotal: {summary.total}  "
        f"[green]Succeeded: {summary.succeeded}[/green]  "
        f"[red]Failed: {summary.failed}[/red]  "
        f"[yellow]Skipped: {summary.skipped}[/yellow]"
    )
