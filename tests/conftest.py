import csv
from pathlib import Path

import pytest

from csvtidy.engine import connect


@pytest.fixture
def con():
    return connect()


def write_csv(path: Path, header, rows) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def rows_of(con, sql):
    """Run SQL and return (columns, list-of-row-tuples)."""
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return cols, cur.fetchall()


@pytest.fixture
def make_csv(tmp_path):
    def _make(name, header, rows):
        return write_csv(tmp_path / name, header, rows)
    return _make
