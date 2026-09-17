# Tutor Behavior Checklist — course-session-core / closure

Turn-shape checklist for the Socratic tutor (`prompts/course-session-core.md`,
`prompts/course-session-closure.md`). Complements `docs/qa-test-suite.md`
(UI-level flow) and `scripts/smoke_lesson_lifecycle.py` (routing/state, no
content judgment) — this file is the one that pins down *how a reply should
read*, so a prompt or model change can be checked against a fixed bar instead
of "does it feel right" each time. Written after the `course-session-core`
rewrite (`docs/socratic-tutor-plan.md`); re-run whenever that prompt, the
closure prompt, or the objective guard / closure-continuation logic changes.

## How to run this

Manually: `make up`, then a live session via the browser (`docs/qa-test-suite.md`
Test 2 gets you into a core turn) or via `scripts/smoke_lesson_lifecycle.py`-style
direct API calls, sending the trigger message for each row below and checking
the reply against "Expected". An AI agent driving Chrome can run this
identically to a human.

Automated (future): each row is a candidate for an LLM-judge check in the same
style as `prompts/lesson-objective-complete.md` (single-purpose, cheap model,
YES/NO or a short verdict token) — feed the row's trigger + reply pair to a
judge prompt asserting the "Expected" column, and fail the check on NO. None
of these are automated yet; this table is the spec to automate against.

## Quantitative bar (query in `docs/socratic-tutor-plan.md`)

Run after any core-turn session:

```sql
SELECT r.prompt_slug, r.model, COUNT(*) n,
  CAST(AVG(LENGTH(m.content)-LENGTH(REPLACE(m.content,' ',''))+1) AS INT) avg_words,
  MAX(LENGTH(m.content)-LENGTH(REPLACE(m.content,' ',''))+1) max_words
FROM runs r JOIN messages m ON m.id = r.assistant_message_id
WHERE r.created_at >= '<session start>' AND r.prompt_slug='course-session-core'
GROUP BY r.prompt_slug, r.model;
```

- `avg_words` ≤ 80, `max_words` ≤ 150 — except turns following an explicit
  depth request (row 7 below), which may run longer.
- Every `course-session-core` reply ends with exactly one question.
- No reply opens with "Great!", "Perfect!", "Exactly right!", "Great question!".
- No `## Headers`, no bold labels ("Takeaway:", "Here's how it works:"), no
  bullet lists unless the student explicitly asked for a comparison.

## Turn-shape scenarios (course-session-core)

| # | Trigger (student reply) | Expected tutor behavior | Fails if |
|---|---|---|---|
| 1 | Confirms session length ("Yes, that works") — the non-material opening reply | Starts the module directly with a question. No re-introduction, no restating the module list. | Reply opens with a greeting/intro instead of teaching content. |
| 2 | Fully correct answer | Names the precise part they got right in a few words; does **not** repeat the answer back or illustrate it; adds the next layer; ends with exactly one question. | Reply restates the student's answer, adds a "Takeaway:"-style recap, or asks zero/multiple questions. |
| 3 | Partly correct answer | Names what holds, then plainly corrects the one piece that doesn't; one question. | Reply is vague about which part was wrong, or corrects everything without crediting what held. |
| 4 | Wrong answer | Corrects kindly and directly; gives a hint, not the answer; re-asks from a different angle. | Reply gives the answer outright, or is evasive about the mistake. |
| 5 | "I don't know" / a brand-new idea | Explains the one idea in 2–3 sentences (using something from the student's stated work/background if available); checks it with a question. | Reply lectures at length, or skips the check-in question. |
| 6 | A direct question from the student | Answers it directly and briefly first, then hands back with a question. | Reply deflects the question, or answers without handing back. |
| 7 | Explicit depth request ("explain more", "give me an example", "in depth") | May run longer than the ~60-word budget for this one reply; returns to short turns after. | Every subsequent reply stays long (budget never resets). |
| 8 | A reply that contains a duration-shaped phrase that **isn't** a session-length request (e.g. "it took me about 5 minutes to get this") | `session_length_minutes` is unchanged (see `session-length-extraction` prompt). | Session length is misread from incidental content. |

## Closure scenarios (course-session-closure + closure-continuation)

| # | Trigger | Expected behavior | Fails if |
|---|---|---|---|
| 9 | Objective guard latches (module clearly demonstrated) while time remains | Next turn is `course-session-closure`; the guard only fires at/after `objective_guard_min_turns(session_length_minutes)` learner turns (`app/learning/objective_guard.py` — floor 4, ~1 turn per 2 planned minutes). | Guard fires before the scaled minimum, or never fires on a long session. |
| 10 | Learner agrees to stop, or asks one quick clarifying question in the closure turn | Brief goodbye, or a brief direct answer, then close out — no repeat of the full summary. | Reply repeats the whole wrap-up summary, or ignores the clarifying question. |
| 11 | Learner clearly asks to keep going in the closure turn (e.g. "actually can we keep going, I have more time") | **This reply** (still generated by the closure prompt) is warm and short, does not repeat the summary, does not re-explain that it was about to close. The **next** turn resolves back to `course-session-core` with real teaching content — `objective_met` cleared and `session_length_minutes` extended (`app/learning/closure_continuation.py`, `CONTINUE_EXTENSION_MINUTES`). | Reply reads as a cutoff ("we're out of time"); or the next turn stays in closure; or the DB flags aren't updated. |
| 12 | Learner's closure reply contains a continuation-shaped word but isn't actually asking to continue (e.g. "actually, thanks, that's enough for today") | Stays in closure — the cheap regex pre-filter over-matches on purpose, but the model call must correctly say NO. | `objective_met` gets cleared on a reply that wasn't really asking to continue. |

## Verified runs

- **2026-09-17** — Step 1 rewrite of `course-session-core`, scenarios 1–8, live
  browser session (RAG/fintech course). All passed except guard-timing (row 9
  fired at the old fixed floor of 4 turns on a 15-minute session — expected
  and fixed same day by the dynamic-min-turns change). See
  `docs/socratic-tutor-plan.md` for the before/after word-count metric.
- **2026-09-17** — Dynamic min-turns (row 9) and closure-continuation
  (rows 10–12) added; verified via `tests/test_objective_guard.py`,
  `tests/test_closure_orchestration.py`, `make smoke` (11/11), and one live
  API run of scenario 11 end-to-end (closure invite → continue reply →
  DB unlatch + extend 15→25min → next turn resumes core).
