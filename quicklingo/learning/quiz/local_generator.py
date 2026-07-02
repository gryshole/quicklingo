from __future__ import annotations

from quicklingo.i18n import tr
from quicklingo.learning.quiz.distractors import pick_quiz_choices
from quicklingo.learning.quiz.fill_blank import best_fill_blank_example, blank_word
from quicklingo.learning.quiz.models import QuizQuestion, QuizQuestionType, QuizWordDto
from quicklingo.learning.tts.text import prepare_text_for_tts

_QUESTION_TYPES = (
    QuizQuestionType.FILL_BLANK,
    QuizQuestionType.DEFINITION_MATCH,
    QuizQuestionType.TRANSLATION_RECALL,
)


class LocalQuizGenerator:
    def build_questions(self, words: list[QuizWordDto]) -> list[QuizQuestion]:
        if not words:
            return []
        pool = [word.english for word in words]
        questions: list[QuizQuestion] = []
        for index, word in enumerate(words):
            qtype = _QUESTION_TYPES[index % len(_QUESTION_TYPES)]
            example_sentence: str | None = None
            if qtype == QuizQuestionType.FILL_BLANK:
                example_sentence = best_fill_blank_example(word)
            choices = pick_quiz_choices(
                correct=word.english,
                distractors=word.distractors,
                pool=pool,
                pos=word.hint_pos,
                examples=word.examples,
                definition=word.definition,
                example_sentence=example_sentence,
                check_examples=qtype == QuizQuestionType.FILL_BLANK,
            )
            prompt_text, prompt_hint = _build_prompt_parts(
                qtype,
                word,
                example_sentence=example_sentence,
            )
            prompt_spoken, answer_spoken = _spoken_text_parts(
                qtype,
                word,
                example_sentence=example_sentence,
            )
            questions.append(
                QuizQuestion(
                    index=index,
                    type=qtype,
                    prompt_html="",
                    prompt_text=prompt_text,
                    prompt_hint=prompt_hint,
                    choices=choices,
                    correct_english=word.english,
                    source_card_id=word.card_id,
                    prompt_spoken_text=prompt_spoken,
                    answer_spoken_text=answer_spoken,
                )
            )
        return questions


def _spoken_text_parts(
    qtype: QuizQuestionType,
    word: QuizWordDto,
    *,
    example_sentence: str | None = None,
) -> tuple[str, str]:
    answer = word.english.strip()
    if qtype == QuizQuestionType.TRANSLATION_RECALL:
        return "", answer
    if qtype == QuizQuestionType.FILL_BLANK:
        sentence = example_sentence or best_fill_blank_example(word)
        blanked = blank_word(sentence, word.english)
        prompt = prepare_text_for_tts(blanked.strip() or sentence.strip())
        return prompt, prepare_text_for_tts(sentence.strip())
    definition = (word.definition or "").strip()
    return definition, answer


def _build_prompt_parts(
    qtype: QuizQuestionType,
    word: QuizWordDto,
    *,
    example_sentence: str | None = None,
) -> tuple[str, str]:
    if qtype == QuizQuestionType.FILL_BLANK:
        sentence = example_sentence or best_fill_blank_example(word)
        blanked = blank_word(sentence, word.english)
        return blanked, tr("learning.quiz_prompt_fill_blank")
    if qtype == QuizQuestionType.DEFINITION_MATCH:
        return (word.definition or word.english).strip(), tr("learning.quiz_prompt_definition")
    return word.ukrainian.strip(), tr("learning.quiz_prompt_translation")
