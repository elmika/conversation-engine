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
from app.learning.closure_continuation import (
    CONTINUE_EXTENSION_MINUTES,
    mentions_continue_intent,
    parse_continue_result,
)
from app.learning.framing_answer_check import parse_framing_answer_result
from app.learning.lesson_flow import (
    LessonPhase,
    is_lesson_flow,
    phase_for_turn,
    resolve_phase_prompt,
)
from app.learning.objective_guard import objective_guard_min_turns, parse_objective_result
from app.learning.session_length import (
    is_time_over,
    mentions_duration,
    parse_extracted_minutes,
    parse_session_length_minutes,
)
from app.learning.setup_flow import (
    FRAMING_TURNS,
    SetupPhase,
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
        uow: Optional[UnitOfWork] = None,
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
            framing_required = (conv_meta or {}).get("framing_turns_required") or FRAMING_TURNS
            phase = setup_phase_for_turn(total_user_turns, framing_required)

            # The turn that CROSSES the threshold (total_user_turns first reaches
            # framing_required) is exactly the one maybe_extend_framing_turns can't
            # protect: that post-turn hook only bumps the requirement for turns
            # *after* the one it inspects, but if the crossing turn itself is a
            # clarifying question rather than an answer, OUTLINE already fired for
            # it before any post-turn hook runs — there's no later turn left to
            # correct. So check synchronously, but only exactly at the boundary
            # (`==`, not `>=`) — once OUTLINE has legitimately started, later
            # refinement replies ("can we review this?") must never be run through
            # this check again, or a normal follow-up turn would wrongly re-lock
            # framing. Real-world case that motivated this (2026-09-17): a
            # clarifying question landed exactly on turn 4 of 4 and jumped straight
            # to the outline, skipping the session-length question entirely.
            if phase is SetupPhase.OUTLINE and total_user_turns == framing_required:
                question, answer = self._last_exchange((history or []) + (pending_messages or []))
                try:
                    answered = not answer or self._reply_answered_pending_question(question, answer)
                except Exception:
                    # Fail open, like every other best-effort hook in this file — a
                    # classifier failure must never break the turn itself.
                    logger.exception(
                        "Threshold-turn framing-answer check failed; treating reply as answered"
                    )
                    answered = True
                if not answered:
                    conversation_id = (conv_meta or {}).get("id")
                    if conversation_id:
                        new_required = framing_required + 1
                        if uow is not None:
                            # Reuse the caller's already-open transaction — opening a
                            # second one here (self._uow_factory()) nests a BEGIN on
                            # top of the caller's, which deadlocks against the
                            # in-memory test DB's single shared connection. The
                            # caller commits this write along with the rest of the
                            # turn's writes.
                            uow.repo.set_framing_turns_required(
                                conversation_id, self._user_id, new_required
                            )
                        else:
                            with self._uow_factory() as fresh_uow:
                                fresh_uow.repo.set_framing_turns_required(
                                    conversation_id, self._user_id, new_required
                                )
                                fresh_uow.commit()
                        logger.info(
                            "Setup turn for %s didn't answer the pending framing question "
                            "at the threshold turn — framing now requires %d turns",
                            conversation_id, new_required,
                        )
                    phase = SetupPhase.FRAMING

            return resolve_setup_phase_prompt(flow_slug, phase)

        return flow_slug

    def _reply_answered_pending_question(self, question: str, answer: str) -> bool:
        """Cheap-model check: did `answer` actually answer `question`? Used both here
        (synchronously, only at the framing threshold turn) and by
        maybe_extend_framing_turns (post-turn, for earlier turns)."""
        record = self._prompt_repo.get_prompt("framing-answer-check")
        if record is None:
            return True  # fail open — never spuriously block a real turn
        exchange = [
            {"role": "assistant", "content": question},
            {"role": "user", "content": answer},
        ]
        result = self._llm.complete(record["system_prompt"], exchange, model=record.get("model"))
        return parse_framing_answer_result(result["text"])

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
          2. skip while still early (< objective_guard_min_turns(session_len)) — no premature close;
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
            min_turns = objective_guard_min_turns(session_len)
            if sum(1 for m in messages if m["role"] == "user") < min_turns:
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

    def maybe_resume_from_closure(self, conversation_id: str) -> None:
        """After a turn, check whether the learner asked to keep going past closure.

        Closure is a suggestion, not a cutoff (prompts/course-session-closure.md).
        Best-effort and advisory, mirroring maybe_update_session_length:
          1. skip non-lesson conversations;
          2. skip unless the turn that just ran was actually CLOSURE (time-over
             or objective-met) — nothing to resume from otherwise;
          3. cheap regex pre-filter on the learner's reply;
          4. cheap-model extraction over the closure invite + learner reply → YES/NO;
          5. on YES: un-latch objective_met and add CONTINUE_EXTENSION_MINUTES to
             the session length, so the *next* turn resolves back to CORE.
        Never raises — a failure leaves the conversation in CLOSURE.
        """
        try:
            with self._uow_factory() as uow:
                conv = uow.repo.get_conversation(conversation_id, self._user_id)
                if not conv or conv.get("session_length_minutes") is None:
                    return
                created_at = uow.repo.get_conversation_created_at(conversation_id)
                messages = uow.repo.get_messages(conversation_id, self._user_id)

            session_len = conv.get("session_length_minutes")
            time_over = bool(
                created_at and session_len
                and is_time_over(self._elapsed_minutes(created_at), session_len)
            )
            if not (time_over or conv.get("objective_met")):
                return  # the turn that just ran wasn't closure — nothing to resume from

            question, answer = self._last_exchange(messages)
            if not mentions_continue_intent(answer):
                return

            record = self._prompt_repo.get_prompt("closure-continue-extraction")
            if record is None:
                return
            exchange = [
                {"role": "assistant", "content": question},
                {"role": "user", "content": answer},
            ]
            result = self._llm.complete(
                record["system_prompt"], exchange, model=record.get("model")
            )
            if not parse_continue_result(result["text"]):
                return

            # Anchor the extension to elapsed time, not just the old target: if the
            # learner took a while to reply while time was already up, session_len
            # + CONTINUE_EXTENSION_MINUTES could still be in the past and re-close
            # on the very next turn.
            elapsed = self._elapsed_minutes(created_at) if created_at else session_len
            new_length = int(max(session_len, elapsed) + CONTINUE_EXTENSION_MINUTES)

            with self._uow_factory() as uow:
                uow.repo.clear_objective_met(conversation_id, self._user_id)
                uow.repo.update_session_length(conversation_id, self._user_id, new_length)
                uow.commit()
            logger.info(
                "Learner asked to continue past closure for %s — resuming core, length %s -> %s",
                conversation_id, session_len, new_length,
            )
        except Exception:
            logger.exception("Closure-continuation check failed; staying in closure")

    @staticmethod
    def _elapsed_minutes(created_at: datetime) -> float:
        """Minutes elapsed since the conversation (session) started."""
        start = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - start).total_seconds() / 60.0)

    def maybe_extend_framing_turns(self, conversation_id: str) -> None:
        """After a setup-flow turn that's still (or was) below the framing
        threshold, check whether the reply actually answered the pending framing
        question; if not, buy one more real framing turn — catches a detour
        happening BEFORE the threshold turn, so the raw count doesn't reach its
        threshold too early relative to how many real questions were actually
        answered. (The complementary case — the threshold-crossing turn itself
        being a detour — is caught synchronously in resolve_effective_prompt,
        since by the time this post-turn hook runs, OUTLINE has already fired
        for that exact turn and there's nothing left here to correct.)

        Best-effort and advisory, mirroring maybe_update_session_length:
          1. skip non-setup-flow conversations;
          2. skip once framing is already complete for this turn (recompute the
             SAME deterministic phase decision the turn used) — nothing to
             correct once OUTLINE has already fired for this conversation;
          3. cheap-model check over the pending question + the learner's reply
             → YES (answered) / NO (wasn't an answer);
          4. on NO, bump framing_turns_required by 1, so the flow needs one
             more real framing turn before it can advance to OUTLINE.
        Never raises — a failure leaves the framing turn count unchanged.
        """
        try:
            with self._uow_factory() as uow:
                conv = uow.repo.get_conversation(conversation_id, self._user_id)
                if not conv:
                    return
                flow_slug = conv.get("prompt_slug")
                if not flow_slug or not is_setup_flow(flow_slug):
                    return
                messages = uow.repo.get_messages(conversation_id, self._user_id)

            total_user_turns = sum(1 for m in messages if m["role"] == "user")
            required = conv.get("framing_turns_required") or FRAMING_TURNS
            if setup_phase_for_turn(total_user_turns, required) != SetupPhase.FRAMING:
                return  # already at/past the outline phase — too late to correct here

            question, answer = self._last_exchange(messages)
            if not answer or self._reply_answered_pending_question(question, answer):
                return  # answered normally — nothing to correct

            new_required = required + 1
            with self._uow_factory() as uow:
                uow.repo.set_framing_turns_required(conversation_id, self._user_id, new_required)
                uow.commit()
            logger.info(
                "Learner reply for %s didn't answer the pending framing question — "
                "framing now requires %d turns",
                conversation_id, new_required,
            )
        except Exception:
            logger.exception("Framing-answer check failed; leaving framing turn count unchanged")

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
