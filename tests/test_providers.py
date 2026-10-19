import dataclasses

import pytest

import providers
from providers import Provider, get_provider, provider_names


def _stub(name="stub", **overrides):
    fields = dict(
        name=name,
        required_secrets={},
        requires_data_file=False,
        fetch=lambda config, secrets: {},
        normalize=lambda raw: {},
    )
    fields.update(overrides)
    return Provider(**fields)


def test_provider_is_frozen_and_list_races_defaults_to_none():
    provider = _stub()
    assert provider.list_races is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        provider.name = "other"


def test_get_provider_returns_registered_instance(monkeypatch):
    provider = _stub()
    monkeypatch.setitem(providers._REGISTRY, "stub", provider)
    assert get_provider("stub") is provider


def test_get_provider_unknown_name_lists_valid_names(monkeypatch):
    monkeypatch.setitem(providers._REGISTRY, "stub", _stub())
    with pytest.raises(ValueError) as exc:
        get_provider("nope")
    assert "'nope'" in str(exc.value)
    assert "stub" in str(exc.value)


def test_provider_names_are_sorted(monkeypatch):
    monkeypatch.setattr(providers, "_REGISTRY", {"b": _stub("b"), "a": _stub("a")})
    assert provider_names() == ["a", "b"]
