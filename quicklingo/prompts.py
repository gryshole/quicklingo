from quicklingo.config.loader import get_prompt as _get_prompt


def get_prompt(direction: str, profile_id: str | None = None) -> str:
    return _get_prompt(direction, profile_id)
