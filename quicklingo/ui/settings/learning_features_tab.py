from PySide6.QtWidgets import QFormLayout

from quicklingo.learning.card_prompt import get_builtin_card_prompt_template
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
        "learning.daily_review",
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


_LEARNING_GROUP_SPECS: GroupSpecs = {
    "learning": (
        "settings.features.group_learning",
        [
            "learning.phrasebook",
            "learning.difficult_words",
            "learning.ai_corpus_analysis",
            "learning.anki_preview",
            "learning.anki_export",
            "learning.deck_scope",
            "learning.daily_review",
            "learning.srs_review",
            "learning.review_typing",
            "learning.card_images",
            "learning.card_pronunciation",
            "learning.streak",
            "learning.extract_vocab",
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
