"""Thin CLI over the Python research API."""

import asyncio
from pathlib import Path

import typer

from polyscout.config import Settings
from polyscout.planner import research as run_research


app = typer.Typer(no_args_is_help=True, help="Research across sources with auditable evidence.")


@app.callback()
def main():
    """PolyScout: BYOK research. No hosted quota or account automation."""


@app.command()
def research(
    question: str = typer.Argument(..., help="Research question."),
    output: Path = typer.Option(Path("runs"), "--output", "-o", help="Parent directory for a new run."),
    max_rounds: int = typer.Option(2, min=1, max=2, help="Bound planning/retrieval rounds."),
):
    """Create evidence.jsonl, report.md, raw excerpts and run.json."""
    try:
        result = asyncio.run(run_research(question, Settings.from_env(), output, max_rounds=max_rounds))
    except ValueError as exc:
        typer.echo(f"Configuration/input error: {exc}", err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("Cancelled; completed observations are retained in the run directory.", err=True)
        raise typer.Exit(130) from None
    except Exception:
        typer.echo("Research failed. Inspect the run artifacts, if created; sensitive error bodies are omitted.", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Run: {result.run_dir}\nStatus: {result.status}\nHTTP attempts: {result.requests}")


if __name__ == "__main__":
    app()
