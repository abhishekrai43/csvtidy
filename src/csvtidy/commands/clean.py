"""clean — whitespace, dates, and empty-row primitives.

Cleaning is non-destructive: dates that can't be parsed keep their original text,
so you never lose data to a format csvtidy didn't recognize.
"""

from __future__ import annotations

from typing import List, Optional

from csvtidy.engine import columns_of, date_expr, quote_ident


def build_clean(
    con,
    source_sql: str,
    trim: bool = True,
    drop_empty_rows: bool = True,
    collapse_spaces: bool = False,
    fix_dates: Optional[List[str]] = None,
    date_format: str = "%Y-%m-%d",
    dayfirst: bool = False,
    ignore_columns: Optional[List[str]] = None,
) -> str:
    """Wrap ``source_sql`` with the requested cleanup steps and return new SQL.

    ``ignore_columns`` are excluded from the empty-row test, so csvtidy-added
    metadata (like a merge ``source_column``) doesn't keep an otherwise-blank
    row alive.
    """
    cols = columns_of(con, source_sql)
    date_cols = set(fix_dates or [])
    unknown = date_cols - set(cols)
    if unknown:
        raise ValueError(
            "fix-dates: column(s) not found: %s" % ", ".join(sorted(unknown))
        )
    ignored = set(ignore_columns or [])

    exprs = []
    for col in cols:
        ident = quote_ident(col)
        expr = ident
        if trim:
            expr = "trim(%s)" % expr
        if collapse_spaces:
            expr = "regexp_replace(%s, '\\s+', ' ', 'g')" % expr
        if col in date_cols:
            expr = date_expr(expr, date_format, dayfirst)
        if expr != ident:
            expr = "%s AS %s" % (expr, ident)
        exprs.append(expr)

    sql = "SELECT %s FROM (%s)" % (", ".join(exprs), source_sql)

    if drop_empty_rows:
        checked = [c for c in cols if c not in ignored] or cols
        conds = " OR ".join(
            "coalesce(trim(%s), '') <> ''" % quote_ident(c) for c in checked
        )
        sql = "SELECT * FROM (%s) WHERE %s" % (sql, conds)

    return sql
