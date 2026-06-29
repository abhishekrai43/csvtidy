from csvtidy.engine import read_sql
from tests.conftest import rows_of


def test_merge_aligns_mismatched_columns(con, make_csv):
    a = make_csv("a.csv", ["id", "name"], [["1", "Ann"], ["2", "Bea"]])
    b = make_csv("b.csv", ["id", "email"], [["3", "c@x.com"]])

    sql = read_sql(con, [str(a), str(b)])
    cols, rows = rows_of(con, sql)

    # union_by_name yields the superset of columns across both files.
    assert set(cols) == {"id", "name", "email"}
    assert len(rows) == 3
    # missing cells become NULL, not a shifted/garbled value.
    by_id = {r[cols.index("id")]: r for r in rows}
    assert by_id["3"][cols.index("name")] is None


def test_merge_headers_not_repeated_as_rows(con, make_csv):
    a = make_csv("a.csv", ["id"], [["1"]])
    b = make_csv("b.csv", ["id"], [["2"]])

    sql = read_sql(con, [str(a), str(b)])
    _, rows = rows_of(con, sql)

    values = {r[0] for r in rows}
    assert values == {"1", "2"}
    assert "id" not in values  # header consumed, not emitted as data


def test_merge_source_column(con, make_csv):
    a = make_csv("jan.csv", ["id"], [["1"]])
    b = make_csv("feb.csv", ["id"], [["2"]])

    sql = read_sql(con, [str(a), str(b)], source_column="source_file")
    cols, rows = rows_of(con, sql)

    assert "source_file" in cols
    sources = {r[cols.index("source_file")] for r in rows}
    assert sources == {"jan.csv", "feb.csv"}  # basename, not full path
