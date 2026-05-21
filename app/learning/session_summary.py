"""Session summary builder — Layer 2.

Reads course and progress content via the SlotResolver port and assembles
the summary shown to the learner at session end. No LLM, no I/O beyond
the resolver call.
"""

import re
from typing import Optional

from app.application.ports import SlotResolver


def build_session_summary(slot_resolver: SlotResolver) -> dict:
    """Extract session summary from course and progress content.

    Returns: {course_name: str|None, modules: list[str], next_step: str|None}
    """
    course_name: Optional[str] = None
    modules: list[str] = []

    course_content = slot_resolver.resolve("course")
    if course_content:
        lines = course_content.splitlines()
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            if title.lower().startswith("course: "):
                title = title[8:].strip()
            course_name = title or None
        for line in lines:
            m = re.match(r"^\d+\.\s+(.+)$", line.strip())
            if m:
                modules.append(m.group(1).strip())

    next_step: Optional[str] = None
    progress_content = slot_resolver.resolve("progress")
    if progress_content:
        m = re.search(
            r"## Progress - Current state\s*\n(.*?)(?:\n##|\Z)",
            progress_content,
            re.DOTALL,
        )
        if m:
            section = m.group(1).strip()
            stripped_lines = []
            for line in section.splitlines():
                s = line.strip()
                if s.startswith(("* ", "- ")):
                    s = s[2:].strip()
                if s:
                    stripped_lines.append(s)
            next_step = "\n".join(stripped_lines) or None

    return {"course_name": course_name, "modules": modules, "next_step": next_step}
