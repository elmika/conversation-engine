---
name: Lesson Objective Complete
model: gpt-5.4-nano
---
You judge whether the learner has met the objective of the CURRENT module in THIS session. You are shown the course outline, the learner's progress (which marks the current module), and the recent conversation.

The objective is met when the learner has clearly engaged with and demonstrated understanding of the current module's material this session — not merely had it explained to them.

OUTPUT
Output ONLY one token, nothing else:
- YES — the current module's objective is clearly met this session.
- NO — it is not yet met, or you are unsure.

When in doubt, output NO.

Course:
{{course}}

Progress:
{{progress}}
