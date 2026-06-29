from csvtidy.commands.clean import build_clean
from csvtidy.engine import read_sql
from tests.conftest import rows_of


def test_clean_trims_and_collapses(con, make_csv):
    f = make_csv("c.csv", ["name"], [[" Erin   Park "]])
    sql = build_clean(con, read_sql(con, [str(f)]), collapse_spaces=True)
    cols, rows = rows_of(con, sql)
    assert rows[0][cols.index("name")] == "Erin Park"


def test_clean_drops_empty_rows(con, make_csv):
    f = make_csv("c.csv", ["a", "b"], [["1", "2"], ["", ""], ["  ", ""]])
    sql = build_clean(con, read_sql(con, [str(f)]))
    _, rows = rows_of(con, sql)
    assert len(rows) == 1  # both blank rows dropped


def test_clean_fix_dates_normalizes(con, make_csv):
    f = make_csv(
        "c.csv",
        ["when"],
        [["01/06/2024"], ["Feb 3 2024"], ["2024-03-01"]],
    )
    sql = build_clean(con, read_sql(con, [str(f)]), fix_dates=["when"])
    cols, rows = rows_of(con, sql)
    values = [r[cols.index("when")] for r in rows]
    assert values == ["2024-01-06", "2024-02-03", "2024-03-01"]


def test_clean_fix_dates_keeps_unparseable(con, make_csv):
    f = make_csv("c.csv", ["when"], [["not a date"]])
    sql = build_clean(con, read_sql(con, [str(f)]), fix_dates=["when"])
    cols, rows = rows_of(con, sql)
    assert rows[0][cols.index("when")] == "not a date"  # non-destructive
