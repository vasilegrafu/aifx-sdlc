#!/usr/bin/env python
"""Stage 3 gate: check a produced skill before anyone trusts it.

    python lint_skill.py <skill-dir> [--phrasings phrasings.txt] [--max-body-lines 500]

Fails (exit 1) on anything that makes a skill unusable or unsafe:
  - frontmatter missing, malformed, or `name` not matching the directory
  - a path mentioned in the body that does not exist
  - a credential-shaped string anywhere in the skill (exemplars come out of a
    real repo — this is the rule that matters most)

Warns (exit 0) on everything that makes a skill weak: thin description, body
over budget, bare exemplars with no pair and no notes, long code blocks that
belong in assets/, prohibitions with no reason, rule tables with no default.

Lexical overlap with --phrasings is a proxy for triggering, not proof. Real
proof is the Stage 4 firing test: if skilled output matches the baseline, the
skill did not load, whatever this script said.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import read_text  # noqa: E402

SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"), "OpenAI-style key"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{16,}\b"), "Anthropic key"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "GitHub token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{30,}\b"), "Google API key"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"), "Slack token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"""(?i)\b(api[_-]?key|secret|password|passwd|token|client[_-]?secret)\b\s*[:=]\s*["'][^"'\s]{12,}["']"""),
     "assigned credential"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\."), "JWT"),
]
PLACEHOLDER = re.compile(r"(?i)(x{6,}|\.{3,}|<[^>]+>|your[_-]|example|placeholder|changeme|dummy|redacted|\bfake\b)")

STOPWORDS = set("""a an the of for to in on with and or is are be this that it its use used using
when how what which where new add create make build write get set do does not from into by at as""".split())

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
PATH_RE = re.compile(r"`([A-Za-z0-9_./\-]+/[A-Za-z0-9_.\-]+)`")
FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.S)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, m: str) -> None:
        self.errors.append(m)

    def warn(self, m: str) -> None:
        self.warnings.append(m)

    def note(self, m: str) -> None:
        self.notes.append(m)


def parse_frontmatter(text: str, r: Report) -> dict:
    """Minimal YAML: the frontmatter contract is name + description, both scalars."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        r.error("no YAML frontmatter — SKILL.md must open with `---` on line 1")
        return {}
    fm: dict[str, str] = {}
    key = None
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s+", line) and key:
            fm[key] += " " + line.strip()
            continue
        k, sep, v = line.partition(":")
        if not sep:
            r.error(f"frontmatter line is not `key: value`: {line!r}")
            continue
        key = k.strip()
        fm[key] = v.strip().strip('"').strip("'")
    return fm


def check_frontmatter(fm: dict, skill_dir: Path, r: Report) -> None:
    name = fm.get("name", "")
    if not name:
        r.error("frontmatter has no `name`")
    else:
        if name != skill_dir.name:
            r.error(f"`name: {name}` does not match directory `{skill_dir.name}` — the skill may not load")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
            r.error(f"`name: {name}` must be lowercase kebab-case")
        if len(name) > 64:
            r.error(f"`name` is {len(name)} chars; keep it under 64")

    desc = fm.get("description", "")
    if not desc:
        r.error("frontmatter has no `description` — this is the trigger; without it the skill never fires")
        return
    if len(desc) < 80:
        r.warn(f"description is {len(desc)} chars: too thin to trigger on varied phrasings")
    if len(desc) > 1024:
        r.warn(f"description is {len(desc)} chars: past the point where triggering improves")
    if not re.search(r"(?i)\buse (this )?(skill )?when\b", desc):
        r.warn("description has no `Use when …` clause — say the situations, not just the capability")
    if re.search(r"(?i)\b(I |you should|my )", desc):
        r.warn("description should be third person, describing the skill and its triggers")
    for extra in set(fm) - {"name", "description", "license", "allowed-tools", "metadata"}:
        r.note(f"unrecognised frontmatter key `{extra}` — harmless, but check it is intended")


def check_secrets(skill_dir: Path, r: Report) -> None:
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file():
            continue
        text = read_text(p)
        if not text:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for pat, label in SECRET_PATTERNS:
                m = pat.search(line)
                if not m:
                    continue
                if PLACEHOLDER.search(m.group(0)):
                    continue
                r.error(f"possible {label} in {p.relative_to(skill_dir).as_posix()}:{line_no} — "
                        f"exemplars come from a real repo; scrub before this goes anywhere")
    return


