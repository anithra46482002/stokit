"""Static guard: no module may reference a global name that is neither defined, imported nor a builtin.

Regression for the missing `import json` in adminapi/crud.py, which made every product PATCH/POST carrying
`discount_banners` or `set_contains` raise NameError (HTTP 500). Mock-based view tests never executed that line.
Stdlib only (symtable); scans first-party packages and skips the venv, caches and migrations.
"""
import builtins
import symtable
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("accounts", "adminapi", "legacy_api", "legacydb", "config")
IMPLICIT = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__path__", "__class__"}


def _unresolved(path):
    source = path.read_text(encoding="utf-8-sig")
    top = symtable.symtable(source, str(path), "exec")
    defined = {s.get_name() for s in top.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
    found = []

    def walk(table):
        for sym in table.get_symbols():
            name = sym.get_name()
            if sym.is_referenced() and (sym.is_global() or (table.get_type() == "module" and not (
                    sym.is_assigned() or sym.is_imported() or sym.is_namespace()))):
                if name not in defined and name not in IMPLICIT:
                    found.append(f"{path.relative_to(ROOT)}:{table.get_lineno()} ({table.get_name()}) uses undefined name '{name}'")
        for child in table.get_children():
            walk(child)

    walk(top)
    return found


class UndefinedNameTests(SimpleTestCase):
    def test_no_unresolved_global_names(self):
        problems = []
        scanned = 0
        for package in PACKAGES:
            for path in sorted((ROOT / package).rglob("*.py")):
                if "migrations" in path.parts or "__pycache__" in path.parts:
                    continue
                scanned += 1
                problems.extend(_unresolved(path))
        self.assertGreater(scanned, 40, "static scan did not find the expected source files")
        self.assertEqual(problems, [], "unresolved global names:\n" + "\n".join(problems))
