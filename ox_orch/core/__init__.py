"""
This module provide all base classes and abstractions used by the ox-orch engine.

Most of the sub-modules members are reexported here.
"""

from .contexts import CONTEXT_INPUT_REGISTRY, ContextInput, ContextInputs, Context, RunContext
from .files import FileBackend, YAMLBackend, JSONBackend, JSONLBackend
from .events import Hook, HookEmitter
from .registry import Registry, RegisteredClass, register
from .pydantic import PolymorphicModel
from .state import Status, State, HistoryState, TreeState, ChangeSet
from .stores import Store, MemoryStore, FileStore
from .shell import ShellExecutionError, ShellSpec, ShellResult, LocalShell, Shell, SHELL_REGISTRY
from .trace import TraceEvent, ReplayState, ExecutionReplay


__all__ = (
    "ContextInput",
    "ContextInputs",
    "CONTEXT_INPUT_REGISTRY",
    "Context",
    "RunContext",
    "FileBackend",
    "YAMLBackend",
    "JSONBackend",
    "JSONLBackend",
    "Hook",
    "HookEmitter",
    "Registry",
    "RegisteredClass",
    "register",
    "PolymorphicModel",
    "Status",
    "State",
    "HistoryState",
    "TreeState",
    "ChangeSet",
    "Store",
    "MemoryStore",
    "FileStore",
    "TraceEvent",
    "ReplayState",
    "ExecutionReplay",
    "ShellExecutionError",
    "ShellSpec",
    "ShellResult",
    "LocalShell",
    "Shell",
    "Local",
    "SHELL_REGISTRY",
)
