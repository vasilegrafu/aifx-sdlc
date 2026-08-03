# CLAUDE.md

Operational context for this repository — what a session needs before touching
anything. It is deliberately short, because there is not much here yet.

## What is here

The repository shell: configuration, versioning, licensing. `.claude/agents/`
and `.claude/skills/` are declared and **empty** — the shelves exist, nothing is
on them.

There is no build, no test runner, and no entry point yet. Do not describe one
in a document before it exists.

## Run things with the venv

```bash
./.venv/Scripts/python.exe <script>          # NOT bare `python`
```

Bare `python` on this machine has no `jinja2` and fails on the first import.

## No file holding a key may ever be trackable

This repository has a remote. Treat anything committed as fetchable by anyone
who guesses the path.

- `secrets.*.json` is gitignored with **no exception and no negation**. The two
  files in the tree hold placeholders, not keys — a real key replaces a
  placeholder in an untracked file, and never travels any other way.
- `config.<env>.json` is **tracked** and must never hold an `api_key`.
- The environment file is deliberately **not** `.env`, because that is where
  every tutorial says to put a key and this one is tracked.
- Assume this repo is committed with a blanket `git add .`, so no file holding
  a key may ever be trackable — not even briefly.

## Ask before committing, and again before pushing

Do the work and leave it uncommitted unless asked. A push is separate from a
commit and needs its own go-ahead: **a published tag is immutable**, because
anything that links an asset by tag breaks if the tag moves.

## One version, at the root

`version.json` is the only place a version number lives. Every skill and agent
added here is governed by it — nothing versions itself. When something starts
generating files that pin a version at build time, **bump before you rebuild**:
rebuild first and the output pins the old number.

The semver rule is in `README.md`: a release is MAJOR if **a thing that worked
stops working**, whether the thing is a file, a link, or a line someone typed.

## Do not put a count of the tree in any document

How many skills exist, how many agents, how many of anything — a count typed
into prose is true the day it is typed and cannot say when it stopped being.
Let something that reads the tree state it, or do not state it.
