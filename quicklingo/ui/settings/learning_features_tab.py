from PySide6.QtWidgets import QFormLayout

from quicklingo.learning.card_prompt import get_builtin_card_prompt_template
from quicklingo.learning.quiz.models import QuizQuestionType
from quicklingo.learning.quiz.quiz_prompts import get_builtin_quiz_prompt, get_builtin_quiz_system_prompt
from quicklingo.ui.settings.feature_settings_editor import FeatureSettingsEditor, GroupSpecs


def _learning_limits(form: QFormLayout, editor: FeatureSettingsEditor) -> None:
    editor._add_spin_form(
        form,
        "learning.ai_corpus_analysis",
        "max_candidates",
        "settings.features.corpus_max_candidates",
        20,
        300,
    )
    editor._add_spin_form(
        form,
        "learning.ai_corpus_analysis",
        "batch_size",
        "settings.features.corpus_batch_size",
        10,
        80,
    )
    editor._add_spin_form(
        form,
        "learning.srs_review",
        "daily_limit",
        "settings.features.daily_review_limit",
        5,
        100,
    )
    editor._add_spin_form(
        form,
        "learning.srs_review",
        "desired_retention",
        "settings.features.desired_retention",
        70,
        99,
    )
    editor._add_spin_form(
        form,
        "learning.srs_review",
        "new_cards_per_day",
        "settings.features.new_cards_per_day",
        1,
        50,
    )
    editor._add_spin_form(
        form,
        "learning.card_images",
        "max_images_per_batch",
        "settings.features.max_images_per_batch",
        1,
        100,
    )
    editor._add_spin_form(
        form,
        "learning.quiz",
        "question_count",
        "settings.features.quiz_question_count",
        5,
        30,
    )
    editor._add_spin_form(
        form,
        "learning.ai_deck_generator",
        "batch_size",
        "settings.features.ai_deck_batch_size",
        5,
        20,
    )


def _learning_prompts(form: QFormLayout, editor: FeatureSettingsEditor) -> None:
    editor._add_prompt_field(
        form,
        "learning.ai_corpus_analysis",
        "card_prompt_template_ua_en",
        "settings.features.corpus_card_prompt_template_ua_en",
        reset_factory=lambda: get_builtin_card_prompt_template("ua-en"),
    )
    editor._add_prompt_field(
        form,
        "learning.ai_corpus_analysis",
        "card_prompt_template_en_ua",
        "settings.features.corpus_card_prompt_template_en_ua",
        reset_factory=lambda: get_builtin_card_prompt_template("en-ua"),
    )
    editor._add_prompt_field(
        form,
        "learning.quiz",
        "quiz_system_prompt_template",
        "settings.features.quiz_system_prompt",
        reset_factory=get_builtin_quiz_system_prompt,
        placeholder_key="settings.features.quiz_prompt_placeholder",
    )
    editor._add_prompt_field(
        form,
        "learning.quiz",
        "quiz_prompt_fill_blank",
        "settings.features.quiz_prompt_fill_blank",
        reset_factory=lambda: get_builtin_quiz_prompt(QuizQuestionType.FILL_BLANK),
        placeholder_key="settings.features.quiz_prompt_placeholder",
    )
    editor._add_prompt_field(
        form,
        "learning.quiz",
        "quiz_prompt_definition_match",
        "settings.features.quiz_prompt_definition",
        reset_factory=lambda: get_builtin_quiz_prompt(QuizQuestionType.DEFINITION_MATCH),
        placeholder_key="settings.features.quiz_prompt_placeholder",
    )
    editor._add_prompt_field(
        form,
        "learning.quiz",
        "quiz_prompt_translation_recall",
        "settings.features.quiz_prompt_translation",
        reset_factory=lambda: get_builtin_quiz_prompt(QuizQuestionType.TRANSLATION_RECALL),
        placeholder_key="settings.features.quiz_prompt_placeholder",
    )


_LEARNING_GROUP_SPECS: GroupSpecs = {
    "learning_modules": (
        "settings.features.group_learning_modules",
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
    "learning_limits": (
        "settings.features.group_learning_limits",
        [],
    ),
    "learning_prompts": (
        "settings.features.group_learning_prompts",
        [],
    ),
}


class LearningFeaturesTab(FeatureSettingsEditor):
    def __init__(self, parent=None) -> None:
        super().__init__(
            _LEARNING_GROUP_SPECS,
            group_hooks={
                "learning_limits": lambda form: _learning_limits(form, self),
                "learning_prompts": lambda form: _learning_prompts(form, self),
            },
            parent=parent,
        )
