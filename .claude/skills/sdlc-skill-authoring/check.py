"""Validate every skill and agent in this repository against the standard.

The standard is SKILL.md beside this file. This script is the half of it that
cannot drift: prose describes the rules, and this reads the tree.

    python check.py            report, exit 1 if any error
    python check.py --quiet    print only failures

Two severities, and the line between them matters:

  error    the thing is broken for any subject -- a missing SKILL.md, a name
           that does not match its directory, a required frontmatter field
           that is absent. Exits 1.
  warning  it works and something about it is thin or suspect -- a description
           that names no trigger, a SKILL.md long enough that progressive
           disclosure has failed. Said loudly, fails nothing.

Without that split a legitimately terse skill would fail its own check, and a
check people learn to ignore is worse than no check at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------- locations

def _ascend(start: Path, marker: str) -> Path:
    """Nearest ancestor of `start` containing `marker`. Hard error, no guess."""
    for directory in [start, *start.parents]:
        if (directory / marker).exists():
            return directory
    raise SystemExit(
        f"no {marker!r} directory above {start}.\n"
        f"This skill finds the tree it validates by locating the .claude "
        f"directory it lives in, so it must sit at "
        f"<project>/.claude/skills/<name>/.")


PROJECT_ROOT = _ascend(Path(__file__).resolve().parent, ".claude")
CLAUDE_DIR = PROJECT_ROOT / ".claude"
SKILLS_DIR = CLAUDE_DIR / "skills"
AGENTS_DIR = CLAUDE_DIR / "agents"

#: A SKILL.md longer than this has stopped being a procedure. Not a hard
#: limit -- a warning, because the right length depends on the procedure.
SKILL_MD_MAX_LINES = 220

#: A description shorter than this cannot state what, when and when-not.
DESCRIPTION_MIN_CHARS = 80

#: Phrases that make a description routable. One is enough.
TRIGGER_CUES = ("use when", "use for", "use on", "use it when",
                "use this", "when asked", "triggers on", "invoked when")

AGENT_REQUIRED_FIELDS = ("name", "description", "tools", "model")


# ---------------------------------------------------------------- frontmatter

def parse_frontmatter(text: str) -> dict[str, str] | None:
    """The `key: value` block between the first two `---` lines.

    Deliberately not YAML: the only shapes used here are flat strings, and a
    parser dependency for that would be a dependency nothing else needs. A
    value may contain colons -- only the first one separates.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def body_after_frontmatter(text: str) -> list[str]:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        try:
            return lines[lines.index("---", 1) + 1:]
        except ValueError:
            pass
    return lines


# ---------------------------------------------------------------- reporting

class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []   # severity, subject, message

    def error(self, subject: str, message: str) -> None:
        self.rows.append(("error", subject, message))

    def warning(self, subject: str, message: str) -> None:
        self.rows.append(("warning", subject, message))

    @property
    def errors(self) -> int:
        return sum(1 for severity, _, _ in self.rows if severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for severity, _, _ in self.rows if severity == "warning")


# ---------------------------------------------------------------- checks

def check_skill(directory: Path, report: Report, known: set[str]) -> None:
    subject = f"skills/{directory.name}"
    skill_md = directory / "SKILL.md"

    if not skill_md.is_file():
        report.error(subject, "no SKILL.md")
        return

    text = skill_md.read_text(encoding="utf-8")
    fields = parse_frontmatter(text)

    if fields is None:
        report.error(subject, "SKILL.md has no `---` frontmatter block")
        return

    name = fields.get("name")
    if not name:
        report.error(subject, "frontmatter has no `name`")
    elif name != directory.name:
        report.error(subject, f"name {name!r} does not match its directory")

    _check_description(subject, fields.get("description"), report)

    body = body_after_frontmatter(text)
    if len(body) > SKILL_MD_MAX_LINES:
        report.warning(
            subject,
            f"SKILL.md is {len(body)} lines (over {SKILL_MD_MAX_LINES}) -- "
            f"push depth into REFERENCE.md or stacks/, or split the skill")

    _check_empty_promises(directory, subject, report)
    _check_references(text, subject, report, known)