def check_body(body: str, skill_dir: Path, r: Report, max_lines: int) -> None:
    lines = body.splitlines()
    if len(lines) > max_lines:
        r.warn(f"body is {len(lines)} lines (budget {max_lines}) — past this the tail competes "
               f"with the payload. Move the deep-but-rare half into references/ before splitting the skill")
    if len(lines) < 15:
        r.warn("body is very short — check the payload is not sitting in the description")

    for path in set(PATH_RE.findall(body)):
        if path.startswith(("http", "//")) or " " in path:
            continue
        candidates = [skill_dir / path, skill_dir.parent / path, Path(path)]
        if any(c.exists() for c in candidates):
            continue
        if path.split("/")[0] in {"assets", "references", "scripts"}:
            r.error(f"body references `{path}`, which does not exist")
        else:
            r.note(f"body references `{path}` — not found relative to the skill; check it is a "
                   f"path in the target repo, not in the skill")

    for block in FENCE_RE.findall(body):
        n = len(block.splitlines())
        if n > 40:
            r.warn(f"a {n}-line code block sits in the body — shape belongs in assets/ as a real "
                   f"file that can be copied, formatted and linted")

    for m in re.finditer(r"(?im)^\s*[>*\-]?\s*\**(don'?t|never|do not)\b(.{0,160})", body):
        seg = m.group(0)
        if not re.search(r"(?i)because|—|--|\(|reverted|caused|broke|instead", seg):
            r.warn(f"prohibition with no reason: {seg.strip()[:80]!r} — a rule without a "
                   f"consequence gets overridden, or outlives its reason")

    for tbl in re.findall(r"(?m)^\|.*\|\s*$(?:\n^\|.*\|\s*$)+", body):
        if re.search(r"(?i)\bif\b|\bwhen\b", tbl.splitlines()[0]) and not re.search(
                r"(?i)default|otherwise|none of the above|neither", tbl):
            r.warn("a decision table has no default row — an unmatched case must fail loudly, "
                   "not silently take row one")
        if len(tbl.splitlines()) - 2 > 6:
            r.note("a decision table has more than ~5 rows — that is a design axis, not a lookup; "
                   "consider a principle with two worked examples")


def check_assets(skill_dir: Path, body: str, r: Report) -> None:
    assets = skill_dir / "assets"
    if not assets.is_dir():
        r.warn("no assets/ — structure carried only in prose generates code that reads as foreign")
        return
    files = [p for p in assets.rglob("*") if p.is_file()]
    code = [p for p in files if p.suffix.lower() not in {".md", ".txt"}
            and ".template." not in p.name]
    if not code:
        # a process skill legitimately ships templates; a code-generation skill does not
        r.note("assets/ holds no code exemplars — fine for a process or checklist skill, "
               "but a skill that generates code needs at least one real file to copy")
    for p in code:
        notes = p.with_suffix(p.suffix + ".notes.md")
        alt_notes = p.parent / (p.stem + ".notes.md")
        siblings = [q for q in code if q != p and q.suffix == p.suffix]
        if not notes.exists() and not alt_notes.exists() and not siblings:
            r.warn(f"`assets/{p.name}` is a lone exemplar with no pair and no .notes.md — "
                   f"a single sample cannot say which lines are contract and which are sample data")
    for p in files:
        if p.name not in body and p.stem not in body:
            r.note(f"`assets/{p.relative_to(assets).as_posix()}` is never mentioned in the body — "
                   f"unreferenced assets are rarely loaded")


