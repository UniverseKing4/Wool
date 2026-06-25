"""Provider registry — keeps track of all configured providers."""

from __future__ import annotations

from wool.providers.base import Provider


class ProviderRegistry:
    """Manages a set of named :class:`Provider` instances."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> Provider | None:
        return self._providers.get(name)

    def remove(self, name: str) -> None:
        self._providers.pop(name, None)

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    async def close_all(self) -> None:
        for p in self._providers.values():
            try:
                await p.close()
            except Exception:
                pass
        self._providers.clear()
