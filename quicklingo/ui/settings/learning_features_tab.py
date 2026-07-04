from PySide6.QtWidgets import QFormLayout

from quicklingo.learning.card_prompt import get_builtin_card_prompt_template
from quicklingo.learning.quiz.models import QuizQuestionType
from quicklingo.learning.quiz.quiz_prompts import get_builtin_quiz_prompt, get_builtin_quiz_system_prompt
from quicklingo.ui.settings.feature_settings_editor import FeatureSettingsEditor, GroupSpecs


def _learning_extras(form: QFormLayout, editor: FeatureSettingsEditor) -> None:
    editor._add_spin(
        form,
        "learning.ai_corpus_analysis",
        "max_candidates",
        "settings.features.corpus_max_candidates",
        20,
        300,
    )
    editor._add_spin(
        form,
        "learning.ai_corpus_analysis",
        "batch_size",
        "settings.features.corpus_batch_size",
        10,
        80,
    )
    editor._add_text_area(
        form,
        "learning.ai_corpus_analysis",
        "card_prompt_template_ua_en",
        "settings.features.corpus_card_prompt_template_ua_en",
        reset_factory=lambda: get_builtin_card_prompt_template("ua-en"),
    )
    editor._add_text_area(
        form,
        "learning.ai_corpus_analysis",
        "card_prompt_template_en_ua",
        "settings.features.corpus_card_prompt_template_en_ua",
        reset_factory=lambda: get_builtin_card_prompt_template("en-ua"),
    )
    editor._add_spin(
        form,
        "learning.srs_review",
        "daily_limit",
        "settings.features.daily_review_limit",
        5,
        100,
    )
    editor._add_spin(
        form,
        "learning.srs_review",
        "desired_retention",
        "settings.features.desired_retention",
        70,
        99,
    )
    editor._add_spin(
        form,
        "learning.srs_review",
        "new_cards_per_day",
        "settings.features.new_cards_per_day",
        1,
        50,
    )
    editor._add_spin(
        form,
        "learning.card_images",
        "max_images_per_batch",
        "settings.features.max_images_per_batch",
        1,
        100,
    )
    editor._add_spin(
        form,
        "learning.quiz",
        "question_count",
        "settings.features.quiz_question_count",
        5,
        30,
    )
    editor._add_text_area(
        form,
        "learning.quiz",
        "quiz_system_prompt_template",
        "settings.features.quiz_system_prompt",
        reset_factory=get_builtin_quiz_system_prompt,
    )
    editor._add_text_area(
        form,
        "learning.quiz",
        "quiz_prompt_fill_blank",
        "settings.features.quiz_prompt_fill_blank",
        reset_factory=lambda: get_builtin_quiz_prompt(QuizQuestionType.FILL_BLANK),
    )
    editor._add_text_area(
        form,
        "learning.quiz",
        "quiz_prompt_definition_match",
        "settings.features.quiz_prompt_definition",
        reset_factory=lambda: get_builtin_quiz_prompt(QuizQuestionType.DEFINITION_MATCH),
    )
    editor._add_text_area(
        form,
        "learning.quiz",
        "quiz_prompt_translation_recall",
        "settings.features.quiz_prompt_translation",
        reset_factory=lambda: get_builtin_quiz_prompt(QuizQuestionType.TRANSLATION_RECALL),
    )
    editor._add_spin(
        form,
        "learning.ai_deck_generator",
        "batch_size",
        "settings.features.ai_deck_batch_size",
        5,
        20,
    )


_LEARNING_GROUP_SPECS: GroupSpecs = {
    "learning": (
        "settings.features.group_learning",
        [
            "learning.ai_corpus_analysis",
            "learning.anki_export",
            "learning.srs_review",
            "learning.card_images",
            "learning.quiz",
            "learning.ai_deck_generator",
            "learning.tts_enabled",
            "learning.tts_auto_play",
        ],
    ),
}


class LearningFeaturesTab(FeatureSettingsEditor):
    def __init__(self, parent=None) -> None:
        super().__init__(
            _LEARNING_GROUP_SPECS,
            group_hooks={"learning": lambda form: _learning_extras(form, self)},
            parent=parent,
        )
