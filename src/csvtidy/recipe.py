"""Recipe runner — build a cleanup once, replay it on any file or folder.

A recipe is a small YAML file describing where to read, an ordered list of
steps, and where to write. Steps are composed into a single DuckDB query, so
running a recipe keeps the same larger-than-RAM streaming as the raw commands.

Example
-------
    input: ./exports/*.csv
    output: customers.clean.csv
    source_column: source_file
    steps:
      - clean:
          trim: true
          drop_empty_rows: true
          fix_dates: [signup_date]
      - dedupe:
          subset: [email]
          keep: first
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from csvtidy.commands.clean import build_clean
from csvtidy.commands.dedupe import build_dedupe
from csvtidy.engine import read_sql

STEP_BUILDERS = {
    "clean": build_clean,
    "dedupe": build_dedupe,
}


class RecipeError(ValueError):
    """Raised when a recipe file is malformed."""


def load_recipe(path: str) -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise RecipeError("recipe must be a YAML mapping")
    if "input" not in data:
        raise RecipeError("recipe is missing required key: input")
    return data


def build_recipe_sql(con, recipe: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Compose a recipe into one SQL statement. Returns (sql, output_path)."""
    inputs = recipe["input"]
    if isinstance(inputs, str):
        inputs = [inputs]

    sql = read_sql(
        con,
        inputs,
        pattern=recipe.get("pattern", "*.csv"),
        recursive=bool(recipe.get("recursive", False)),
        source_column=recipe.get("source_column"),
    )

    source_column = recipe.get("source_column")
    for step in recipe.get("steps", []) or []:
        sql = _apply_step(con, sql, step, source_column)

    return sql, recipe.get("output")


def _apply_step(con, sql: str, step: Any, source_column: Optional[str] = None) -> str:
    if not isinstance(step, dict) or len(step) != 1:
        raise RecipeError(
            "each step must be a mapping with a single command key "
            "(clean or dedupe)"
        )
    (name, opts), = step.items()
    builder = STEP_BUILDERS.get(name)
    if builder is None:
        raise RecipeError(
            "unknown step '%s' (expected one of: %s)"
            % (name, ", ".join(sorted(STEP_BUILDERS)))
        )
    opts = opts or {}
    if not isinstance(opts, dict):
        raise RecipeError("options for step '%s' must be a mapping" % name)
    # A merge source_column is csvtidy-added metadata; don't let it keep an
    # otherwise-empty row alive when a clean step drops empty rows.
    if name == "clean" and source_column and "ignore_columns" not in opts:
        opts = {**opts, "ignore_columns": [source_column]}
    return builder(con, sql, **opts)


def step_names() -> List[str]:
    return sorted(STEP_BUILDERS)
