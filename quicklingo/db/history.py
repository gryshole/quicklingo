"""Translation history persistence — public API facade."""

from quicklingo.db.history_analytics import (
    count_untagged,
    get_daily_counts,
    get_direction_counts,
    get_distinct_models,
    get_distinct_tags,
    get_model_counts,
    get_stats,
    get_tag_counts,
    get_translation_stats,
)
from quicklingo.db.history_models import (
    TranslationRecord,
    format_tags,
    make_content_hash,
    parse_tags,
)
from quicklingo.db.history_repository import (
    bulk_apply_tags,
    clear_all,
    delete_by_id,
    export_csv,
    find_cached,
    get_all,
    get_recent_for_context,
    get_source_text,
    save_translation,
    search_records,
    set_starred,
    set_tags,
)
from quicklingo.db.history_schema import init_db

__all__ = [
    "TranslationRecord",
    "bulk_apply_tags",
    "clear_all",
    "count_untagged",
    "delete_by_id",
    "export_csv",
    "find_cached",
    "format_tags",
    "get_all",
    "get_daily_counts",
    "get_direction_counts",
    "get_distinct_models",
    "get_distinct_tags",
    "get_model_counts",
    "get_recent_for_context",
    "get_source_text",
    "get_stats",
    "get_tag_counts",
    "get_translation_stats",
    "init_db",
    "make_content_hash",
    "parse_tags",
    "save_translation",
    "search_records",
    "set_starred",
    "set_tags",
]
