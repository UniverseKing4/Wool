"""Persistent configuration management.

Stores provider credentials and active selections in
``~/.config/wool/config.json``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Self

CONFIG_DIR: Path = Path.home() / ".config" / "wool"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"


@dataclass
class ProviderConfig:
    """A single AI-provider entry."""

    name: str
    base_url: str
    api_key: str
    default_model: str | None = None


@dataclass
class WoolConfig:
    """Root configuration object."""

    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    active_provider: str | None = None
    active_model: str | None = None
    active_session: str | None = None
    last_session: str | None = None
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)

    # ── persistence ───────────────────────────────────────────────────────

    @classmethod
    def load(cls) -> Self:
        """Load config from disk, returning defaults if the file is absent."""
        if not CONFIG_FILE.exists():
            return cls()
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()

        providers: dict[str, ProviderConfig] = {}
        for name, pdata in raw.get("providers", {}).items():
            providers[name] = ProviderConfig(
                name=pdata.get("name", name),
                base_url=pdata.get("base_url", ""),
                api_key=pdata.get("api_key", ""),
                default_model=pdata.get("default_model"),
            )
        return cls(
            providers=providers,
            active_provider=raw.get("active_provider"),
            active_model=raw.get("active_model"),
            active_session=raw.get("active_session"),
            last_session=raw.get("last_session"),
            mcp_servers=raw.get("mcp_servers", {}),
        )

    def save(self) -> None:
        """Persist current config to ``~/.config/wool/config.json``."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "providers": {n: asdict(p) for n, p in self.providers.items()},
            "active_provider": self.active_provider,
            "active_model": self.active_model,
            "active_session": self.active_session,
            "last_session": self.last_session,
            "mcp_servers": self.mcp_servers,
        }
        temp_path = CONFIG_FILE.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(CONFIG_FILE)

    # ── helpers ───────────────────────────────────────────────────────────

    def add_provider(self, config: ProviderConfig) -> None:
        self.providers[config.name] = config
        if self.active_provider is None:
            self.active_provider = config.name
        self.save()

    def remove_provider(self, name: str) -> None:
        self.providers.pop(name, None)
        if self.active_provider == name:
            self.active_provider = next(iter(self.providers), None)
        self.save()

    def get_active_provider(self) -> ProviderConfig | None:
        if self.active_provider and self.active_provider in self.providers:
            return self.providers[self.active_provider]
        return None
