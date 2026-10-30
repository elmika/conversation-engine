"""Tests for synthesise_progress: the end-of-session progress rewrite.

Regression coverage for a real production bug (2026-09-18): the wrap-up
instructions used to be read from a file (sections/progress/progress-wrap-up.md)
that lived under the gitignored, never-deployed sections/ tree — on a fresh
volume (e.g. Fly) that file simply doesn't exist, so every synthesis call threw
FileNotFoundError, was silently swallowed (best-effort by design), and every
learner's progress stayed on the seeded "Begin Module 1..." text forever, no
matter how much they covered. Moved to the same DB-seeded PromptRepo every
other prompt uses (prompts/progress-wrap-up.md), which is what these tests
pin down.
"""

from pathlib import Path

from app.application.ports import LLMResult
from app.learning.progress_synthesis import synthesise_progress


class FakePromptRepo:
    def __init__(self, prompts: dict) -> None:
        self._prompts = prompts

    def get_prompt(self, slug: str):
        return self._prompts.get(slug)


class RecordingLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list = []

    def complete(self, instructions, messages, model=None) -> LLMResult:
        self.calls.append((instructions, messages, model))
        return LLMResult(
            text=self.text,
            model=model or "fake",
            ttfb_ms=0,
            total_ms=0,
            input_tokens=0,
            output_tokens=0,
        )


class FakeSlotResolver:
    def __init__(self, progress_text: str) -> None:
        self._progress_text = progress_text

    def resolve(self, tag: str):
        if tag == "progress":
            return self._progress_text
        return None


def test_writes_new_progress_when_prompt_is_registered(tmp_path: Path) -> None:
    prompt_repo = FakePromptRepo(
        {
            "progress-wrap-up": {
                "slug": "progress-wrap-up",
                "system_prompt": "Update the progress: {{progress}}",
                "model": "gpt-5.6-luna",
            },
        }
    )
    llm = RecordingLLM("## Progress - Current state\nNext, we'll move on to Module 2.")
    sections_dir = str(tmp_path)
    (tmp_path / "progress").mkdir()
    (tmp_path / "progress" / "user-1.md").write_text("old progress", encoding="utf-8")

    synthesise_progress(
        messages=[{"role": "user", "content": "hi"}],
        slot_resolver=FakeSlotResolver("old progress"),
        llm=llm,
        prompt_repo=prompt_repo,
        sections_dir=sections_dir,
        wrap_up_model="gpt-5.6-luna",
        user_id="user-1",
    )

    new_content = (tmp_path / "progress" / "user-1.md").read_text(encoding="utf-8")
    assert "Module 2" in new_content
    assert len(llm.calls) == 1
    instructions, _messages, model = llm.calls[0]
    assert "old progress" in instructions  # {{progress}} tag was expanded
    assert model == "gpt-5.6-luna"


def test_archives_previous_version_before_overwriting(tmp_path: Path) -> None:
    prompt_repo = FakePromptRepo(
        {
            "progress-wrap-up": {"slug": "progress-wrap-up", "system_prompt": "go", "model": None},
        }
    )
    llm = RecordingLLM("new progress content")
    (tmp_path / "progress").mkdir()
    (tmp_path / "progress" / "user-1.md").write_text("original", encoding="utf-8")

    synthesise_progress(
        messages=[],
        slot_resolver=FakeSlotResolver("original"),
        llm=llm,
        prompt_repo=prompt_repo,
        sections_dir=str(tmp_path),
        wrap_up_model="gpt-5.6-luna",
        user_id="user-1",
    )

    archived = list((tmp_path / "progress").glob("user-1-*.md"))
    assert len(archived) == 1
    assert archived[0].read_text(encoding="utf-8") == "original"


def test_missing_prompt_leaves_progress_file_unchanged(tmp_path: Path) -> None:
    """The exact production failure mode: no 'progress-wrap-up' prompt registered.

    Must fail open (log and return) rather than raise — but critically, it must
    NOT silently leave a FileNotFoundError as the only trace forever; this test
    just pins the observable behavior (file untouched, LLM never called)."""
    prompt_repo = FakePromptRepo({})  # nothing registered — the real prod bug
    llm = RecordingLLM("should never be used")
    (tmp_path / "progress").mkdir()
    (tmp_path / "progress" / "user-1.md").write_text("seeded placeholder", encoding="utf-8")

    synthesise_progress(
        messages=[],
        slot_resolver=FakeSlotResolver("seeded placeholder"),
        llm=llm,
        prompt_repo=prompt_repo,
        sections_dir=str(tmp_path),
        wrap_up_model="gpt-5.6-luna",
        user_id="user-1",
    )

    assert llm.calls == []
    unchanged = (tmp_path / "progress" / "user-1.md").read_text(encoding="utf-8")
    assert unchanged == "seeded placeholder"


def test_real_progress_wrap_up_prompt_is_seeded() -> None:
    """The actual prompts/progress-wrap-up.md file must parse and carry the
    {{progress}} tag — this is what the DB-seeding startup step loads from."""
    import re

    content = Path("prompts/progress-wrap-up.md").read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert re.search(r"^model:\s*\S+", content, re.MULTILINE)
    assert "{{progress}}" in content
    assert "Module <N>" in content or "Module" in content
