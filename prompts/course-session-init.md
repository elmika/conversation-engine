---
name: Course Session Init
model: gpt-4.1
---
You are opening a learning session. Based on the course outline and progress below, write a short opening message that:
1. Recaps the course and shows where the learner stands in it (modules completed vs remaining)
2. Names exactly where they left off and what the next step is
3. Proposes one specific thing to do today

Be warm but brief — two short paragraphs maximum. No bullet dumps.

Course:
{{course}}

Progress:
{{progress}}
