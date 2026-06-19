"""Setup completion — Layer 2 close-triggered action for the setup flow.

Fires when the learner clicks "Let's start" after the setup conversation has
proposed a course outline. Runs two extraction LLM calls against the setup
conversation history:

1. user-profile-extraction → writes sections/user/<user_id>.md
2. course-outline-extraction → writes sections/course/<user_id>.md

Unlike progress synthesis, this runs SYNCHRONOUSLY (not as a BackgroundTask) —
the learner is actively waiting on the result before the first course session
can begin, and the next session's prompts require these files to exist.

Raises SetupCompletionError if extraction or file writes fail.
"""

import logging
from pathlib import Path

from app.application.ports import LLMPort, PromptRepo

logger = logging.getLogger(__name__)


class SetupCompletionError(RuntimeError):
    """Raised when setup completion fails (extraction LLM call or file write)."""


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

    try:
        user_path.parent.mkdir(parents=True, exist_ok=True)
        course_path.parent.mkdir(parents=True, exist_ok=True)
        user_path.write_text(profile_result["text"], encoding="utf-8")
        course_path.write_text(outline_result["text"], encoding="utf-8")
    except OSError as e:
        logger.exception("Setup file write failed")
        raise SetupCompletionError(f"Failed to write section files: {e}") from e

    logger.info("Setup completed for user_id=%s", user_id)


def _load_prompt(prompt_repo: PromptRepo, slug: str) -> dict:
    record = prompt_repo.get_prompt(slug)
    if record is None:
        raise SetupCompletionError(
            f"Extraction prompt '{slug}' not found in DB. Did the prompt seeding run?"
        )
    return record
