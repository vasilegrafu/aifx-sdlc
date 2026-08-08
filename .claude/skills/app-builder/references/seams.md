# Seams: the library the source calls, and the platform the target runs on

Read this when the exemplar sits on a library, or when the target's database,
runtime or operating system is not the source's. Both are places where a
contract reproduced faithfully still fails, and neither shows up in `shape` —
to the exemplars they are not variables at all.

## A library is not an exemplar

A solution usually contains both the application and the library it is built on
— often a directory linked in by junction or symlink, which is part of the
solution and indexed as part of it. They play different roles and must not be
read the same way:

- The **application** is what you copy. Its family is the thing being reproduced.
- The **library** is what you call. You need its surface — what exists, what each
  method takes — not its style.

Separate them **at query time**, with `--path` to look inside one and
`--not-path` to hold it out:

```bash
scripts/query.py families --not-path 'devfx/*'   # the application
scripts/query.py find   --path 'devfx/database/*'  # what it calls
```

A `shape` run across both averages a library's conventions into an
application's and produces a form neither one uses — the same error as averaging
two codebases in step 6. Query-time separation keeps the index faithful to the
solution while still letting you read one side at a time.

## When the library is not there

The application may not be able to reach the library its exemplars call. There
are three answers, and the right one is rarely obvious:

- **Link it**, as the source does — a junction or symlink into the other
  repository. Highest fidelity, and the generated code stays identical to the
  exemplar. The cost is that a linked directory carries no package metadata, so
  **nothing declares its dependencies**: they have to be found by importing it
  until it stops raising, and written down by hand.
- **Reproduce its surface**, minimally — only the methods the generated code
  calls, under the same names. Self-contained, and honest as long as it stays
  small. It stops being honest the moment it grows behaviour of its own.
- **Deviate**, and call the underlying framework directly. Cheapest, and it
  breaks the contract `shape` reported. Only with the user's agreement.

Say which one you took and why. All three are defensible; silently picking one
is not.

## The target is not the source's platform

The contract has a platform baked into it, and the exemplars will not mention it
because to them it is not a variable. Reproducing the contract faithfully onto a
different database, runtime or operating system is where generated code fails —
each failure looking like a different problem, all of them the same seam.

Before generating, enumerate what the source assumes and the target does not:

- **dialect-only DDL** — schemas, `IF EXISTS` forms, collations, identity
- **isolation levels** the target rejects, including the source's default
- **constraint enforcement that is off by default** — SQLite ignores foreign
  keys unless every connection is told otherwise, so `ondelete='CASCADE'` is
  declared and never enforced, and nothing errors until a row is orphaned
- **types with no equivalent**, and how the source spells identity

Each of these is a VARIES that the **target** settles, not the source. Reproduce
what the contract means, not the SQL it happens to emit — and when you diverge,
say so in the file, next to the line that diverges.

Every one of these is invisible to rungs 1 and 2 of step 8: the code imports,
the entry point runs, and the guarantee is not there. Rung 3 is where a platform
seam is caught, which is why it is the rung nothing will do for you.
