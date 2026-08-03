# aifx-sdlc

**A versioned toolbox for Claude Code — agents and skills for the software
development lifecycle, in one repo, dropped into any project.**

Right now this is the repository shell only: configuration, versioning and
licensing are wired, and `.claude/agents/` and `.claude/skills/` are declared
and empty. Nothing is on the shelf yet.

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Layout

```
aifx-sdlc/
  environment.json          which config/secrets pair a run reads
  config.dev.json           tracked    — settings that are not secret
  config.prod.json          tracked
  secrets.dev.json          NEVER tracked — placeholders until you fill them
  version.json              the single version for everything in here
  .claude/
    agents/                 empty
    skills/                 empty
```

## Installation

### Option A — copy

Grab a skill folder and paste it into your project. MIT allows exactly this —
take it, keep it, modify it.

```
<your-project>/.claude/skills/<skill-name>/
```

Claude Code discovers it next session. Your copy is frozen: it never changes
unless you update it yourself.

### Option B — clone once, link everywhere

One shared clone on your machine serves all your projects through links.
Nothing you already have is touched — your own skills stay beside the links.

```bash
git clone https://github.com/vasilegrafu/aifx-sdlc.git
```

```bat
:: Windows (junction — no admin rights needed)
mklink /J <project>\.claude\skills\<skill-name> <path-to>\aifx-sdlc\.claude\skills\<skill-name>
```

```bash
# macOS / Linux
ln -s <path-to>/aifx-sdlc/.claude/skills/<skill-name> <project>/.claude/skills/<skill-name>
```

**Linking is the better option if you intend to run anything.** A linked skill
resolves back through the junction into this clone, so it reads the clone's
`environment.json`, `config.<env>.json` and `secrets.<env>.json`: one set of
credentials on the machine, and nothing lands in your project. A copied skill
is a real file tree and needs its own beside `.claude/` — in which case add
`secrets.*.json` to that project's `.gitignore` yourself, since this repo's
cannot reach it.

```bash
git -C <path-to>/aifx-sdlc pull             # latest
git -C <path-to>/aifx-sdlc checkout v1.0.0  # or pin a released version
```

---

## Environment

```powershell
python -m venv .venv
.venv\Scripts\activate                    # PowerShell
# source .venv/bin/activate               # macOS / Linux
pip install -r requirements.txt
```

### Configuration is split by file, not by field

`config.<env>.json` is **tracked** and holds what is not secret.
`secrets.<env>.json` is **never tracked** and holds keys. A fresh clone has
neither, so write them by hand in this shape:

```json
{
  "<provider>": {
    "api_key": "<your-key>"
  }
}
```

**There is deliberately no `secrets.example.json` to copy.** `.gitignore`
matches `secrets.*.json` with no exception, so nothing by that name can ever be
staged. A tracked template would need a negation, and a negation is one
mis-ordered line away from publishing a key. Writing four lines of JSON is
cheaper than that risk.

The split is per **file** so that "is this safe to commit?" is decided once for
the filename, rather than judged every time someone adds a field.

### The environment is declared, not passed

`environment.json` is tracked, so a fresh clone starts somewhere:

```json
{ "environment": "dev" }
```

Set `ENVIRONMENT` in the shell to override it. There is no flag: a flag reaches
only the command you typed it on, and cannot be inherited by a shell another
tool spawned — which is where things usually run.

It is deliberately **not** called `.env`. That name is where every tutorial
tells you to put an API key, and this file is tracked; a name nobody reaches
for by reflex is a name that can be committed safely.

One declaration picks `config.<env>.json` *and* `secrets.<env>.json` together,
so a run cannot read dev settings against a prod key.

---

## Versioning

**One version governs the whole repository** — everything under
`.claude/`, and anything published alongside it. The single source of truth is
`version.json` at the root; no version number lives anywhere else. A skill that
versioned itself would let two skills in one clone disagree about which shared
assets they were written against.

Each release is the git tag `v<version>`.

**A published version is immutable.** Any change, however small, is a new
version — never a re-tag.

| bump | what changed | what it costs you |
|---|---|---|
| **PATCH** | a fix with no contract change | nothing |
| **MINOR** | additive: a new skill, agent, or capability | nothing — existing use is unchanged |
| **MAJOR** | a contract changed, something was removed, **or a published command changed shape** | you must opt in; a linked directory can vanish; a command from the previous release may stop working |

**A release is major if a thing that worked stops working** — whether the thing
is a file, a link, or a line someone typed.

Read the tag message — `git show v1.0.0` — for what broke and what to do about
it.

---

## License

[MIT](LICENSE) — use it, copy it, ship it.
