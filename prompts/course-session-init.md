---
name: Course Session Init
model: gpt-4.1
---
You are opening a learning session. Respond with exactly this structure:

A markdown list of every module, one item per line, using this exact format:
- ✓ 1. Module Name
- ✓ 2. Module Name
- → 3. Module Name (current)
- 4. Module Name
- 5. Module Name

Then one sentence: exactly where to pick up today.

Then one sentence: what to do right now.

Rules: ✓ = completed, → = current module. Every module on its own list item. No prose around the list. No headers.

Course:
{{course}}

Progress:
{{progress}}
