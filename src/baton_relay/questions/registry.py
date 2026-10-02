"""Question type registry."""

from __future__ import annotations

from typing import Any, Callable, Type

from baton_relay.questions.base import Question

_REGISTRY: dict[str, Type[Question]] = {}
_BUILDERS: dict[str, Callable[[dict[str, Any]], Question]] = {}


def register(type_name: str):
    """Decorator: register a Question subclass under a type name."""

    def deco(cls: Type[Question]):
        _REGISTRY[type_name] = cls
        return cls

    return deco


def register_builder(type_name: str, builder: Callable[[dict[str, Any]], Question]) -> None:
    _BUILDERS[type_name] = builder


def get_builder(type_name: str) -> Callable[[dict[str, Any]], Question] | None:
    if type_name in _BUILDERS:
        return _BUILDERS[type_name]
    cls = _REGISTRY.get(type_name)
    if cls is None:
        return None

    def default_builder(data: dict[str, Any]) -> Question:
        # Subclasses should register explicit builders; this is a fallback.
        raise TypeError(f"No builder for question type {type_name}")

    return default_builder


def known_types() -> list[str]:
    return sorted(set(_REGISTRY) | set(_BUILDERS))


def ensure_builtin_types_loaded() -> None:
    # Import side effects register types
    from baton_relay.questions import types as _types  # noqa: F401
