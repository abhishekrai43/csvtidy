import pytest

from csvtidy.commands.dedupe import build_dedupe
from csvtidy.engine import read_sql
from tests.conftest import rows_of


def test_dedupe_full_row(con, make_csv):
    f = make_csv(
        "d.csv",
        ["a", "b"],
        [["1", "x"], ["1", "x"], ["2", "y"]],
    )
    sql = build_dedupe(con, read_sql(con, [str(f)]))
    _, rows = rows_of(con, sql)
    assert len(rows) == 2


def test_dedupe_subset_keeps_first(con, make_csv):
    f = make_csv(
        "d.csv",
        ["email", "name"],
        [["a@x.com", "first"], ["a@x.com", "second"], ["b@x.com", "other"]],
    )
    sql = build_dedupe(con, read_sql(con, [str(f)]), subset=["email"], keep="first")
    cols, rows = rows_of(con, sql)
    names = [r[cols.index("name")] for r in rows]
    assert names == ["first", "other"]


def test_dedupe_subset_keeps_last(con, make_csv):
    f = make_csv(
        "d.csv",
        ["email", "name"],
        [["a@x.com", "first"], ["a@x.com", "second"], ["b@x.com", "other"]],
    )
    sql = build_dedupe(con, read_sql(con, [str(f)]), subset=["email"], keep="last")
    cols, rows = rows_of(con, sql)
    names = [r[cols.index("name")] for r in rows]
    assert names == ["second", "other"]


def test_dedupe_unknown_column_errors(con, make_csv):
    f = make_csv("d.csv", ["a"], [["1"]])
    with pytest.raises(ValueError):
        build_dedupe(con, read_sql(con, [str(f)]), subset=["missing"])
