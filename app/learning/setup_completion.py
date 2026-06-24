"""Setup completion — Layer 2 close-triggered action for the setup flow.

Fires when the learner clicks "Let's start" after the setup conversation has
proposed a course outline. Runs two extraction LLM calls against the setup
conversation history:

1. user-profile-extraction → writes sections/user/<user_id>.md
2. course-outline-extraction → writes sections/course/<user_id>.md

It also seeds an initial sections/progress/<user_id>.md so the learner's first
course session can render {{progress}} (real progress is only written at session
end by progress-synthesis).

Unlike progress synthesis, this runs SYNCHRONOUSLY (not as a BackgroundTask) —
the learner is actively waiting on the result before the first course session
can begin, and the next session's prompts require these files to exist.

Raises SetupCompletionError if extraction or file writes fail.
"""

import logging
import os
from pathlib import Path

from app.application.ports import LLMPort, PromptRepo

logger = logging.getLogger(__name__)


class SetupCompletionError(RuntimeError):
    """Raised when setup completion fails (extraction LLM call or file write)."""


# Initial progress snapshot for a brand-new learner. The first course session's
# prompt (course-session-init) reads {{progress}}, but real progress is only
# written at session END by progress-synthesis — so without this seed the very
# first session would fail to render (missing section file). Matches the
# four-section structure that progress-synthesis produces, in a "nothing done
# yet, start at Module 1" starting state.
_INITIAL_PROGRESS = """\
## What the student knows
No learning sessions have been completed yet.

## Patterns to reinforce (common mistakes)
- None yet — this is the learner's first session.

## Side quests: Dynamic topics
Completed:
- None

Available:
- None

## Progress - Current state
- Begin Module 1 from the course outline this session.
"""


def complete_setup(
    messages: list[dict],
    prompt_repo: PromptRepo,
    llm: LLMPort,
    sections_dir: str,
    user_id: str,
) -> None:
    """Run profile + outline extraction against the setup conversation and write both files.

    Both LLM calls are made in sequence (not parallel) for simplicity — the total
    latency is acceptable since extraction prompts use a small model. Either failure
    is fatal: we don't want to write half the setup output.
    """
    profile_prompt = _load_prompt(prompt_repo, "user-profile-extraction")
    outline_prompt = _load_prompt(prompt_repo, "course-outline-extraction")

    try:
        profile_result = llm.complete(
            profile_prompt["system_prompt"], messages, model=profile_prompt.get("model")
        )
        outline_result = llm.complete(
            outline_prompt["system_prompt"], messages, model=outline_prompt.get("model")
        )
    except Exception as e:
        logger.exception("Setup extraction failed")
        raise SetupCompletionError(f"Extraction LLM call failed: {e}") from e

    base = Path(sections_dir)
    user_path = base / "user" / f"{user_id}.md"
    course_path = base / "course" / f"{user_id}.md"
    progress_path = base / "progress" / f"{user_id}.md"

    try:
        user_path.parent.mkdir(parents=True, exist_ok=True)
        course_path.parent.mkdir(parents=True, exist_ok=True)
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        # The user file is the has_profile signal, so it must land LAST: only once the
        # course AND the initial progress snapshot exist is the learner fully set up
        # (the first course session reads both {{course}} and {{progress}}). Each write
        # is atomic (temp + os.replace) so a partial/corrupt file is never observable.
        # If any write fails, has_profile stays false and the learner can safely retry.
        _atomic_write(course_path, outline_result["text"])
        _atomic_write(progress_path, _INITIAL_PROGRESS)
        _atomic_write(user_path, profile_result["text"])
    except OSError as e:
        logger.exception("Setup file write failed")
        raise SetupCompletionError(f"Failed to write section files: {e}") from e

    logger.info("Setup completed for user_id=%s", user_id)


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via a temp file + os.replace."""
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _load_prompt(prompt_repo: PromptRepo, slug: str) -> dict:
    record = prompt_repo.get_prompt(slug)
    if record is None:
        raise SetupCompletionError(
            f"Extraction prompt '{slug}' not found in DB. Did the prompt seeding run?"
        )
    return record
