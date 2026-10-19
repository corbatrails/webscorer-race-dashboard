"""Provider registry. Add a provider by importing it here and adding it to `_REGISTRY`."""
from providers.base import Provider, RaceChoice
from providers.webscorer import PROVIDER as _WEBSCORER

_REGISTRY = {provider.name: provider for provider in (_WEBSCORER,)}


def provider_names():
    return sorted(_REGISTRY)


def get_provider(name):
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown source {name!r}. Valid sources: {', '.join(provider_names())}."
        ) from None


__all__ = ["Provider", "RaceChoice", "get_provider", "provider_names"]
