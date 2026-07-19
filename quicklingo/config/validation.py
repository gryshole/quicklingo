from __future__ import annotations

import re

from quicklingo import settings

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ValidationError(Exception):
    def __init__(self, key: str, **params: object) -> None:
        self.key = key
        self.params = params
        super().__init__(key)

    def translate(self) -> str:
        from quicklingo.i18n import tr

        return tr(self.key, **self.params)

    def __str__(self) -> str:
        return self.translate()


def validate_id(value: str, *, field: str = "ID") -> None:
    if not value or not _ID_PATTERN.match(value):
        raise ValidationError("validation.invalid_id", field=field)


def prompt_path(profile_id: str, direction_id: str) -> str:
    validate_id(profile_id, field="ID")
    validate_id(direction_id, field="ID")
    return f"prompts/{profile_id}--{direction_id}.txt"


def profiles_using_direction(direction_id: str) -> list[str]:
    from quicklingo.config.loader import get_all_profiles

    return [p.id for p in get_all_profiles() if direction_id in p.prompts]


def check_direction_deletable(direction_id: str) -> None:
    from quicklingo.config.loader import get_all_directions

    all_dirs = get_all_directions()
    enabled = [d.id for d in all_dirs if d.enabled]
    if direction_id in enabled and len(enabled) <= 1:
        raise ValidationError("validation.cannot_delete_last_direction")

    refs: list[str] = []
    for profile_id in profiles_using_direction(direction_id):
        refs.append(profile_id)
    active = settings.get_active_profiles()
    if direction_id in active:
        refs.append("active profile")

    if refs:
        raise ValidationError(
            "validation.direction_in_use",
            refs=", ".join(dict.fromkeys(refs)),
        )


def check_profile_deletable(profile_id: str) -> None:
    from quicklingo.config.loader import get_all_directions

    refs: list[str] = []
    for direction in get_all_directions():
        if direction.default_profile == profile_id:
            refs.append(f"{direction.id} (default)")
    for direction_id, active_pid in settings.get_active_profiles().items():
        if active_pid == profile_id:
            refs.append(f"active for {direction_id}")
    if refs:
        raise ValidationError("validation.profile_in_use", refs=", ".join(refs))


