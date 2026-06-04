# ox_orch/core/resolver.py

from __future__ import annotations

import importlib
from typing import Type

from ox_orch.operations.base import AbstractOperation
from ox_orch.hooks.base import ExecutorHook


class OperationResolver:
    """
    Resolves operations from different identifiers.

    Supported formats:
    - "type:op:pip_install" (preferred)
    - "module.path:ClassName"
    """

    def __init__(self, registry: dict[str, Type[AbstractOperation]] | None = None):
        self.registry = registry or {}

    def resolve(self, ref: str) -> Type[AbstractOperation]:
        """
        Resolve an operation class from a reference string.
        """

        # 1. type_id lookup
        if ref in self.registry:
            return self.registry[ref]

        # 2. module:class format
        if ":" in ref:
            try:
                module_path, class_name = ref.split(":")
                module = importlib.import_module(module_path)
                return getattr(module, class_name)
            except ModuleNotFoundError:
                pass

        raise ValueError(f"Unknown operation reference: {ref}")


class HookResolver:
    """
    Resolve hooks from string references.
    """

    def resolve(self, ref: str) -> Type[ExecutorHook]:
        module_path, class_name = ref.split(":")
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
