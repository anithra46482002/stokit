"""Regression tests for zg_location.city_name collation evidence (see docs/STOKIT_CITY_NAME_COLLATION_EVAL.json).

The evidence file is produced by scripts/schema_conversion/collation_eval.py against a disposable MariaDB instance
(utf8mb4_uca1400_ai_ci, the source column collation) and disposable PostgreSQL databases. These tests are DB-free.
Source server in the dump is MariaDB 11.8.9; the executable evidence was produced on MariaDB 13.0.2, so the
facts below are established for that version only.
"""
import json
import unittest
from pathlib import Path

from django.test import SimpleTestCase

EVAL = Path(__file__).resolve().parents[1] / "docs" / "STOKIT_CITY_NAME_COLLATION_EVAL.json"
DDL = Path(__file__).resolve().parents[1] / "docs" / "STOKIT_COMPLETE_DDL_CANDIDATE.sql"


def _load():
    return json.loads(EVAL.read_text(encoding="utf-8"))


def _by_case(data):
    return {row["case"]: row for row in data["detail"]}


class SourceCollationEvidenceTests(SimpleTestCase):
    def test_source_table_collation_recorded(self):
        self.assertEqual(_load()["mariadb"]["TABLE_COLLATION"], "utf8mb4_uca1400_ai_ci")

    def test_source_equal_pairs(self):
        rows = _by_case(_load())
        for case in ("case Kochi/kochi", "accent cafe-acute/cafe", "NFC vs NFD cafe-acute",
                     "trailing space", "two trailing spaces"):
            self.assertTrue(rows[case]["mariadb_equal"], case)

    def test_source_distinct_pairs(self):
        rows = _by_case(_load())
        for case in ("leading space", "trailing tab", "inner space", "dotless i",
                     "hyphen Kochi-City/KochiCity", "control Kochi/Kochin"):
            self.assertFalse(rows[case]["mariadb_equal"], case)

    def test_source_unique_collision_matches_equality(self):
        for row in _load()["detail"]:
            self.assertEqual(row["mariadb_equal"], row["mariadb_unique_collision"], row["case"])

    def test_ddl_candidate_declares_no_collation_for_city_name(self):
        text = DDL.read_text(encoding="utf-8")
        block = text.split('CREATE TABLE "zg_location"', 1)[1].split(");", 1)[0]
        self.assertNotIn("COLLATE", block)
        self.assertIn('UNIQUE ("city_name")', block)

    def test_current_candidate_known_collation_gap_is_recorded(self):
        # Do not mask the known parity gap as an expected failure. Keep a passing
        # regression assertion that the current default strategy is still explicitly
        # recorded as incompatible until an approved collation strategy is implemented.
        summary = _load()["summary"]["default_deterministic"]
        self.assertGreater(summary["mismatches"], 0)
        self.assertIn("case Kochi/kochi", summary["mismatched_cases"])
        self.assertIn("trailing NBSP", _load()["summary"]["ks-level1 + rtrim expression unique index"]["mismatched_cases"])

    def test_best_evaluated_strategy_residual_gap_is_recorded(self):
        best = _load()["summary"]["ks-level1 + rtrim expression unique index"]
        self.assertEqual(best["mismatched_cases"], ["trailing NBSP"])
