import pytest

from ox_orch.core.resolver import OperationResolver, HookResolver
from ox_orch.operations.base import AbstractOperation
from ox_orch.hooks.base import ExecutorHook


class DummyOperation(AbstractOperation):
    __type_id__ = "op:dummy"

    def _apply(self, state, **context):
        yield state

    def _rollback(self, state, **context):
        yield state


class DummyHook(ExecutorHook):
    pass


class TestOperationResolver:
    def test_resolve_from_registry(self):
        resolver = OperationResolver(registry={"op:dummy": DummyOperation})

        cls = resolver.resolve("op:dummy")
        assert cls is DummyOperation

    def test_resolve_module_class(self):
        resolver = OperationResolver()

        ref = "tests.core.test_resolvers:DummyOperation"
        cls = resolver.resolve(ref)

        assert cls is DummyOperation

    def test_resolve_unknown(self):
        resolver = OperationResolver()

        with pytest.raises(ValueError):
            resolver.resolve("unknown:op")


class TestHookResolver:
    def test_resolve_hook(self):
        resolver = HookResolver()

        ref = "tests.core.test_resolvers:DummyHook"
        cls = resolver.resolve(ref)

        assert cls is DummyHook

    def test_invalid_ref(self):
        resolver = HookResolver()

        with pytest.raises(ValueError):
            resolver.resolve("invalid-ref")