def check_agent(path: Path, report: Report, known: set[str]) -> None:
    subject = f"agents/{path.name}"
    text = path.read_text(encoding="utf-8")
    fields = parse_frontmatter(text)

    if fields is None:
        report.error(subject, "no `---` frontmatter block")
        return

    for field in AGENT_REQUIRED_FIELDS:
        if not fields.get(field):
            report.error(subject, f"frontmatter has no `{field}`")

    name = fields.get("name")
    if name and name != path.stem:
        report.error(subject, f"name {name!r} does not match its filename")

    _check_description(subject, fields.get("description"), report)
    _check_references(text, subject, report, known)


def _check_description(subject: str, description: str | None, report: Report) -> None:
    if not description:
        report.error(subject, "frontmatter has no `description`")
        return
    if len(description) < DESCRIPTION_MIN_CHARS:
        report.warning(
            subject,
            f"description is {len(description)} chars -- too short to say what "
            f"it does, when to use it and when not to")
    if not any(cue in description.lower() for cue in TRIGGER_CUES):
        report.warning(
            subject,
            "description names no trigger -- it is the routing key, so say "
            "when to use it in the words someone would type")


def _check_empty_promises(directory: Path, subject: str, report: Report) -> None:
    """A REFERENCE.md or stacks/ that holds nothing costs a turn to discover."""
    reference = directory / "REFERENCE.md"
    if reference.is_file() and not reference.read_text(encoding="utf-8").strip():
        report.error(subject, "REFERENCE.md is empty")

    stacks = directory / "stacks"
    if stacks.is_dir() and not any(stacks.glob("*.md")):
        report.error(subject, "stacks/ holds no .md file")


def _check_references(text: str, subject: str, report: Report, known: set[str]) -> None:
    """Every `sdlc-*` named in the file must be something that exists.

    The `description` is scanned along with the body, because pointing at a
    sibling ("for X, use sdlc-other instead") is how a description keeps a
    dispatch from going wrong -- a stale pointer there is worse than one in
    prose. The `name` line is skipped: when it disagrees with its directory
    that is already reported, and reporting it twice under a second heading
    only teaches people to skim.

    A warning, not an error: naming a skill that is planned but unbuilt is a
    legitimate way to mark intent, exactly as this repository's own documents
    do. What it must never do is go unnoticed.
    """
    import re

    scanned = "\n".join(
        line for line in text.splitlines()
        if not line.startswith("name:"))

    own = subject.split("/", 1)[1].removesuffix(".md")
    for match in sorted(set(re.findall(r"\bsdlc-[a-z0-9]+(?:-[a-z0-9]+)*", scanned))):
        if match != own and match not in known:
            report.warning(subject, f"names {match!r}, which does not exist")


# ---------------------------------------------------------------- entry point

def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv
    report = Report()

    if not SKILLS_DIR.is_dir():
        raise SystemExit(f"no skills directory at {SKILLS_DIR}")

    skill_dirs = sorted(
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith((".", "_")))
    agent_files = sorted(
        f for f in AGENTS_DIR.glob("*.md")) if AGENTS_DIR.is_dir() else []

    known = {d.name for d in skill_dirs} | {f.stem for f in agent_files}

    for directory in skill_dirs:
        check_skill(directory, report, known)
    for path in agent_files:
        check_agent(path, report, known)

    if not quiet:
        print(f"aifx-sdlc  {PROJECT_ROOT}\n")
        print(f"skills  {len(skill_dirs)}")
        for directory in skill_dirs:
            print(f"  {directory.name}")
        print(f"\nagents  {len(agent_files)}")
        for path in agent_files:
            print(f"  {path.stem}")
        print()

    if report.rows:
        for severity, subject, message in report.rows:
            print(f"{severity:8}{subject:32}{message}")
        print()

    verdict = (f"{report.errors} error(s), {report.warnings} warning(s)")
    if not quiet or report.rows:
        print(verdict)

    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
