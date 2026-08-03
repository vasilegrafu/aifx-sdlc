---
name: sdlc-skill-authoring
description: Write or revise a skill or agent in this repository — the directory shape, the frontmatter contract, how to write a description that actually routes, and the validator that enforces all of it. Use when creating a new skill or agent, turning a mining brief into a working skill, splitting or merging existing ones, or when check.py reports a failure. This is the standard every other skill here is held to.
---

# Authoring a skill or an agent

This skill is the standard the rest of this repository is held to, and it is
**derived from the skills that already exist here, not invented**. When you
change the standard, change the existing skills to match or the standard is
already a lie.

Run the validator when you are done:

```bash
./.venv/Scripts/python.exe .claude/skills/sdlc-skill-authoring/check.py
```

It exits 1 if anything is wrong. That is the end of the procedure, not the
beginning.

## Skill or agent?

**Write a skill** by default. A skill is knowledge and procedure: cheap,
composable, versioned, invokable by anyone.

**Write an agent only** when one of these is true, all of which are about
context rather than subject matter:

- the work reads far more than the answer is worth carrying back
- the job requires *not* having a capability (a reviewer must not hold `Edit`)
- the result is invalid if the same context produced the thing being judged
- there is a conflict of interest with the caller's goal

Everything else is a skill. An agent for a topic that needed none is a cold
start, a re-derived context and a worse answer.

## The shape

```
.claude/skills/<name>/
  SKILL.md          the procedure. Always loaded once triggered. Keep it short.
  REFERENCE.md      depth, loaded only when SKILL.md sends the reader there
  stacks/<x>.md     per-technology detail, loaded on detection
  check.py          the executable part, if the skill has one
```

```
.claude/agents/<name>.md    frontmatter + prompt, one file
```

Only `SKILL.md` is required. Add the rest when there is something to put in
them — an empty `REFERENCE.md` is a promise the reader will waste a turn on.

## Naming

- **Skills** take activity or artifact names: `sdlc-code-review`, `sdlc-adr`.
- **Agents** take role nouns: `sdlc-reviewer`, `sdlc-explorer`.

Both share the `sdlc-` prefix, so the *grammar* is what keeps them apart. A
skill and an agent with the same name leave nobody able to tell which was
invoked.

The directory name and the frontmatter `name` must match. `check.py` enforces
this.

## Frontmatter

**Skill** — two fields, both required:

```yaml
---
name: sdlc-code-trace
description: <what it does> — <when to use it> — <when NOT to use it>
---
```

**Agent** — four:

```yaml
---
name: sdlc-explorer
description: <what it does, when to use it, when not to>
tools: Read, Grep, Glob, Bash, Skill
model: sonnet
---
```

Grant the **narrowest tool set that lets the job finish**. A capability that is
not removed will eventually be used. Where a tool must be granted for one
purpose but not another — `Bash` for `git log` but not for writing — say so
explicitly in the prompt body, and know that prose is a weaker guarantee than
omission.

Pick the model by the work: high-volume, low-judgment reading does not need the
strongest model; adversarial review does.

## The description is a routing key

**It is the highest-leverage sentence in the file** — usually the only part
loaded until the skill fires. A skill nobody triggers is a skill that does not
exist, and the failure is silent: no error, just an answer that ignores it.

Write it for the dispatcher:

1. **What it does**, concretely.
2. **When to use it** — the actual phrases someone would type. Lift real
   wording: "where does X happen", "how do I run this", "what is this repo".
3. **When *not* to** — and name the sibling skill that covers that case. Every
   near-miss you disambiguate is a wrong dispatch that will not happen.

```
✗ description: Helps with testing.
✓ description: Decide what to test, at which level, and what to leave untested.
  Use when planning tests for a new feature, when coverage is argued about, or
  when asked "what should we test here". For writing the tests themselves, use
  sdlc-test-generation.
```

The second one costs a minute and is the difference between a skill that fires
and one that sits there.

## Progressive disclosure

`SKILL.md` is loaded whole, every time it fires. Everything in it is paid for
on every invocation, so it holds the **procedure** and nothing else.

- Rationale, background, edge cases → `REFERENCE.md`
- Per-technology specifics → `stacks/<name>.md`
- Anything bulky or generated → its own file

**One skill is one procedure with per-stack detail behind it, never one skill
per stack.** Forking `SKILL.md` per technology gives you N copies of the
interesting part and N places for it to drift. The invariant lives once.

If `SKILL.md` is growing past a couple of hundred lines, something in it belongs
one level down — or it is two skills.

## Prefer a script to a sentence

Where a rule is deterministic, **check it in code**. Prose drifts from the tree
silently; a script reads the tree every time.

Corollary, and it is absolute: **never write a count of the tree into a
document.** How many skills exist, how many agents, how many stacks — a count
typed into prose is true the day it is typed and cannot say when it stopped
being. Let something that reads the tree state it, or do not state it.

## Validate what you generate

Any skill that *produces* something must check what it produced, splitting
severity two ways:

- **error** — structurally broken, and independent of the input. It would be
  wrong for any subject.
- **warning** — it was produced, but the content is thin. Usually a sparse
  input, so say it loudly and fail nothing.

Without the split, a legitimately sparse input fails its own check, and people
learn to ignore the output — which costs more than having no check.

## One procedure lives in one place

Never restate a procedure in a second file "for convenience". The copy drifts,
and the drift is silent until someone follows the stale one. Link to it.

## Procedure

1. **Name it** and decide skill vs agent by the four criteria above.
2. **Write the description first.** If you cannot say when it should *not*
   fire, the scope is not settled and the body will wander.
3. **Write the procedure** as numbered steps with a stopping condition. A step
   nobody can tell they have finished is not a step.
4. **Push depth down** — `REFERENCE.md`, `stacks/`.
5. **Write the checks** for anything deterministic.
6. **Add the anti-patterns.** Name the failure modes, especially the plausible
   ones — they are what the reader is about to do.
7. **Run `check.py`.** Exit 0, or fix it.
8. **Leave it uncommitted** and say what you built.

## Anti-patterns

- **A vague description.** The most common cause of a skill that never fires,
  and it fails silently.
- **A skill per technology.** See progressive disclosure. This is the mistake
  that scales worst.
- **Writing the standard before the examples.** Two working skills make a
  better standard than a blank page — which is why this file was written after
  the first ones, not before.
- **Documenting instead of proceduring.** A skill is a set of instructions for
  doing something, not an essay about the topic.
- **An empty `REFERENCE.md` or `stacks/`.** A promise that costs a turn to
  discover is empty.
- **Restating a procedure for convenience.** It drifts, silently.
- **Skipping `check.py` because the change was small.** Small changes are the
  ones nobody re-reads.
