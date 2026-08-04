#!/usr/bin/env python
"""The silent failure, made loud.

    python check_registered.py <atlas-root> [--domain reference_data] [--entity stock_instrument]

A model in this layer only becomes a table because something imports it:

    database_generator.generate()
      -> import database.<domain>_data          (database_generator.py)
      -> from .models import *                  (<domain>_data/__init__.py)
      -> from .<entity> import <Entity>         (<domain>_data/models/__init__.py)
      -> the class body runs and registers on BaseDatabaseModel.metadata
      -> metadata.create_all(engine) creates the table

Break any link and nothing fails. The module imports, the controller imports,
the tests that touch it pass — and the table is simply never created, which
surfaces later as a runtime error against a database that looks fine.

The same applies to `__table_args__`: a model with no `{'schema': ...}` entry
lands in `dbo` instead of its domain schema, and `create_schemas()` has quietly
built an empty schema beside it.

Run with no --entity to check every model in the tree. Exit 1 on any finding.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CLASS_RE = re.compile(r"^class\s+(\w+)\s*\(\s*BaseDatabaseModel\s*\)", re.M)
SCHEMA_RE = re.compile(r"""\{\s*['"]schema['"]\s*:\s*['"]([\w]+)['"]""")
TABLENAME_RE = re.compile(r"""__tablename__\s*=\s*['"]([\w]+)['"]""")


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def imported_in(barrel: Path, module_stem: str, symbol: str) -> bool:
    """Either `from .<stem> import <Symbol>` or `from .<stem> import *`."""
    text = read(barrel)
    if re.search(rf"^\s*from\s+\.{re.escape(module_stem)}\s+import\s+\*", text, re.M):
        return True
    return bool(re.search(rf"^\s*from\s+\.{re.escape(module_stem)}\s+import\s+.*\b{re.escape(symbol)}\b",
                          text, re.M))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="solution.atlas (the directory holding database/)")
    ap.add_argument("--domain", default=None, help="e.g. reference_data")
    ap.add_argument("--entity", default=None, help="module stem, e.g. stock_instrument")
    args = ap.parse_args()

    db = args.root / "database" if (args.root / "database").is_dir() else args.root
    if not db.is_dir():
        print(f"error: {db} is not the database directory", file=sys.stderr)
        return 2

    generator = read(db / "database_generator.py")
    problems: list[str] = []
    checked = 0

    domains = ([db / f"{args.domain}"] if args.domain
               else sorted(p for p in db.iterdir() if p.is_dir() and p.name.endswith("_data")))

    for domain_dir in domains:
        domain = domain_dir.name
        models_dir = domain_dir / "models"
        if not models_dir.is_dir():
            continue

        # 1. the domain package must be imported by the generator, or none of
        #    its models ever register
        if not re.search(rf"^\s*import\s+database\.{re.escape(domain)}\b", generator, re.M):
            problems.append(f"{domain}: not imported in database_generator.py — no table in this "
                            f"domain will ever be created")

        # 2. the domain __init__ must pull models and controllers up
        init = read(domain_dir / "__init__.py")
        for part in ("models", "controllers"):
            if not re.search(rf"^\s*from\s+\.{part}\s+import\s+\*", init, re.M):
                problems.append(f"{domain}/__init__.py: missing `from .{part} import *`")

        for model_file in sorted(models_dir.glob("*.py")):
            if model_file.name == "__init__.py":
                continue
            stem = model_file.stem
            if args.entity and stem != args.entity:
                continue
            text = read(model_file)
            classes = CLASS_RE.findall(text)
            if not classes:
                continue
            checked += 1
            entity = classes[0]

            # 3. the model must be imported by the models barrel
            if not imported_in(models_dir / "__init__.py", stem, entity):
                problems.append(f"{domain}/models/__init__.py: does not import {entity} from "
                                f"`.{stem}` — the table will never be created, and nothing "
                                f"will say so")

            # 4. __table_args__ must place it in the domain schema
            schema = SCHEMA_RE.search(text)
            if not schema:
                problems.append(f"{domain}/models/{stem}.py: no {{'schema': ...}} in "
                                f"__table_args__ — the table lands in dbo")
            elif schema.group(1) != domain:
                problems.append(f"{domain}/models/{stem}.py: schema is '{schema.group(1)}' but the "
                                f"package is '{domain}'")

            # 5. table name should match the module name (the rename in 5b1401b3
            #    made this the convention: one table per instrument type)
            tablename = TABLENAME_RE.search(text)
            if tablename and tablename.group(1) != stem:
                problems.append(f"{domain}/models/{stem}.py: __tablename__ is "
                                f"'{tablename.group(1)}' but the module is '{stem}'")

            # 6. the matching controller, if present, must be in its barrel
            ctrl_dir = domain_dir / "controllers"
            ctrl_file = ctrl_dir / f"{stem}_dbctrl.py"
            if ctrl_file.is_file():
                ctrl_classes = re.findall(r"^class\s+(\w+)", read(ctrl_file), re.M)
                symbol = ctrl_classes[0] if ctrl_classes else f"{entity}DbCtrl"
                if not imported_in(ctrl_dir / "__init__.py", ctrl_file.stem, symbol):
                    problems.append(f"{domain}/controllers/__init__.py: does not import {symbol} "
                                    f"from `.{ctrl_file.stem}`")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"checked {checked} model(s) across {len(domains)} domain(s)\n")
    for p in problems:
        print(f"FAIL  {p}")
    if not problems:
        print("OK  every model registers, sits in its domain schema, and is exported")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
