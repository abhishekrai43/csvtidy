"""Command-line interface for csvtidy."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from csvtidy import __version__
from csvtidy.commands.clean import build_clean
from csvtidy.commands.dedupe import build_dedupe
from csvtidy.engine import connect, read_sql, write_output
from csvtidy.recipe import build_recipe_sql, load_recipe

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Clean and merge messy CSV files — offline, big-file capable, recipe-driven.",
)

# Status/progress goes to stderr so stdout stays a clean, pipeable CSV stream.
err = Console(stderr=True)


def _split(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def _version_cb(show: bool) -> None:
    if show:
        typer.echo("csvtidy %s" % __version__)
        raise typer.Exit()


@app.callback()
def _main(
    _version: bool = typer.Option(
        False, "--version", callback=_version_cb, is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    pass


@app.command()
def merge(
    inputs: List[str] = typer.Argument(
        ..., help="CSV files, folders, or globs to combine."
    ),
    output: Optional[str] = typer.Option(
        None, "-o", "--output",
        help="Write to this CSV (streamed). Omit to print to stdout.",
    ),
    source_column: Optional[str] = typer.Option(
        None, "--source-column",
        help="Add a column with each row's source file name.",
    ),
    pattern: str = typer.Option(
        "*.csv", "--pattern", help="Glob used when an input is a folder."
    ),
    recursive: bool = typer.Option(
        False, "-r", "--recursive", help="Recurse into sub-folders."
    ),
) -> None:
    """Combine many CSVs (or a whole folder) into one.

    Per-file headers are consumed as headers, not repeated as rows, and columns
    are aligned by name so files with mismatched columns merge cleanly (missing
    cells become empty).
    """
    con = connect()
    sql = read_sql(con, inputs, pattern, recursive, source_column)
    rows = write_output(con, sql, output)
    _report("Merged", rows, output)


@app.command()
def dedupe(
    input: str = typer.Argument(..., help="CSV file or glob to de-duplicate."),
    output: Optional[str] = typer.Option(
        None, "-o", "--output", help="Write to this CSV. Omit for stdout."
    ),
    subset: Optional[str] = typer.Option(
        None, "--subset",
        help="Comma-separated columns to match on (default: all columns).",
    ),
    keep: str = typer.Option(
        "first", "--keep", help="Which duplicate to keep: first or last."
    ),
) -> None:
    """Remove duplicate rows, keeping input order."""
    con = connect()
    src = read_sql(con, [input])
    before = con.execute("SELECT count(*) FROM (%s)" % src).fetchone()[0]
    sql = build_dedupe(con, src, subset=_split(subset), keep=keep)
    rows = write_output(con, sql, output)
    _report("Kept", rows, output, extra="removed %d duplicate(s)" % (before - rows))


@app.command()
def clean(
    input: str = typer.Argument(..., help="CSV file or glob to clean."),
    output: Optional[str] = typer.Option(
        None, "-o", "--output", help="Write to this CSV. Omit for stdout."
    ),
    trim: bool = typer.Option(True, "--trim/--no-trim", help="Trim whitespace."),
    drop_empty_rows: bool = typer.Option(
        True, "--drop-empty-rows/--keep-empty-rows",
        help="Drop rows where every cell is blank.",
    ),
    collapse_spaces: bool = typer.Option(
        False, "--collapse-spaces",
        help="Collapse runs of whitespace inside cells to a single space.",
    ),
    fix_dates: Optional[str] = typer.Option(
        None, "--fix-dates",
        help="Comma-separated columns to normalize to a single date format.",
    ),
    date_format: str = typer.Option(
        "%Y-%m-%d", "--date-format", help="Output format for --fix-dates."
    ),
    dayfirst: bool = typer.Option(
        False, "--dayfirst",
        help="Read ambiguous dates as day/month (e.g. 03/04 = 3 April).",
    ),
) -> None:
    """Apply cleanup primitives: trim, normalize dates, drop empty rows."""
    con = connect()
    src = read_sql(con, [input])
    sql = build_clean(
        con, src,
        trim=trim,
        drop_empty_rows=drop_empty_rows,
        collapse_spaces=collapse_spaces,
        fix_dates=_split(fix_dates),
        date_format=date_format,
        dayfirst=dayfirst,
    )
    rows = write_output(con, sql, output)
    _report("Cleaned", rows, output)


@app.command()
def run(
    recipe: str = typer.Argument(..., help="Path to a recipe YAML file."),
    output: Optional[str] = typer.Option(
        None, "-o", "--output",
        help="Override the recipe's output path.",
    ),
) -> None:
    """Run a saved recipe — a reusable sequence of steps from a YAML file."""
    con = connect()
    spec = load_recipe(recipe)
    sql, recipe_output = build_recipe_sql(con, spec)
    target = output or recipe_output
    rows = write_output(con, sql, target)
    _report("Recipe wrote", rows, target)


def _report(verb: str, rows: int, output: Optional[str], extra: str = "") -> None:
    where = output if (output and output != "-") else "stdout"
    tail = " (%s)" % extra if extra else ""
    err.print("[green]%s[/green] %s row(s) -> %s%s" % (verb, f"{rows:,}", where, tail))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
