"""Runtime configuration primitives."""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class RuntimeConfig:
    """Local runtime configuration."""

    online_mode: bool = False

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        """Create config from environment variables."""
        raw = getenv("LOCUSLAB_ONLINE_MODE", "0").strip().lower()
        return cls(online_mode=raw in {"1", "true", "yes", "on"})
