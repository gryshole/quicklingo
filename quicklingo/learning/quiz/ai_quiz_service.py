from __future__ import annotations

import asyncio
from collections.abc import Callable

from quicklingo.db import learning
from quicklingo.db.learning import QuizQuestionRecord
from quicklingo.features import get_feature
from quicklingo.i18n import tr
from quicklingo.learning.quiz.eligibility import is_quiz_eligible
from quicklingo.learning.quiz.fill_blank import best_fill_blank_example, blank_word
from quicklingo.learning.quiz.fill_blank_example_fix import (
    append_discriminating_fill_blank_example,
    needs_new_fill_blank_example,
)
from quicklingo.learning.quiz.models import QuizQuestion, QuizQuestionType, QuizWordDto
from quicklingo.learning.quiz.normalize import card_to_quiz_word
from quicklingo.learning.quiz.quiz_prompts import (
    CardQuizContext,
    build_choices_user_prompt,
    is_custom_quiz_prompt,
    parse_choices_response,
    get_quiz_system_prompt,
)
from quicklingo.learning.quiz.quiz_validator import filter_valid_choices, pools_overlap_too_much
from quicklingo.learning.tts.text import prepare_text_for_tts
from quicklingo.logging.ai_requests import ai_request_scope, log_validation_retry
from quicklingo.providers.registry import ModelEntry

_QUESTION_TYPES = (
    QuizQuestionType.FILL_BLANK,
    QuizQuestionType.DEFINITION_MATCH,
    QuizQuestionType.TRANSLATION_RECALL,
)


class AiQuizService:
    async def generate_for_deck(
        self,
        deck_id: int,
        model_entry: ModelEntry,
        *,
        progress_cb: Callable[[str], None] | None = None,
        cancel_flag: Callable[[], bool] | None = None,
    ) -> learning.QuizCoverageStats:
        deck = learning.get_deck(deck_id)
        if deck is None:
            return learning.QuizCoverageStats(
                eligible=0, ready=0, missing_any=0, missing_by_type={}
            )

        cards = learning.list_cards(deck_id)
        pending: list[tuple[learning.LearningCard, QuizWordDto]] = []
        for card in cards:
            word = card_to_quiz_word(card, deck.direction)
            if not is_quiz_eligible(card, word):
                continue
            if learning.card_has_full_quiz_coverage(card.id):
                continue
            pending.append((card, word))

        total = len(pending)
        for index, (card, word) in enumerate(pending, start=1):
            if cancel_flag and cancel_flag():
                break
            if progress_cb:
                progress_cb(f"Card {index}/{total}: {word.english}")
            await self._generate_for_card(
                card,
                word,
                deck.direction,
                model_entry,
                progress_cb=progress_cb,
                cancel_flag=cancel_flag,
            )

        return learning.get_quiz_coverage(deck_id)

    async def _generate_for_card(
        self,
        card: learning.LearningCard,
        word: QuizWordDto,
        direction: str,
        model_entry: ModelEntry,
        *,
        progress_cb: Callable[[str], None] | None = None,
        cancel_flag: Callable[[], bool] | None = None,
    ) -> None:
        context = self._build_card_context(word, direction)
        saved_pools: dict[QuizQuestionType, list[str]] = {}
        prompt_version = "custom" if is_custom_quiz_prompt() else "v1"
        max_retries = int(get_feature("learning.quiz").get("generation_max_retries", 3))
        min_valid = 4
        target_size = int(get_feature("learning.quiz").get("choices_pool_size", 6))
        fill_blank_example_fix_attempted = False

        for qtype in _QUESTION_TYPES:
            if cancel_flag and cancel_flag():
                return
            existing = learning.get_quiz_question(card.id, qtype.value)
            if existing is not None and existing.status == "active":
                saved_pools[qtype] = list(existing.choices_pool)
                continue

            if progress_cb:
                progress_cb(f"{word.english}: {qtype.value}")

            if (
                qtype == QuizQuestionType.FILL_BLANK
                and not fill_blank_example_fix_attempted
                and needs_new_fill_blank_example(word.examples, word.english)
            ):
                fill_blank_example_fix_attempted = True
                if progress_cb:
                    progress_cb(f"{word.english}: adding example sentence")
                fixed = await append_discriminating_fill_blank_example(
                    card,
                    word,
                    direction,
                    model_entry,
                    cancel_flag=cancel_flag,
                )
                if fixed is not None:
                    card, word = fixed
                    context = self._build_card_context(word, direction)

            pool = await self._generate_choice_pool(
                qtype,
                context,
                word,
                model_entry,
                saved_pools=saved_pools,
                max_retries=max_retries,
                min_valid=min_valid,
                target_size=target_size,
                cancel_flag=cancel_flag,
            )

            if len(pool) < min_valid:
                learning.upsert_quiz_question(
                    card_id=card.id,
                    question_type=qtype.value,
                    prompt_text=_prompt_text_for_type(qtype, context, word),
                    example_sentence=context.fill_sentence
                    if qtype == QuizQuestionType.FILL_BLANK
                    else "",
                    choices_pool=pool,
                    correct_english=word.english,
                    status="failed",
                    model_id=model_entry.model_id,
                    prompt_version=prompt_version,
                )
                continue

            saved_pools[qtype] = pool
            learning.upsert_quiz_question(
                card_id=card.id,
                question_type=qtype.value,
                prompt_text=_prompt_text_for_type(qtype, context, word),
                example_sentence=context.fill_sentence
                if qtype == QuizQuestionType.FILL_BLANK
                else "",
                choices_pool=pool[:target_size],
                correct_english=word.english,
                status="active",
                model_id=model_entry.model_id,
                prompt_version=prompt_version,
            )

    async def _generate_choice_pool(
        self,
        qtype: QuizQuestionType,
        context: CardQuizContext,
        word: QuizWordDto,
        model_entry: ModelEntry,
        *,
        saved_pools: dict[QuizQuestionType, list[str]],
        max_retries: int,
        min_valid: int,
        target_size: int,
        cancel_flag: Callable[[], bool] | None,
    ) -> list[str]:
        fill_sentence = context.fill_sentence if qtype == QuizQuestionType.FILL_BLANK else ""
        pool: list[str] = []
        for attempt in range(max_retries):
            if cancel_flag and cancel_flag():
                return pool
            user_prompt = build_choices_user_prompt(qtype, context, choices_count=target_size)
            purpose = f"learning.quiz.choices.{qtype.value}"
            if attempt > 0:
                purpose = f"{purpose}.retry{attempt}"
            with ai_request_scope(purpose):
                raw = await model_entry.provider.complete(
                    get_quiz_system_prompt(),
                    user_prompt,
                    model_entry.model_id,
                    temperature=0.35,
                )
            candidates = parse_choices_response(raw)
            pool = filter_valid_choices(
                question_type=qtype,
                correct=word.english,
                candidates=candidates,
                examples=word.examples,
                definition=word.definition,
                example_sentence=fill_sentence,
                target_size=target_size,
            )
            trial_pools = [saved_pools[t] for t in saved_pools if saved_pools[t]]
            if pool:
                trial_pools = [*trial_pools, pool]
            if len(pool) >= min_valid and not pools_overlap_too_much(trial_pools):
                break
            if len(pool) >= min_valid and attempt == max_retries - 1:
                break
            log_validation_retry(
                purpose=purpose,
                detail=(
                    f"card={word.english} type={qtype.value} "
                    f"valid={len(pool)} attempt={attempt + 1}/{max_retries}"
                ),
            )
            await asyncio.sleep(0)
        return pool

    @staticmethod
    def _build_card_context(word: QuizWordDto, direction: str) -> CardQuizContext:
        fill_sentence = best_fill_blank_example(word)
        blanked = blank_word(fill_sentence, word.english)
        return CardQuizContext(
            english=word.english,
            ukrainian=word.ukrainian,
            definition=word.definition,
            hint_pos=word.hint_pos,
            examples=word.examples,
            direction=direction,
            fill_sentence=fill_sentence,
            blanked_sentence=blanked,
        )


