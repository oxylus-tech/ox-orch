from __future__ import annotations
from typing import Type, Iterable


__all__ = ("Registry", "RegisteredClass", "register")


class Registry:
    """Stores class mappings per domain."""

    def __init__(self):
        self._registry: dict[str, Type] = {}

    def register(self, key: str, cls: Type):
        if obj := self._registry.get(key):
            raise ValueError(f"Duplicate type_id: {key}, declared {obj.__module__}")
        self._registry[key] = cls

    def get(self, key: str) -> Type:
        """
        Get object by key.

        :raises ValueError: when object is not registered.
        """
        try:
            return self._registry[key]
        except KeyError:
            raise ValueError(f"Unknown type_id: {key}")

    def items(self) -> Iterable[tuple[str, Type]]:
        return self._registry.items()

    def keys(self) -> Iterable[str]:
        return self._registry.keys()

    def values(self) -> Iterable[Type]:
        return self._registry.values()

    def __getitem__(self, key: str) -> Type:
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self._registry


class RegisteredClass:
    """
    Base class for all registry-enabled types.

    This provides:
    - __type_id__ declaration
    - optional __registry__ binding
    """

    __type_id__: str | None = None
    __registry__: Registry | None = None


def register(type_id: str | None = None, registry: Registry | None = None):
    """
    Decorator to register a class into a registry.

    If type_id is not provided, uses cls.__type_id__.
    If registry is not provided, uses cls.__registry__.
    """

    def decorator(cls: Type):
        resolved_id = type_id or getattr(cls, "__type_id__", None)
        if not resolved_id:
            raise ValueError(f"Missing type_id for {cls.__name__}")

        resolved_registry = registry or getattr(cls, "__registry__", None)
        if not resolved_registry:
            raise ValueError(f"Missing registry for {cls.__name__}")

        cls.__type_id__ = resolved_id
        resolved_registry.register(resolved_id, cls)
        cls.__registry__ = resolved_registry

        return cls

    return decorator
