"""dedupe — remove duplicate rows, by all columns or a chosen subset."""

from __future__ import annotations

from typing import List, Optional

from csvtidy.engine import columns_of, quote_ident


def build_dedupe(
    con,
    source_sql: str,
    subset: Optional[List[str]] = None,
    keep: str = "first",
) -> str:
    """Return SQL that keeps one row per duplicate group, preserving input order.

    ``subset`` limits the comparison to those columns (e.g. dedupe on ``email``);
    by default every column must match. ``keep`` chooses which copy survives:
    ``first`` or ``last`` in input order.
    """
    if keep not in ("first", "last"):
        raise ValueError("keep must be 'first' or 'last'")

    cols = columns_of(con, source_sql)
    keys = subset or cols
    unknown = set(keys) - set(cols)
    if unknown:
        raise ValueError(
            "dedupe: column(s) not found: %s" % ", ".join(sorted(unknown))
        )

    partition = ", ".join(quote_ident(k) for k in keys)
    order = "DESC" if keep == "last" else "ASC"

    numbered = "SELECT *, row_number() OVER () AS _rid FROM (%s)" % source_sql
    picked = (
        "SELECT * FROM (%s) "
        "QUALIFY row_number() OVER (PARTITION BY %s ORDER BY _rid %s) = 1"
        % (numbered, partition, order)
    )
    return "SELECT * EXCLUDE(_rid) FROM (%s) ORDER BY _rid" % picked
