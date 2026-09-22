"""The results.db data dictionary (scripts/describe_results_db.py)."""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "describe_results_db.py"
_spec = importlib.util.spec_from_file_location("describe_results_db", _PATH)
doc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(doc)


def make_db(path, tables):
    with sqlite3.connect(path) as con:
        for name, columns in tables.items():
            con.execute(
                f'create table "{name}" ({", ".join(f"{c!r} REAL" for c in columns)})'
            )


def test_every_documented_column_appears_with_its_meaning(tmp_path):
    db = tmp_path / "r.db"
    make_db(db, {"runs": ["run_id", "decline_p50"]})
    text = doc.render(
        db,
        {
            "runs": (
                "One row per solve.",
                "08",
                {"run_id": "Run name.", "decline_p50": "Median rate."},
            )
        },
    )
    assert "## `runs`" in text
    assert "| `decline_p50` | REAL | Median rate. |" in text


def test_an_undocumented_column_is_an_error(tmp_path):
    db = tmp_path / "r.db"
    make_db(db, {"runs": ["run_id", "new_column"]})
    with pytest.raises(ValueError, match="new_column"):
        doc.render(db, {"runs": ("One row per solve.", "08", {"run_id": "Run name."})})


def test_an_undocumented_table_is_an_error(tmp_path):
    db = tmp_path / "r.db"
    make_db(db, {"mystery": ["x"]})
    with pytest.raises(ValueError, match="mystery"):
        doc.render(db, {})


def test_a_prefix_pattern_documents_a_family_of_columns(tmp_path):
    db = tmp_path / "r.db"
    make_db(db, {"paths": ["year", "scenario: BAU", "scenario: TN"]})
    text = doc.render(
        db,
        {
            "paths": (
                "Paths.",
                "10",
                {"year": "Year.", "scenario: *": "That scenario's CH4, kt."},
            )
        },
    )
    assert "| `scenario: BAU` | REAL | That scenario's CH4, kt. |" in text
