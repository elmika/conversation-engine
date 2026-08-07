---
name: reflect
description: "Propose durable engineering lessons from this coding session, routed to the right place in the project. Nothing is written without approval."
---

# /reflect — Session Reflection

Propose durable lessons from this coding session, each routed to its correct home. Human reviews and approves before anything is written.

Run at the end of any significant session.

---

## Steps

### 1. Gather the raw material

Two sources:

**a) Git state**
```bash
git log --oneline -10
git diff HEAD~1..HEAD --stat
```
What was built, changed, or fixed this session?

**b) The current conversation**
What was decided, discovered, or corrected that isn't already captured in the code, comments, or git messages?

### 2. Identify candidates

Look for what is:
- **Non-obvious** — not derivable by reading the code or git history
- **Durable** — will still matter in future sessions
- **New** — not already documented in `CLAUDE.md`, `architecture/`, or `docs/`

Common categories worth capturing:
- An architectural constraint that will catch future engineers if not written down
- A coding convention that emerged organically and should be made explicit
- A gate or invariant that must be enforced (e.g. "never do X in layer Y")
- A debugging insight or failure mode discovered the hard way
- A rejected design option with the reason — captures "we considered this"

### 3. Route to the closest scope

| The lesson is about... | It belongs in... |
|---|---|
| A project-wide convention or gate | `CLAUDE.md` — add to the relevant section |
| An architectural decision (why, not what) | `architecture/` — add or update the relevant doc |
| A specific domain/feature invariant | A note in `docs/` or the module's own docstring |
| A testing or tooling pattern | `CLAUDE.md` Commands section |

**Closest scope wins.** Don't promote to `CLAUDE.md` what only applies to one file or module.

**A round with 0 entries is fully valid.** Don't propose weak entries to fill a quota.

### 4. Review loop

Present all proposals together (0–3 max), numbered. For each:
- **Target file and section**
- **Exact text to add** — as it would appear in the file

Ask: **"Approve / Skip / Edit — 1, 2, 3?"**

- **Approve** — write it immediately (apply any twist verbatim)
- **Skip** — discard
- **Edit** — ask what to change, show revised version, ask again

### 5. Write approved items

Edit the target file directly. Show what changed.

---

## Rules

- Propose 0–3 items max. Quality over quantity.
- Never auto-write — every item requires explicit approval.
- Always read the target section before proposing — don't duplicate what's already there.
- If nothing qualifies, say so and stop. That's a valid outcome.
