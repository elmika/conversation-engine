# Prompt Management

## Architecture overview

Prompts are stored in **SQLite** (the same DB as conversations). They are loaded into the UI via the admin panel and selected per conversation at runtime. The prompt system has two layers:

```
prompts/*.md  (seed source, gitignored, private)
     │
     ▼  on every startup (upsert)
SQLite prompts table  (live store)
     │
     ▼  at conversation start
LLM system prompt
```

Key files:
- `app/infra/prompt_seeder.py` — parses `*.md` files, upserts into DB on startup
- `app/infra/persistence/repo_prompt.py` — CRUD for the prompts table
- `app/infra/persistence/models.py` — `Prompt` ORM model
- `app/domain/prompt_registry.py` — **removed**; DB is now the registry
- `app/settings.py` → `prompts_dir` — path to seed directory (default: `./prompts`)

---

## Critical: seeder behaviour

The seeder runs on **every startup**, not just the first time. It upserts — meaning it overwrites the DB row with whatever is in the `.md` file.

**Consequence:** if you edit a prompt through the admin UI and then restart the server (`make up`), your edit is lost if a matching `.md` file exists for that slug.

Safe workflow:
- Edit the `.md` file first, then restart → DB reflects the file
- Edit via admin UI only for prompts that have **no corresponding `.md` file** (those are safe from the seeder)
- Or: delete the `.md` file for a prompt you want to own in the DB permanently

---

## Two-phase prompts (first-response vs. ongoing)

When a prompt has a structured "opening" format followed by free conversation, the LLM will re-emit the opening format on every turn unless you explicitly separate the two phases in the system prompt.

Pattern that works:

```
## Your very first response only
<structured format instructions>

## All subsequent turns
<open-ended behavior instructions — explicitly say NOT to repeat the opening format>
```

Without the explicit `## All subsequent turns` section, the model treats the opening format as the default behavior for all responses.

---

## Prompt `.md` format

```markdown
---
name: Human-readable name
model: gpt-4.1          # optional — overrides default model for this prompt
---
System prompt content goes here.
```

The slug is the filename stem (e.g. `learn-typescript.md` → slug `learn-typescript`).

---

## Seed files on disk (gitignored)

These files live in `prompts/` and are **not committed**. They are private prompt IP.

| File | Slug | Notes |
|---|---|---|
| `prompts/default.md` | `default` | Disabled in DB |
| `prompts/conflict-coach-v1.md` | `conflict-coach-v1` | Disabled in DB, 57 chars (stub) |
| `prompts/learn-typescript.md` | `learn-typescript` | Disabled in DB, seeder overwrites on restart |

All other prompts in the DB (see below) have **no corresponding file** and are safe from the seeder.

---

## Current DB state

Live DB: `data/chat.db` — last checked 2026-04-24.

| Slug | Name | Model | Active | Last updated |
|---|---|---|---|---|
| `docker-3-sections` | Docker with 3 sections templates | gpt-5.4-pro | ✅ | 2026-04-01 |
| `learn-typescript-module3` | TypeScript Mentor Module 3 | — | ✅ | 2026-03-23 |
| `test-templating-system` | TEST templating system | gpt-5.4-nano | ✅ | 2026-03-27 |
| `learn-typescript` | TypeScript Mentor | — | ❌ | 2026-03-30 |
| `default` | Default Assistant | — | ❌ | 2026-03-30 |
| `docker-prompt-3` | Docker prompt 3 (with time) | gpt-5.3-codex | ❌ | 2026-03-30 |
| `typescript-prompt-4` | Docker prompt | gpt-5.4-mini | ❌ | 2026-03-28 |
| `conflict-coach-v1` | Conflict Coach | — | ❌ | 2026-03-27 |
| `docker-prompt-2` | Docker prompt 2 | gpt-5.3-codex | ❌ | 2026-03-27 |

**Active prompts** (3): `docker-3-sections`, `learn-typescript-module3`, `test-templating-system`.

The `docker-3-sections` prompt is the most recent and most complete — it uses the section templating system (`{{course}}`, `{{user}}`, `{{progress}}`, `{{time:*}}`).

---

## Versioning and privacy

`prompts/` is gitignored. Prompt content is never committed to the public repo.

Recommended workflow for versioning:
- Keep a separate private git repo (`skillforge-prompts`) that mirrors the `prompts/` directory
- Commit prompt changes there independently
- `make backup` before any destructive change to also snapshot the DB

To backup the DB:
```bash
make backup
# saves to data/backups/chat-<timestamp>.sql
```

---

## Prompt templating

The `docker-3-sections` prompt shows the full template syntax. Placeholders are injected at conversation start from section files:

| Placeholder | Source |
|---|---|
| `{{course}}` | `sections/course/<slug>.md` (falls back to `default.md`) |
| `{{user}}` | `sections/user/default.md` |
| `{{progress}}` | `sections/progress/<slug>.md` (falls back to `default.md`) |
| `{{time:conversation-start}}` | Conversation `created_at` timestamp |
| `{{time:current}}` | Current time at request |
| `{{time:lesson-time-spent}}` | Elapsed since conversation start |

Section files in `sections/` are also gitignored.

---

## Target architecture (in progress)

The current model conflates two concerns: the prompt template (stable frame) and slot content (dynamic per learner / per course). The target architecture separates them via a port/adapter pattern:

- **Layer 1a** — `prompts` table, unchanged. Holds only system prompt templates.
- **Layer 1b** — `SlotResolver` port, scans `{{tags}}` and resolves each. Default adapter reads from `sections/` files.
- **Layer 2** — `courses`, `users`, `progress` tables (new). Override `SlotResolver` adapter reads from these; slugs for active course/user come from env vars (`COURSE_SLUG`, `USER_SLUG`). Progress is keyed by (user, course).


**Phase status:**
- [ ] Phase 1 — Formalize `SlotResolver` port, extract file loader into `FileSlotResolver` (no behaviour change)
- [ ] Phase 2 — Add `courses`, `users`, `progress` tables + repos
- [ ] Phase 3 — Settings (`course_slug`, `user_slug`) + `Layer2SlotResolver` with file fallback
- [ ] Phase 4 — One-shot import script from `sections/` to tables
- [ ] Phase 5 — Admin UI for Layer 2 tables (deferred)
