"""Learning DB facade — re-exports split modules for stable imports."""

from quicklingo.db.learning_cards import *  # noqa: F403
from quicklingo.db.learning_decks import *  # noqa: F403
from quicklingo.db.learning_due import *  # noqa: F403
from quicklingo.db.learning_models import *  # noqa: F403
from quicklingo.db.learning_quiz import *  # noqa: F403
from quicklingo.db.learning_reviews import *  # noqa: F403
from quicklingo.db.learning_schema import init_learning_tables  # noqa: F401
