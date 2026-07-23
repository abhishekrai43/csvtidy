# csvtidy

Clean and merge messy CSV files from the command line — trim whitespace, fix dates, drop duplicates, and combine an entire folder of exports into one tidy file.
For data engineers, analysts, and anyone wrangling CSV exports — including the messy ones Excel and other tools spit out — that are too big to open in a spreadsheet or too many to merge by hand.
**100% offline**, powered by **DuckDB** so it streams files **bigger than RAM**, and driven by reusable **recipes** — define your cleanup once, replay it on any file or whole folder.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Powered by DuckDB](https://img.shields.io/badge/engine-DuckDB-yellow.svg)

```bash
pip install csvtidy
```

```bash
# Merge every CSV in a folder into one, tagging each row with its source file
csvtidy merge ./exports --output combined.csv --source-column file
```

---

## Why csvtidy

- **Offline and private.** Your data never leaves your machine. No accounts, no uploads, no cloud.
- **Handles huge files.** The DuckDB engine streams and spills to disk, so you can merge and clean CSVs that won't fit in memory — the kind that crash a spreadsheet.
- **Recipe-driven.** Save a sequence of steps to a small YAML file and re-run it on next month's data with one command. Build once, reuse forever.
- **Non-destructive by default.** Values are read as text and never silently retyped; dates it can't parse keep their original text instead of becoming blank.
- **Merges messy schemas.** Files with mismatched or reordered columns are aligned by name — missing cells become empty, nothing shifts.

## Install

```bash
# Recommended: isolated install with pipx
pipx install csvtidy

# Or with pip
pip install csvtidy

# From source
git clone https://github.com/abhishekrai43/csvtidy
cd csvtidy
pip install -e .
```

Requires Python 3.9+.

## Examples

The repo ships small messy sample files under `examples/` so every command below runs as-is.

### Merge a whole folder into one file

```bash
csvtidy merge examples/data/exports --output combined.csv --source-column source_file
```

Per-file headers are read as headers (never repeated as data rows), columns are aligned by name across files, and `--source-column` adds the originating file name to every row.

### Remove duplicate rows

```bash
# Exact duplicate rows
csvtidy dedupe combined.csv --output deduped.csv

# Or treat rows as duplicates when one column matches (keep the first seen)
csvtidy dedupe combined.csv --subset email --keep first
```

### Clean up a file

```bash
csvtidy clean examples/data/exports/feb.csv \
  --fix-dates signup_date \
  --collapse-spaces \
  --output feb.clean.csv
```

Trims whitespace, collapses internal whitespace runs, drops all-blank rows, and rewrites the dates in `signup_date` to ISO `YYYY-MM-DD` — leaving anything it can't parse untouched.

### Run a recipe (build once, re-run forever)

```bash
csvtidy run examples/recipe.yaml
```

Pipe results between commands or into other tools — omit `--output` and csvtidy writes CSV to stdout, while progress goes to stderr:

```bash
csvtidy merge ./exports | csvtidy dedupe - --subset email > clean.csv
```

## Recipes

A recipe captures a whole cleanup as a small YAML file so you can replay it on new data without re-typing flags. Steps run top to bottom and compose into a single DuckDB query, keeping the same larger-than-RAM streaming as the individual commands.

```yaml
# examples/recipe.yaml
input: examples/data/exports/*.csv   # files, a folder, or a glob
output: customers.clean.csv
source_column: source_file           # tag each row with its source file

steps:
  - clean:
      trim: true
      drop_empty_rows: true
      collapse_spaces: true
      fix_dates: [signup_date]
      date_format: "%Y-%m-%d"

  - dedupe:
      subset: [email]
      keep: first
```

```bash
csvtidy run examples/recipe.yaml            # writes customers.clean.csv
csvtidy run examples/recipe.yaml -o out.csv # override the output path
```

## Command reference

### `csvtidy merge <inputs...>`

Combine multiple CSVs, a folder, or globs into one file.

| Option | Description |
| --- | --- |
| `-o, --output PATH` | Write to this CSV (streamed to disk). Omit to print to stdout. |
| `--source-column NAME` | Add a column with each row's source file name. |
| `--pattern GLOB` | Glob used when an input is a folder (default `*.csv`). |
| `-r, --recursive` | Recurse into sub-folders. |

### `csvtidy dedupe <input>`

Remove duplicate rows, preserving input order.

| Option | Description |
| --- | --- |
| `-o, --output PATH` | Write to this CSV. Omit for stdout. |
| `--subset COLS` | Comma-separated columns to match on (default: all columns). |
| `--keep first\|last` | Which duplicate to keep (default `first`). |

### `csvtidy clean <input>`

Apply cleanup primitives.

| Option | Description |
| --- | --- |
| `-o, --output PATH` | Write to this CSV. Omit for stdout. |
| `--trim / --no-trim` | Trim leading/trailing whitespace (default on). |
| `--drop-empty-rows / --keep-empty-rows` | Drop rows where every cell is blank (default on). |
| `--collapse-spaces` | Collapse internal whitespace runs to a single space. |
| `--fix-dates COLS` | Comma-separated columns to normalize to one date format. |
| `--date-format FMT` | Output format for `--fix-dates` (default `%Y-%m-%d`). |
| `--dayfirst` | Read ambiguous dates as day/month (e.g. `03/04` = 3 April). |

### `csvtidy run <recipe.yaml>`

Run a saved recipe. `-o, --output PATH` overrides the recipe's output path.

## How it works

csvtidy is a thin, friendly layer over [DuckDB](https://duckdb.org). Each command builds a single SQL query and lets DuckDB do the heavy lifting: it reads CSVs directly, processes data in a streaming fashion, and spills to disk when a job is larger than memory. That's why merging a folder of multi-gigabyte exports works on an ordinary laptop without loading everything into RAM at once.

## Development

```bash
git clone https://github.com/abhishekrai43/csvtidy
cd csvtidy
pip install -e ".[dev]"
pytest
```

## License

[MIT](LICENSE) © Abhishek Rai

---

csvtidy is the open-source command-line tool. If you'd prefer a full desktop app with a visual recipe builder and the same offline, big-file engine, see [Kramata](https://kramata.com).
