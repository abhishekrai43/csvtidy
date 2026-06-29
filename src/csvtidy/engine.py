"""Shared DuckDB engine: connection, SQL helpers, and the CSV read/write core.

Every command builds a SQL string and hands it to DuckDB, which streams the work
and spills to disk when needed — so csvtidy can process files larger than RAM.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import duckdb


def connect() -> "duckdb.DuckDBPyConnection":
    """Open an in-memory DuckDB connection configured for large CSV work."""
    con = duckdb.connect()
    # Let DuckDB spill intermediates to a temp dir so big jobs don't OOM.
    try:
        con.execute("PRAGMA temp_directory='%s'" % _temp_dir())
    except duckdb.Error:
        pass
    return con


def _temp_dir() -> str:
    base = Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or ".")
    return str(base / ".csvtidy-tmp")


# --- SQL string helpers ----------------------------------------------------

def sql_str(value: str) -> str:
    """Quote a string as a SQL literal, escaping single quotes."""
    return "'" + str(value).replace("'", "''") + "'"


def quote_ident(name: str) -> str:
    """Quote an identifier (column name), escaping embedded double quotes."""
    return '"' + str(name).replace('"', '""') + '"'


def columns_of(con, sql: str) -> List[str]:
    """Return the column names produced by a SELECT statement."""
    rows = con.execute("DESCRIBE " + sql).fetchall()
    return [r[0] for r in rows]


# --- Reading CSV inputs ----------------------------------------------------

def expand_inputs(inputs: Sequence[str], pattern: str, recursive: bool) -> List[str]:
    """Turn a mix of files, folders, and globs into glob strings DuckDB can read.

    Folders become ``folder/<pattern>`` (or ``folder/**/<pattern>`` when recursive).
    Files and explicit globs are passed straight through.
    """
    out: List[str] = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            glob = ("**/" + pattern) if recursive else pattern
            out.append(str(p / glob))
        else:
            out.append(str(raw))
    if not out:
        raise ValueError("no input files given")
    return out


def read_sql(
    con,
    inputs: Sequence[str],
    pattern: str = "*.csv",
    recursive: bool = False,
    source_column: Optional[str] = None,
) -> str:
    """Build a SELECT that reads one or many CSVs as a single, aligned table.

    Columns are read as text (``all_varchar``) so values are never silently
    retyped, and ``union_by_name`` aligns mismatched columns across files,
    filling gaps with NULL. Per-file headers are consumed as headers, not data,
    so merging many files never repeats the header row.

    A single ``-`` reads CSV from stdin. Stdin is materialized into a temp table
    so it can be read more than once (e.g. for both a count and the output).
    """
    if any(i == "-" for i in inputs):
        return _read_stdin_sql(con, source_column)

    files = expand_inputs(inputs, pattern, recursive)
    array = "[" + ", ".join(sql_str(f) for f in files) + "]"
    want_filename = "true" if source_column else "false"
    base = (
        "read_csv_auto(%s, header=true, all_varchar=true, "
        "union_by_name=true, filename=%s)" % (array, want_filename)
    )
    if source_column:
        select = "* EXCLUDE(filename), parse_filename(filename) AS %s" % quote_ident(
            source_column
        )
    else:
        select = "*"
    return "SELECT %s FROM %s" % (select, base)


def _read_stdin_sql(con, source_column: Optional[str]) -> str:
    """Load piped CSV into a temp table and return a SELECT over it."""
    con.execute(
        "CREATE OR REPLACE TEMP TABLE _csvtidy_stdin AS "
        "SELECT * FROM read_csv_auto('/dev/stdin', header=true, all_varchar=true)"
    )
    if source_column:
        return "SELECT *, 'stdin' AS %s FROM _csvtidy_stdin" % quote_ident(
            source_column
        )
    return "SELECT * FROM _csvtidy_stdin"


# --- Date normalization ----------------------------------------------------

def date_formats(dayfirst: bool = False) -> List[str]:
    """Common messy date layouts, tried in order by ``try_strptime``."""
    iso = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]
    dmy = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"]
    mdy = ["%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y", "%m/%d/%y", "%m-%d-%y"]
    words = [
        "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y",
        "%d-%b-%Y", "%b %d, %Y", "%B %d, %Y",
    ]
    stamps = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"]
    ordered = iso + (dmy + mdy if dayfirst else mdy + dmy) + words + stamps
    return ordered


def date_expr(inner: str, out_format: str, dayfirst: bool) -> str:
    """Wrap an expression so recognized dates are reformatted, others untouched."""
    fmts = "[" + ", ".join(sql_str(f) for f in date_formats(dayfirst)) + "]"
    parsed = "try_strptime(%s, %s)" % (inner, fmts)
    return "coalesce(strftime(%s, %s), %s)" % (parsed, sql_str(out_format), inner)


# --- Writing output --------------------------------------------------------

def count_rows(con, sql: str) -> int:
    return con.execute("SELECT count(*) FROM (%s)" % sql).fetchone()[0]


def write_output(con, sql: str, output: Optional[str]) -> int:
    """Write a SELECT to a CSV file (streamed) or to stdout. Returns row count.

    When ``output`` is a path, DuckDB streams the COPY straight to disk so the
    job never has to fit in memory. With no output (or ``-``) rows go to stdout.
    """
    if output and output != "-":
        res = con.execute(
            "COPY (%s) TO %s (FORMAT CSV, HEADER)" % (sql, sql_str(output))
        )
        row = res.fetchone()
        return int(row[0]) if row else count_rows(con, sql)

    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    writer = csv.writer(sys.stdout)
    writer.writerow(cols)
    n = 0
    for batch in _iter_batches(cur):
        for row in batch:
            writer.writerow(["" if v is None else v for v in row])
            n += 1
    return n


def _iter_batches(cur, size: int = 10000) -> Iterable[list]:
    while True:
        rows = cur.fetchmany(size)
        if not rows:
            break
        yield rows
