---
name: <kebab-case, matches the directory name>
description: <What it produces, in one clause.> Use when <task phrasings: verbs someone would type, the artifact noun, this codebase's own directory names / file suffixes / framework names, and the problem phrasings — "make this match the rest of the repo", "why does my X not Y">.
---

# <Artifact> in <this codebase>

<One sentence: what this generates and where it goes.>

## Start here

<The exemplar to copy, named. If two, say which one and when.>

- `assets/<canonical>.<ext>` — <what it is; the default>
- `assets/<variant>.<ext>` — <how it differs and when to use it instead>

Copy the structure, not the domain nouns. `assets/<canonical>.notes.md` marks
which lines are contract and which are sample data.

## Choose

| If the thing you are building… | Then | Exemplar |
|---|---|---|
| <observable property of the request> | <what changes> | `assets/<x>` |
| <observable property of the request> | <what changes> | `assets/<y>` |
| none of the above | <the default> | `assets/<canonical>` |

If nothing matches, follow the default and say so in your output.

## Rules

<Only what a competent stranger gets wrong and does not notice. Each one a
sentence. No shape descriptions — the exemplars carry those.>

- <rule>
- <rule>

## Don't

> **Don't** <the tempting thing> — <what happened> (<sha / PR / ADR>).
> Instead: <what to do>.

> **Don't** <the tempting thing> — <what happened> (<pointer>).
> Instead: <what to do>.

<Longer list, if there is one, in `references/rejected.md`.>

## Before you're done

```bash
<the repo's own formatter / linter / test command>
./.venv/Scripts/python.exe <skill-dir>/scripts/check.py <generated-path>
```

## Bets

- <the part that is uncertain> — <what would settle it>.

<Deeper material lives in references/ and is read only when needed:
 - `references/<topic>.md` — <when to open it>>