VALID_CLASSES = {"Enforced", "Repaired", "Reasoned", "Recent", "Confirmed"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_provenance(skill_dir: Path, body: str, r: Report) -> None:
    """Every rule should be re-checkable. Provenance is what drift.py reads."""
    path = skill_dir / "references" / "provenance.jsonl"
    if not path.is_file():
        # a hand-written process skill was not mined from anywhere, so it has no
        # source to re-check; a skill carrying copied code always does
        mined = [p for p in (skill_dir / "assets").rglob("*")
                 if p.is_file() and p.suffix.lower() not in {".md", ".txt"}
                 and ".template." not in p.name]
        msg = ("no references/provenance.jsonl — nothing in this skill can be re-checked later, "
               "and drift.py cannot run against it")
        (r.warn if mined else r.note)(msg)
        return
    import json
    ids: set[str] = set()
    items = 0
    for n, line in enumerate(read_text(path).splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            r.error(f"provenance.jsonl line {n} is not valid JSON: {exc}")
            continue
        if "_schema" in obj or "_comment" in obj:
            r.warn(f"provenance.jsonl line {n} is template scaffolding — delete it")
            continue
        items += 1
        for key in ("id", "claim", "form", "where", "evidence", "source", "mined"):
            if not obj.get(key):
                r.error(f"provenance item {obj.get('id', f'on line {n}')} has no `{key}`")
        if obj.get("id") in ids:
            r.error(f"duplicate provenance id `{obj.get('id')}` — ids must be stable and unique")
        ids.add(obj.get("id"))

        classes = {e.get("class") for e in obj.get("evidence", []) if isinstance(e, dict)}
        for cls in classes - VALID_CLASSES:
            r.error(f"provenance item `{obj.get('id')}` has unknown evidence class `{cls}`")
        if classes and not (classes & {"Enforced"}) and len(classes) < 2:
            r.warn(f"provenance item `{obj.get('id')}` rests on one evidence class "
                   f"({', '.join(classes)}) — two are required unless it is Enforced")
        if "Confirmed" in classes:
            if not obj.get("confirmed_by") or not ISO_DATE.match(str(obj.get("confirmed_on", ""))):
                r.error(f"provenance item `{obj.get('id')}` is Confirmed but has no "
                        f"confirmed_by / confirmed_on (YYYY-MM-DD) — an unattributed confirmation "
                        f"cannot be re-asked")
        if obj.get("mined") and not ISO_DATE.match(str(obj["mined"])):
            r.warn(f"provenance item `{obj.get('id')}` has a non-ISO `mined` date")

        where = str(obj.get("where", "")).split("#")[0]
        if where and not (skill_dir / where).exists():
            r.error(f"provenance item `{obj.get('id')}` points at `{where}`, which does not exist")

    if items == 0:
        r.warn("provenance.jsonl holds no items")


def check_phrasings(desc: str, phrasings: Path, r: Report) -> None:
    words = set(re.findall(r"[a-z0-9]+", desc.lower())) - STOPWORDS
    misses = []
    for line in read_text(phrasings).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        toks = set(re.findall(r"[a-z0-9]+", line.lower())) - STOPWORDS
        if not toks:
            continue
        overlap = toks & words
        if len(overlap) < 2:
            misses.append((line, sorted(overlap)))
    if misses:
        r.warn(f"{len(misses)} phrasing(s) share fewer than two content words with the description:")
        for line, ov in misses[:10]:
            r.warn(f"    {line!r} (overlap: {ov or 'none'})")
    else:
        r.note("all phrasings share content words with the description (a proxy — confirm with "
               "the Stage 4 firing test)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir", type=Path)
    ap.add_argument("--phrasings", type=Path, default=None,
                    help="file of one-per-line requests you would actually type")
    ap.add_argument("--max-body-lines", type=int, default=500)
    args = ap.parse_args()

    skill_dir = args.skill_dir.resolve()
    r = Report()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        print(f"error: {skill_md} not found", file=sys.stderr)
        return 2

    text = read_text(skill_md)
    fm = parse_frontmatter(text, r)
    check_frontmatter(fm, skill_dir, r)
    body = FRONTMATTER_RE.sub("", text, count=1)
    check_body(body, skill_dir, r, args.max_body_lines)
    check_assets(skill_dir, body, r)
    check_provenance(skill_dir, body, r)
    check_secrets(skill_dir, r)
    if args.phrasings:
        if args.phrasings.is_file():
            check_phrasings(fm.get("description", ""), args.phrasings, r)
        else:
            r.warn(f"--phrasings file {args.phrasings} not found")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"# lint — {skill_dir.name}\n")
    for label, items in (("ERROR", r.errors), ("WARN", r.warnings), ("NOTE", r.notes)):
        for m in items:
            print(f"{label}: {m}")
    print(f"\n{len(r.errors)} error(s), {len(r.warnings)} warning(s), {len(r.notes)} note(s)")
    if not r.errors and not r.warnings:
        print("clean — now run the Stage 4 firing test, which is the only real proof")
    return 1 if r.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
