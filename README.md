# aifx-sdlc

Skills for Claude Code, and the configuration they share.

## What is here

`.claude/skills/` holds the skills; `.claude/agents/` is declared and empty.
`config.json` says which codebases those skills may read and where they build.
`solution.university/` holds what they generated.

There is no build and no test runner. Do not describe one here before it exists.

## One interpreter

```bash
./.venv/Scripts/python.exe <script>
```

One venv at the root, built from one `requirements.txt`, serving both the skills
and what they generate.

Nothing in `requirements.txt` is needed by a skill. Every skill imports nothing
but the standard library, deliberately — that is what lets one be copied into
another checkout and still work. The dependencies are there for
`solution.university/`, and some of them are not even its choices: `devfx` is
linked in as a junction rather than installed, so it brings no metadata with it
and what it imports has to be declared by hand.

The venv is not tracked. Rebuild it with `python -m venv .venv` and
`pip install -r requirements.txt`.

## Tests

```bash
./.venv/Scripts/python.exe -m pytest solution.university
```

They run against their own database and refuse to start if pointed at any other.

## Configuration

`config.json` is **tracked** and must never hold an `api_key`. It holds absolute
paths to codebases on this machine, so it is expected to be wrong on anyone
else's; a skill reports a configured path as missing rather than failing
obscurely.

A skill's working data — anything derived from another repository — belongs in
`<skill>/.data/`, kept out of git by a `.gitignore` inside that skill so the
rule travels with it. Assume this repository is committed with a blanket
`git add .`: no file holding a key, and no copy of someone else's source, may
ever be trackable, not even briefly.

## Versioning

`version.json` is the only place a version number lives. Nothing versions
itself. When something starts generating files that pin a version at build time,
bump before rebuilding — rebuild first and the output pins the old number.

A release is **MAJOR** if a thing that worked stops working, whether the thing
is a file, a link, or a line someone typed.

## Committing

Do the work and leave it uncommitted unless asked. A push is separate from a
commit and needs its own go-ahead: a published tag is immutable, because
anything that links an asset by tag breaks if the tag moves.

## Writing documents here

Do not put a count of the tree in any document — how many skills, how many
agents, how many of anything. A count typed into prose is true the day it is
typed and cannot say when it stopped being. Let something that reads the tree
state it, or do not state it.

## Licence

See `LICENSE`.
