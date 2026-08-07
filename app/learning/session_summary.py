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

    Returns: {course_name: str|None, modules: list[{title, status}], next_step: str|None}
    `status` is "done" | "current" | "upcoming" | None (None when the Progress
    section names no module, e.g. a brand-new course with no session yet).
    """
    course_name: Optional[str] = None
    titles: list[str] = []

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
                titles.append(m.group(1).strip())

    next_step: Optional[str] = None
    current_module: Optional[int] = None
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

            # The Progress section is the sole source of truth for module status
            # (same rule the course-session-init prompt follows for the in-chat
            # module list) — the highest module number it names is the one the
            # student is currently on; anything below is done, above is upcoming.
            module_nums = [int(n) for n in re.findall(r"Module\s+(\d+)", section)]
            if module_nums:
                current_module = max(module_nums)

    modules: list[dict] = []
    for i, title in enumerate(titles, start=1):
        if current_module is None:
            status = None
        elif i < current_module:
            status = "done"
        elif i == current_module:
            status = "current"
        else:
            status = "upcoming"
        modules.append({"title": title, "status": status})

    return {"course_name": course_name, "modules": modules, "next_step": next_step}
