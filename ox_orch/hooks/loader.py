# ox_orch/hooks/loader.py
import importlib

from ox_orch.hooks.base import ExecutorHook


def load_hooks(paths: list[str]) -> list[ExecutorHook]:
    """Load hooks and return hooks provided as resolve python paths.

    Paths follow this format: ``module_1.sub_mode:HookClass``.
    """
    hooks = []

    for path in paths:
        module_path, class_name = path.split(":")
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        hooks.append(cls())

    return hooks