def _prompt_text_for_type(
    qtype: QuizQuestionType,
    context: CardQuizContext,
    word: QuizWordDto,
) -> str:
    if qtype == QuizQuestionType.FILL_BLANK:
        return context.blanked_sentence
    if qtype == QuizQuestionType.DEFINITION_MATCH:
        return (word.definition or word.english).strip()
    return word.ukrainian.strip()


def prompt_hint_for_type(qtype: QuizQuestionType) -> str:
    if qtype == QuizQuestionType.FILL_BLANK:
        return tr("learning.quiz_prompt_fill_blank")
    if qtype == QuizQuestionType.DEFINITION_MATCH:
        return tr("learning.quiz_prompt_definition")
    return tr("learning.quiz_prompt_translation")


def spoken_text_parts(
    qtype: QuizQuestionType,
    word: QuizWordDto,
    record: QuizQuestionRecord,
) -> tuple[str, str]:
    answer = word.english.strip()
    if qtype == QuizQuestionType.TRANSLATION_RECALL:
        return "", answer
    if qtype == QuizQuestionType.FILL_BLANK:
        sentence = record.example_sentence.strip() or record.prompt_text
        prompt = prepare_text_for_tts(record.prompt_text.strip() or sentence)
        return prompt, prepare_text_for_tts(sentence.strip())
    definition = record.prompt_text.strip() or (word.definition or "").strip()
    return definition, answer


def record_to_quiz_question(
    *,
    index: int,
    word: QuizWordDto,
    qtype: QuizQuestionType,
    record: QuizQuestionRecord,
    choices: list[str],
) -> QuizQuestion:
    prompt_spoken, answer_spoken = spoken_text_parts(qtype, word, record)
    return QuizQuestion(
        index=index,
        type=qtype,
        prompt_html="",
        prompt_text=record.prompt_text,
        prompt_hint=prompt_hint_for_type(qtype),
        choices=choices,
        correct_english=record.correct_english,
        source_card_id=word.card_id,
        prompt_spoken_text=prompt_spoken,
        answer_spoken_text=answer_spoken,
        question_id=record.id,
        choices_shown=list(choices),
    )
