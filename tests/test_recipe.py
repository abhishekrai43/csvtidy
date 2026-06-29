from csvtidy.recipe import build_recipe_sql
from tests.conftest import rows_of, write_csv


def _exports(tmp_path):
    d = tmp_path / "exports"
    write_csv(d / "jan.csv", ["email", "when"],
              [["a@x.com", "01/06/2024"], ["a@x.com", "2024-01-06"]])
    write_csv(d / "feb.csv", ["email", "when", "plan"],
              [["b@x.com", "Feb 3 2024", "pro"], ["", "", ""]])
    return d


def test_recipe_cleans_merges_and_dedupes(con, tmp_path):
    d = _exports(tmp_path)
    recipe = {
        "input": str(d / "*.csv"),
        "source_column": "source_file",
        "steps": [
            {"clean": {"trim": True, "drop_empty_rows": True,
                       "fix_dates": ["when"]}},
            {"dedupe": {"subset": ["email"], "keep": "first"}},
        ],
    }
    sql, output = build_recipe_sql(con, recipe)
    cols, rows = rows_of(con, sql)

    assert output is None  # not set in this recipe
    assert "source_file" in cols
    # The all-blank feb row is dropped even though source_file is populated.
    emails = sorted(r[cols.index("email")] for r in rows)
    assert emails == ["a@x.com", "b@x.com"]
    # Dates were normalized during the clean step.
    whens = {r[cols.index("when")] for r in rows}
    assert whens == {"2024-01-06", "2024-02-03"}


def test_recipe_keeps_explicit_output(con, tmp_path):
    d = _exports(tmp_path)
    sql, output = build_recipe_sql(
        con, {"input": str(d / "*.csv"), "output": "result.csv"}
    )
    assert output == "result.csv"
