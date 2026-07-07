from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str = ""
    expires_at: float = 0.0
    account_label: str = ""
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        if not self.access_token:
            return True
        if self.expires_at <= 0:
            return False
        return time.time() >= self.expires_at - 60

    def to_dict(self) -> dict[str, object]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "account_label": self.account_label,
            "token_type": self.token_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> OAuthTokens:
        expires_at = data.get("expires_at", 0.0)
        try:
            expires_at = float(expires_at)
        except (TypeError, ValueError):
            expires_at = 0.0
        return cls(
            access_token=str(data.get("access_token", "") or ""),
            refresh_token=str(data.get("refresh_token", "") or ""),
            expires_at=expires_at,
            account_label=str(data.get("account_label", "") or ""),
            token_type=str(data.get("token_type", "Bearer") or "Bearer"),
        )
