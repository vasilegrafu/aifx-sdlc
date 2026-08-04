# Worked example — what a run produces

A concrete instance, so the shape of the output is not left to interpretation.
The stack here is incidental (a TypeScript service repo); the shape is not.

## Stage 0 output

- Target: `github.com/acme/platform`, scope `services/`, `packages/http/`
- What we'd build with it: a new HTTP service in `services/<name>/`
- Weak spots: `services/legacy-billing` (mid-migration, do not mine)
- Beyond the code: full git history, PR bodies, `docs/adr/`

## Stage 1 output (ledger extract)

| # | Claim | Example | Enf | Rep | Rea | Rec | Accident test | Survives |
|---|---|---|---|---|---|---|---|---|
| 1 | Every handler returns `Result<T, AppError>`; nothing throws across a module boundary | `services/orders/create.ts:14` | ✓ (lint rule `no-throw-boundary`) | ✓ `a91f3c` | ✓ ADR-014 | ✓ | callers stop compiling | yes |
| 2 | Repos take a `Tx` as first arg, never open their own transaction | `services/orders/repo.ts:22` | – | ✓ `77c0aa` | ✓ PR #812 | ✓ | nothing breaks; double-commit under load | yes |
| 3 | Files ordered: types, then the exported factory, then helpers | many | – | – | – | ✓ | nobody notices | **no — fossil** |
| 4 | `zod` schemas live beside the handler, not in a shared `schemas/` | `services/orders/create.ts:1` | – | ✓ `2b40de` | – | ✓ | nothing breaks; drift | yes |

Contradiction found: `services/legacy-billing` uses class-based controllers,
everything since 2024-06 uses factory functions. Newest class-based file: 400
days. Ruling: **encode factories, tripwire the classes.**

## Stage 2 output (charter extract)

Baseline got right, therefore dropped: directory layout, test framework choice,
async/await usage, DI by constructor argument, naming of the exported factory.

Baseline got wrong **silently** — the payload:

| Item | Quirk/Principle | Form |
|---|---|---|
| `Result` return instead of throwing | principle + local type | exemplar + one prose line |
| repo takes `Tx`, never opens one | principle | exemplar pair + tripwire |
| schema colocated with handler | quirk | exemplar |
| errors carry a `code` from `packages/http/codes.ts`, never a free string | quirk | prose + script check |

Baseline got wrong **loudly** (one line each, no exemplar): import path alias
`@platform/*`, the `strict: true` tsconfig, the test file naming.

## Which skills came out, in what order

1. **`acme-http-service`** — the vertical slice: handler, repo, schema, wiring,
   test. This is the one that gets invoked weekly.
2. **`acme-db-migration`** — separate artifact, separate moment, separate
   trigger phrasing. Not a section of skill 1.
3. **`acme-service-client`** — the generated client other services import.
   Deferred: it is mostly codegen, so a script in skill 1 may cover it.

Not skills: "error handling", "layering", "naming". Those are the content of
skill 1 and would fire partially on their own.

## The first skill's SKILL.md skeleton

```markdown
---
name: acme-http-service
description: Build an HTTP service in the acme platform monorepo the way the
  team builds them — handler, repo, zod schema, wiring and test. Use when adding
  or changing anything under services/, adding an endpoint, route, handler,
  controller or resolver, wiring a new repo or Tx-taking data access, writing a
  zod schema for a request, or when asked to make a service match the rest of
  the repo or follow house style. Covers Result-returning handlers, AppError
  codes and the packages/http contract.
---

# HTTP services in the acme platform

Generates one service directory under `services/<name>/`.

## Start here
- `assets/create-order.handler.ts` — the canonical handler (default)
- `assets/list-orders.handler.ts` — same shape, read path, no Tx
The pair differs in exactly one dimension: whether it writes. That difference is
the specification of what varies.
- `assets/order.repo.ts` + `assets/order.repo.notes.md` — load-bearing lines marked
- `assets/create-order.test.ts` — the test that ships with every handler

## Choose
| If the endpoint… | Then | Exemplar |
|---|---|---|
| writes to the database | take `Tx` as the first repo arg; the handler owns the transaction | `assets/create-order.handler.ts` |
| only reads | no `Tx`; repo takes the connection | `assets/list-orders.handler.ts` |
| calls another service | use the generated client, never `fetch` | `assets/gateway-call.ts` |
| none of the above | follow the read path and say so in your output | — |

## Rules
- Return `Result<T, AppError>`. Nothing throws across a module boundary (ADR-014).
- `AppError` carries a `code` from `packages/http/codes.ts`. Never a free string —
  the alert routing keys off it.
- The zod schema lives beside the handler, not in a shared directory.

## Don't
> **Don't** open a transaction inside a repo — `77c0aa` reverted that; under
> load it double-committed on retry. Instead: the handler opens it and passes
> `Tx` down.

> **Don't** write a class-based controller. You will see them in
> `services/legacy-billing`; they are being removed (PR #1044).

## Before you're done
    pnpm lint && pnpm test services/<name>
    python .claude/skills/acme-http-service/scripts/check_error_codes.py services/<name>

## Bets
- The Tx rule may generalise past repos to any resource handle — encoded narrowly
  for now. A second reverted commit on cache handles would settle it.
```

## What went where, and why

| Item | Location | Why not somewhere else |
|---|---|---|
| handler shape, ordering, ceremony | `assets/*.handler.ts` | prose describing a shape is dead weight beside the file |
| what varies between read and write | the *pair* of handlers | one exemplar cannot show an axis |
| which lines are contract | `assets/order.repo.notes.md` | the repo had no second instance to pair with |
| `Result` / `AppError` / colocation rules | body prose | they are *whys* and *nevers*; nothing to show |
| error codes are valid | `scripts/check_error_codes.py` | a check with one right answer is a fact, not advice |
| the full list of rejected approaches | `references/rejected.md` | true, occasionally needed, would crowd out the payload |
| ADR-014's full argument | `references/adr-014-summary.md` | loaded only when someone challenges the rule |
| regeneration log | `references/regressions.md` | the test suite for next quarter's re-run |

## Stage 4 result

Target: `services/refunds` (created 6 weeks ago, ticket PLAT-2210 available).

- original ↔ baseline 54% · original ↔ skilled 88% · baseline ↔ skilled 31%
- Verdict: FIRING, CLOSER.
- Meaningful divergences: 2 — the skilled version invented `services/refunds/
  schemas/` (colocation rule stated but not shown → moved the schema into the
  exemplar file), and used `throw` in one branch (rule present but buried at line
  310 → moved into the Rules block).
- Second target `services/notifications`: no new meaningful divergences. Stop.
