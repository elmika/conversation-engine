"""Progress synthesis — Layer 2 close-triggered action.

Fires at session end (registered by the route as a BackgroundTask). Calls
the LLM with the wrap-up prompt to produce an updated progress snapshot,
then writes it to disk, archiving the previous version.

This is the canonical example of a Layer 1b close-triggered action: Layer 1b
fires it, Layer 2 owns the implementation.
"""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.application.ports import LLMPort, PromptRepo, SlotResolver
from app.domain.prompt_template import resolve_file_sections

logger = logging.getLogger(__name__)


def synthesise_progress(
    messages: list[dict],
    slot_resolver: SlotResolver,
    llm: LLMPort,
    prompt_repo: PromptRepo,
    sections_dir: str,
    wrap_up_model: str,
    user_id: str = "default",
) -> None:
    """Call the LLM to produce an updated progress snapshot and write it to disk.

    Reads the wrap-up prompt from the "progress-wrap-up" prompt slug (seeded from
    prompts/progress-wrap-up.md like every other prompt — NOT a per-user section
    file, since it's a static system prompt, not learner data), renders slot tags
    via the SlotResolver, calls the LLM, and atomically replaces
    sections/progress/<user_id>.md (archiving the previous version as
    <user_id>-<timestamp>.md in the same directory).

    Errors are logged but not re-raised — a failing synthesis never blocks the learner.
    """
    try:
        record = prompt_repo.get_prompt("progress-wrap-up")
        if record is None:
            logger.error("progress-wrap-up prompt not found — progress file not updated")
            return
        raw_instructions = record["system_prompt"]
        instructions = resolve_file_sections(raw_instructions, slot_resolver.resolve)

        result = llm.complete(instructions, messages, model=wrap_up_model)
        new_progress = result["text"]

        progress_dir = Path(sections_dir) / "progress"
        user_path = progress_dir / f"{user_id}.md"
        if user_path.exists():
            archive_name = f"{user_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.md"
            shutil.copy2(str(user_path), str(progress_dir / archive_name))
        user_path.write_text(new_progress, encoding="utf-8")
    except Exception:
        logger.exception("Progress synthesis failed — progress file not updated")
