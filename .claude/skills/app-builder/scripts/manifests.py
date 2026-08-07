"""Dependency manifests, read as structure rather than as source.

`package.json`, `requirements.txt`, `pyproject.toml` and `.csproj` are not code
and no extractor claims them, so until now nothing in the index knew a codebase
declared a single dependency. That is a real gap rather than a tidy one: for a
frontend, *the dependency set is half the convention*. Whether a project reaches
for MUI or Tailwind, axios or fetch, Redux or Zustand says more about how its
code is written than most of what `shape` reports -- and none of it is visible
in an import list alone, because an import proves a package is used somewhere
while a manifest says what the project committed to.

It also closes a specific hole. A generated layer that imports a package nobody
declared installs nothing, builds nowhere, and fails at run time with a module
resolution error that reads as a path problem.

Read deliberately shallowly. A manifest is a fact about a project, and walking
into every nested package would turn one fact into hundreds -- the same reason
`SKIP_DIRS` exists.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from _common import rel

# package.json is the only one that appears more than a level or two down in
# normal projects -- a monorepo puts one per app.
MAX_DEPTH = 4

NAMES = ("package.json", "pyproject.toml", "requirements.txt",
         "requirements-dev.txt", "requirements_dev.txt")


def _is_manifest(name: str) -> bool:
    low = name.lower()
    # `tsconfig*.json` rather than `tsconfig.json`. The standard Vite and
    # create-react-app layouts put nothing but `references` in the root file and
    # every real setting in `tsconfig.app.json` -- so matching the root alone
    # reports the most common modern setup as a project that sets no strictness
    # at all, which is a false absence rather than a missing feature.
    return (low in NAMES or low.endswith(".csproj")
            or (low.startswith("tsconfig") and low.endswith(".json")))


def _strip_jsonc(text: str) -> str:
    """JSON with comments and trailing commas, as `tsconfig.json` is allowed to
    be and usually is. `json.loads` rejects both, and a config that fails to
    parse is reported as a project with no TypeScript settings at all."""
    out, i, n = [], 0, len(text)
    quote = False
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                quote = False
            i += 1
            continue
        if c == '"':
            quote = True; out.append(c); i += 1; continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c); i += 1
    cleaned = "".join(out)
    return re.sub(r",(\s*[}\]])", r"\1", cleaned)


def _tsconfig(path: Path) -> dict | None:
    """TypeScript's settings, read as dependencies are read.

    `typescript` is never imported, so counting imports reports a TypeScript
    codebase as using no TypeScript. What actually varies between projects is
    the *strictness*, and that is a real convention with real consequences:
    `strict` off means every generated type annotation is advisory, and
    `noUncheckedIndexedAccess` decides whether `rows[0]` is `Row` or
    `Row | undefined` -- which changes the code you must write around it.
    """
    try:
        data = json.loads(_strip_jsonc(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    options = data.get("compilerOptions") or {}
    if not isinstance(options, dict):
        options = {}
    # Only the flags that change what code has to look like. A `paths` map or an
    # `outDir` is a fact about this project and not a convention worth comparing.
    keep = ("strict", "noImplicitAny", "strictNullChecks",
            "noUncheckedIndexedAccess", "exactOptionalPropertyTypes",
            "noUnusedLocals", "noUnusedParameters", "target", "module",
            "moduleResolution", "jsx", "verbatimModuleSyntax", "isolatedModules")
    return {"ecosystem": "tsconfig",
            "deps": {k: str(options[k]) for k in keep if k in options},
            "dev_deps": {}, "scripts": {},
            "extends": str(data.get("extends") or "")}


def _npm(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return {"ecosystem": "npm",
            "deps": {k: str(v) for k, v in (data.get("dependencies") or {}).items()},
            "dev_deps": {k: str(v) for k, v in (data.get("devDependencies") or {}).items()},
            "scripts": {k: str(v) for k, v in (data.get("scripts") or {}).items()}}


def _pyproject(path: Path) -> dict | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return None
    project = data.get("project") or {}
    deps = {}
    for spec in project.get("dependencies") or ():
        name, version = _split_requirement(str(spec))
        if name:
            deps[name] = version
    # Poetry keeps its own tree, and a project using it has nothing under
    # [project] at all -- reporting "no dependencies" there would be wrong.
    poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    for name, version in poetry.items():
        if name.lower() != "python":
            deps.setdefault(name, str(version) if not isinstance(version, dict)
                            else str(version.get("version") or ""))
    return {"ecosystem": "python", "deps": deps, "dev_deps": {}, "scripts": {}}


def _requirements(path: Path) -> dict | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    deps = {}
    for line in lines:
        line = line.split("#", 1)[0].strip()
        # -r, -e, --index-url and friends are instructions, not dependencies.
        if not line or line.startswith("-"):
            continue
        name, version = _split_requirement(line)
        if name:
            deps[name] = version
    return {"ecosystem": "python", "deps": deps, "dev_deps": {}, "scripts": {}}


def _csproj(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    deps = {}
    for m in re.finditer(r'<PackageReference\s+Include="([^"]+)"'
                         r'(?:\s+Version="([^"]*)")?', text):
        deps[m.group(1)] = m.group(2) or ""
    return {"ecosystem": "nuget", "deps": deps, "dev_deps": {}, "scripts": {}}


_REQ = re.compile(r"^([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*(.*)$")


def _split_requirement(spec: str) -> tuple[str, str]:
    """`sqlalchemy>=2.0` -> `('sqlalchemy', '>=2.0')`. Extras are dropped."""
    spec = spec.split(";", 1)[0].strip()
    m = _REQ.match(spec)
    if not m:
        return "", ""
    return m.group(1), m.group(2).strip()


def _reader(path: Path):
    name = path.name.lower()
    if name.startswith("tsconfig") and name.endswith(".json"):
        return _tsconfig
    if name == "package.json":
        return _npm
    if name == "pyproject.toml":
        return _pyproject
    if name.startswith("requirements") and name.endswith(".txt"):
        return _requirements
    if name.endswith(".csproj"):
        return _csproj
    return None


def find(root: Path, skip, keep=None) -> list[Path]:
    """Manifests at or near the top of a codebase. `skip` decides which
    directories are not walked, so it stays consistent with the source walk."""
    out, stack = [], [(root, 0)]
    while stack:
        here, depth = stack.pop()
        try:
            entries = list(here.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if (depth < MAX_DEPTH and not skip(entry.name)
                        and (keep is None or keep(entry, True))):
                    stack.append((entry, depth + 1))
            elif (_is_manifest(entry.name)
                  and (keep is None or keep(entry, False))):
                out.append(entry)
    return out


def extract(root: Path, repo: str, skip, keep=None):
    """Yield one `manifest` record per file found.

    A record carries no `imports`, `bases` or `name`, so every command that
    filters on those ignores it. Commands that iterate raw records must skip
    kinds they do not understand -- `layers` does.
    """
    for path in find(root, skip, keep):
        reader = _reader(path)
        if reader is None:
            continue
        parsed = reader(path)
        if parsed is None:
            continue
        try:
            mtime = int(path.stat().st_mtime)
        except OSError:
            mtime = 0
        yield {"k": "manifest", "repo": repo, "path": rel(path, root),
               "mtime": mtime, "commit": 0, **parsed}
