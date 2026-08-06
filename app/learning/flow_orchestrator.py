"""LearningFlowOrchestrator: the concrete LearningFlowPort adapter for Layer 1b.

Owns everything ConversationService used to know about lessons and setup —
phase selection, session-length capture, and the objective guard. See
CLAUDE.md "Layer model" for the seam this implements.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

from app.application.ports import LLMPort, PromptRepo, SlotResolver, UnitOfWork
from app.domain.prompt_template import render_instructions
from app.learning.lesson_flow import (
    LessonPhase,
    is_lesson_flow,
    phase_for_turn,
    resolve_phase_prompt,
)
from app.learning.objective_guard import OBJECTIVE_GUARD_MIN_TURNS, parse_objective_result
from app.learning.session_length import (
    is_time_over,
    mentions_duration,
    parse_extracted_minutes,
    parse_session_length_minutes,
)
from app.learning.setup_flow import (
    is_setup_flow,
    resolve_setup_phase_prompt,
    setup_phase_for_turn,
)

logger = logging.getLogger(__name__)


class LearningFlowOrchestrator:
    """Learning-specific (Layer 2) turn logic, reached from ConversationService via LearningFlowPort."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        llm: LLMPort,
        prompt_repo: PromptRepo,
        slot_resolver: SlotResolver,
        user_id: str = "default",
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._prompt_repo = prompt_repo
        self._slot_resolver = slot_resolver
        self._user_id = user_id

    def resolve_effective_prompt(
        self,
        flow_slug: Optional[str],
        conv_meta: Optional[dict],
        created_at: Optional[datetime],
        history: Optional[list[dict[str, str]]],
        pending_messages: Optional[list[dict[str, str]]],
    ) -> Optional[str]:
        """Pick the phase for this turn from code-owned state, never inferred by the model:
          - lesson flow  → CLOSURE once the session's time is up (see
            session_length.is_time_over) or the objective guard latched, else CORE.
          - setup flow   → OUTLINE once the learner has answered all framing
            questions (a fixed turn count), else FRAMING.
          - flat prompts → identity (setup/admin conversations unaffected).
        """
        if flow_slug and is_lesson_flow(flow_slug):
            phase = phase_for_turn(is_opening_turn=False)
            session_len = (conv_meta or {}).get("session_length_minutes")
            time_over = bool(
                session_len and created_at
                and is_time_over(self._elapsed_minutes(created_at), session_len)
            )
            # Closure fires on either trigger: the session's time is up, or the
            # objective guard latched the current module as complete.
            if time_over or (conv_meta or {}).get("objective_met"):
                phase = LessonPhase.CLOSURE
            return resolve_phase_prompt(flow_slug, phase)

        if flow_slug and is_setup_flow(flow_slug):
            total_user_turns = sum(1 for m in (history or []) if m["role"] == "user")
            total_user_turns += sum(1 for m in (pending_messages or []) if m["role"] == "user")
            return resolve_setup_phase_prompt(flow_slug, setup_phase_for_turn(total_user_turns))

        return flow_slug

    def initial_session_length_minutes(self, flow_slug: Optional[str]) -> Optional[int]:
        """Seed the session length from the learner's profile for lesson flows.

        Flat prompts (setup/admin) have no session and store None.
        """
        if not flow_slug or not is_lesson_flow(flow_slug):
            return None
        return parse_session_length_minutes(self._slot_resolver.resolve("user"))

    def maybe_update_session_length(self, conversation_id: str) -> None:
        """Capture an in-chat "adjust session length" request and persist it.

        Runs after a subsequent (core) turn. Best-effort and advisory:
          1. skip non-lesson conversations (session_length_minutes is None);
          2. cheap regex pre-filter on the learner's reply — skip if no duration hint;
          3. cheap-model extraction over only the last tutor message + learner reply;
          4. validate/clamp — persist only a sane, explicit, changed value.
        Any failure or ambiguity leaves the stored length unchanged; this never
        raises, so it can't break the turn it follows.
        """
        try:
            with self._uow_factory() as uow:
                conv = uow.repo.get_conversation(conversation_id, self._user_id)
                if not conv or conv.get("session_length_minutes") is None:
                    return  # not a lesson session — nothing to track
                current = conv["session_length_minutes"]
                question, answer = self._last_exchange(
                    uow.repo.get_messages(conversation_id, self._user_id)
                )
            if not mentions_duration(answer):
                return

            record = self._prompt_repo.get_prompt("session-length-extraction")
            if record is None:
                return
            exchange = [
                {"role": "assistant", "content": question},
                {"role": "user", "content": answer},
            ]
            result = self._llm.complete(
                record["system_prompt"], exchange, model=record.get("model")
            )
            new_minutes = parse_extracted_minutes(result["text"])
            if new_minutes is None or new_minutes == current:
                return

            with self._uow_factory() as uow:
                uow.repo.update_session_length(conversation_id, self._user_id, new_minutes)
                uow.commit()
            logger.info(
                "Session length for %s adjusted %s → %s min",
                conversation_id, current, new_minutes,
            )
        except Exception:
            logger.exception("Session-length extraction failed; keeping current value")

    def maybe_flag_objective_complete(self, conversation_id: str) -> None:
        """Run the objective guard after a core turn; latch closure if the module is met.

        Best-effort and advisory, mirroring maybe_update_session_length:
          1. skip non-lesson conversations and ones already latched;
          2. skip while still early (< OBJECTIVE_GUARD_MIN_TURNS) — no premature close;
          3. skip if the session's time is already up (closure fires on time anyway);
          4. cheap-model guard over course + progress + recent transcript → YES/NO;
          5. on YES, latch objective_met so the next turn resolves to CLOSURE.
        Never raises — a failure leaves the objective treated as not yet met.
        """
        try:
            with self._uow_factory() as uow:
                conv = uow.repo.get_conversation(conversation_id, self._user_id)
                if not conv or conv.get("session_length_minutes") is None or conv.get("objective_met"):
                    return
                created_at = uow.repo.get_conversation_created_at(conversation_id)
                messages = uow.repo.get_messages(conversation_id, self._user_id)

            session_len = conv.get("session_length_minutes")
            if created_at and session_len and is_time_over(
                self._elapsed_minutes(created_at), session_len
            ):
                return  # already closing on time — don't spend the guard call
            if sum(1 for m in messages if m["role"] == "user") < OBJECTIVE_GUARD_MIN_TURNS:
                return

            record = self._prompt_repo.get_prompt("lesson-objective-complete")
            if record is None:
                return
            instructions = render_instructions(
                record["system_prompt"], self._slot_resolver.resolve, created_at
            )
            result = self._llm.complete(instructions, messages[-12:], model=record.get("model"))
            if not parse_objective_result(result["text"]):
                return

            with self._uow_factory() as uow:
                uow.repo.set_objective_met(conversation_id, self._user_id)
                uow.commit()
            logger.info("Objective met for %s — next turn will close", conversation_id)
        except Exception:
            logger.exception("Objective guard failed; treating objective as not met")

    @staticmethod
    def _elapsed_minutes(created_at: datetime) -> float:
        """Minutes elapsed since the conversation (session) started."""
        start = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - start).total_seconds() / 60.0)

    @staticmethod
    def _last_exchange(messages: list[dict]) -> tuple[str, str]:
        """Return (last tutor message, last learner reply) from a message list.

        Used to give the session-length extractor just enough context without the
        whole conversation. Returns empty strings if there is no learner message.
        """
        last_user = next(
            (i for i in range(len(messages) - 1, -1, -1) if messages[i]["role"] == "user"),
            None,
        )
        if last_user is None:
            return "", ""
        answer = messages[last_user]["content"]
        question = next(
            (messages[j]["content"] for j in range(last_user - 1, -1, -1) if messages[j]["role"] == "assistant"),
            "",
        )
        return question, answer
