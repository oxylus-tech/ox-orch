"""
This module provide all base classes and abstractions used by the ox-orch engine.

Most of the sub-modules members are reexported here.
"""

from .contexts import CONTEXT_INPUT_REGISTRY, ContextInput, ContextInputs, Context, RunContext
from .files import FileBackend, YAMLBackend, JSONBackend, JSONLBackend, GenericFileBackend
from .events import Hook, HookEmitter
from .execution import ExecutionError, ExecutionSpec, ExecutionContext, Executor, ExecutorHook, EXECUTOR_HOOK_REGISTRY
from .operation import (
    OPERATION_REGISTRY,
    STATE_REGISTRY,
    OperationState,
    Operation,
    OperationCapabilities,
)
from .registry import Registry, RegisteredClass, register
from .pydantic import PolymorphicModel
from .state import Status, State, HistoryState, TreeState, ChangeSet
from .stores import Store, MemoryStore, FileStore
from .shell import ShellExecutionError, ShellSpec, ShellResult, LocalShell, Shell, SHELL_REGISTRY
from .trace import TraceEvent, ReplayState, ExecutionReplay


__all__ = (
    # Context
    "ContextInput",
    "ContextInputs",
    "CONTEXT_INPUT_REGISTRY",
    "Context",
    "RunContext",
    # Files
    "FileBackend",
    "YAMLBackend",
    "JSONBackend",
    "JSONLBackend",
    "GenericFileBackend",
    # Events
    "Hook",
    "HookEmitter",
    # Execution
    "ExecutionError",
    "ExecutionSpec",
    "ExecutionContext",
    "Executor",
    "ExecutorHook",
    "EXECUTOR_HOOK_REGISTRY",
    # Registry
    "Registry",
    "RegisteredClass",
    "register",
    # Pydantic
    "PolymorphicModel",
    # States
    "Status",
    "State",
    "HistoryState",
    "TreeState",
    "ChangeSet",
    # Stores
    "Store",
    "MemoryStore",
    "FileStore",
    # Replay
    "TraceEvent",
    "ReplayState",
    "ExecutionReplay",
    # Shell
    "ShellExecutionError",
    "ShellSpec",
    "ShellResult",
    "LocalShell",
    "Shell",
    "Local",
    "SHELL_REGISTRY",
    # Operation
    "OPERATION_REGISTRY",
    "STATE_REGISTRY",
    "OperationState",
    "Operation",
    "OperationCapabilities",
)
