"""Unit tests for build_session_summary (Layer 2 — no LLM, no I/O beyond the resolver)."""

from app.infra.slot_resolver_files import FileSlotResolver
from app.learning.session_summary import build_session_summary

COURSE = """# Course: Pandas for a Python Engineer

## Modules

1. Pandas for a Python Engineer
2. Inspecting and Cleaning Real-World Fintech Data
3. Filtering, Joining, and Aggregating Transactions
"""


def _resolver(tmp_path, course=None, progress=None):
    if course is not None:
        (tmp_path / "course").mkdir()
        (tmp_path / "course" / "u1.md").write_text(course, encoding="utf-8")
    if progress is not None:
        (tmp_path / "progress").mkdir()
        (tmp_path / "progress" / "u1.md").write_text(progress, encoding="utf-8")
    return FileSlotResolver(str(tmp_path), "u1")


def test_marks_modules_done_current_upcoming_from_progress_section(tmp_path) -> None:
    progress = """## Progress - Current state
- Module 1 is complete; the next session should begin with Module 2: Inspecting and Cleaning.
"""
    resolver = _resolver(tmp_path, course=COURSE, progress=progress)
    summary = build_session_summary(resolver)

    assert summary["course_name"] == "Pandas for a Python Engineer"
    assert summary["modules"] == [
        {"title": "Pandas for a Python Engineer", "status": "done", "checklist": None},
        {
            "title": "Inspecting and Cleaning Real-World Fintech Data",
            "status": "current",
            "checklist": None,
        },
        {
            "title": "Filtering, Joining, and Aggregating Transactions",
            "status": "upcoming",
            "checklist": None,
        },
    ]


def test_first_session_marks_module_one_current(tmp_path) -> None:
    progress = """## Progress - Current state
- Begin Module 1 from the course outline this session.
"""
    resolver = _resolver(tmp_path, course=COURSE, progress=progress)
    summary = build_session_summary(resolver)

    statuses = [m["status"] for m in summary["modules"]]
    assert statuses == ["current", "upcoming", "upcoming"]


def test_no_progress_section_leaves_status_none(tmp_path) -> None:
    resolver = _resolver(tmp_path, course=COURSE, progress=None)
    summary = build_session_summary(resolver)

    assert all(m["status"] is None for m in summary["modules"])


def test_progress_section_with_no_module_mention_leaves_status_none(tmp_path) -> None:
    progress = """## Progress - Current state
- The student is doing great, keep it up.
"""
    resolver = _resolver(tmp_path, course=COURSE, progress=progress)
    summary = build_session_summary(resolver)

    assert all(m["status"] is None for m in summary["modules"])


def test_forward_looking_module_mention_does_not_advance_current_module(tmp_path) -> None:
    """Regression test for a real progress file (2026-09-29): the "Next, we'll
    continue Module 1 ..." sentence is authoritative, but the same sentence
    can also mention a *later* module in passing ("... before moving on to
    Module 2"). A naive max()-of-all-mentions parse picked up that forward
    reference and showed Module 2 as current/ready in the session summary,
    while the next session (driven by the same progress text in-context)
    correctly stayed on Module 1 — the summary overstated progress the
    learner hadn't actually made.
    """
    progress = """## Progress - Current state
This session clarified that the student considers the introductory Lesson 1
material already covered and requested a summary of the remaining work, but
no new Module 1 content was taught. Next, we'll continue Module 1 by
examining sample AI tools for practical restaurant administration and
clarifying what they can and cannot reliably do before moving on to Module 2.
"""
    resolver = _resolver(tmp_path, course=COURSE, progress=progress)
    summary = build_session_summary(resolver)

    statuses = [m["status"] for m in summary["modules"]]
    assert statuses == ["current", "upcoming", "upcoming"]


def test_move_on_to_sentence_advances_current_module(tmp_path) -> None:
    """The authoritative "Next, we'll move on to Module N" phrasing (the prompt's
    other allowed wording) should still be able to advance the current module."""
    progress = """## Progress - Current state
This session finished Module 1's practical examples. Next, we'll move on to
Module 2: Inspecting and Cleaning, starting with real fintech data.
"""
    resolver = _resolver(tmp_path, course=COURSE, progress=progress)
    summary = build_session_summary(resolver)

    statuses = [m["status"] for m in summary["modules"]]
    assert statuses == ["done", "current", "upcoming"]


def test_unchanged_checklist_after_a_session_with_no_new_sub_points(tmp_path) -> None:
    """product/use-cases/courses/session-start.md + session-end.md, "Within-module
    progress checklist" (2026-09-29): a module's 2-4 sub-points are persisted in
    the progress file as a checklist. A session that covered nothing new (pure
    meta-conversation) must render that checklist exactly as it was — 1 of 3,
    same as last time — not a vague recap that implies progress that didn't
    happen.
    """
    progress = """## Progress - Current state
Next, we'll continue Module 1 by examining sample AI tools.

## Module checklist

Module 1
- [x] What AI tools are
- [ ] Where they're reliable
- [ ] Finding fast wins
"""
    resolver = _resolver(tmp_path, course=COURSE, progress=progress)
    summary = build_session_summary(resolver)

    current = summary["modules"][0]
    assert current["status"] == "current"
    assert current["checklist"] == [
        {"title": "What AI tools are", "done": True},
        {"title": "Where they're reliable", "done": False},
        {"title": "Finding fast wins", "done": False},
    ]


def test_checklist_shows_only_the_one_newly_covered_sub_point(tmp_path) -> None:
    """A session that covered exactly one new sub-point must show only that one
    newly checked — the others keep whatever state they already had.
    """
    progress = """## Progress - Current state
Next, we'll continue Module 1 by examining where AI is and isn't reliable.

## Module checklist

Module 1
- [x] What AI tools are
- [x] Where they're reliable
- [ ] Finding fast wins
"""
    resolver = _resolver(tmp_path, course=COURSE, progress=progress)
    summary = build_session_summary(resolver)

    current = summary["modules"][0]
    assert current["checklist"] == [
        {"title": "What AI tools are", "done": True},
        {"title": "Where they're reliable", "done": True},
        {"title": "Finding fast wins", "done": False},
    ]


def test_checklist_is_none_for_modules_other_than_the_checklisted_one(tmp_path) -> None:
    progress = """## Progress - Current state
Next, we'll continue Module 1.

## Module checklist

Module 1
- [x] What AI tools are
- [ ] Where they're reliable
"""
    resolver = _resolver(tmp_path, course=COURSE, progress=progress)
    summary = build_session_summary(resolver)

    assert summary["modules"][0]["checklist"] is not None
    assert summary["modules"][1]["checklist"] is None
    assert summary["modules"][2]["checklist"] is None


def test_no_module_checklist_section_leaves_checklist_none(tmp_path) -> None:
    """Progress files written before this feature (or before a module has been
    introduced) have no "## Module checklist" section — must degrade cleanly."""
    progress = """## Progress - Current state
- Begin Module 1 from the course outline this session.
"""
    resolver = _resolver(tmp_path, course=COURSE, progress=progress)
    summary = build_session_summary(resolver)

    assert all(m["checklist"] is None for m in summary["modules"])


def test_module_titles_keep_markdown_bold_for_frontend_rendering(tmp_path) -> None:
    course = """# Course: Pandas

## Modules

1. **Pandas for a Backend Engineer** — Build a practical mental model
"""
    resolver = _resolver(tmp_path, course=course)
    summary = build_session_summary(resolver)

    assert (
        summary["modules"][0]["title"]
        == "**Pandas for a Backend Engineer** — Build a practical mental model"
    )
