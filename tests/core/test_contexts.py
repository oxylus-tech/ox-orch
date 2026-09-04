import pytest


from ox_orch.core import register
from ox_orch.core.contexts import ContextInput, ContextInputs

from ..conftest import DummyContext, ContextStrInput, ContextIntInput


@register("custom")
class ContextCustomInput(ContextInput):
    __context_key__ = "custom_ctx"

    value: float = 0.23

    def build_context(self, *_, **__):
        return DummyContext(value=str(self.value))


@pytest.fixture
def a_input():
    return ContextStrInput(value="a")


@pytest.fixture
def b_input():
    return ContextIntInput(value=123)


@pytest.fixture
def c_input():
    return ContextCustomInput(value=1.23)


@pytest.fixture
def context_inputs(a_input):
    a_context = a_input.build_context(context_inputs)
    return ContextInputs(inputs={"test_str_input": a_input}, contexts={"test_str_input": a_context})


class TestContextInputs:
    def test__init__sets_key_map(self, context_inputs):
        keys = {
            "test_str_input": "test_str_input",
            "test_int_input": "test_int_input",
            "custom_ctx": "custom",
        }
        assert keys == {k: context_inputs.key_map[k] for k in keys.keys()}

    def test_norm_inputs(self, context_inputs):
        raw = {"test_str_input": {"value": "a-a"}}
        inputs = context_inputs.norm_inputs(raw)
        assert inputs["test_str_input"] == ContextStrInput(value="a-a")

    def test_build(self, context_inputs, a_input, b_input):
        a_context = context_inputs.contexts["test_str_input"]
        context_inputs.inputs.update(
            {
                "test_int_input": ContextIntInput(value=123),
                "custom": ContextCustomInput(value=23.4),
            }
        )
        context_inputs.build()
        assert context_inputs.contexts["test_str_input"] is a_context
        assert context_inputs.contexts["test_int_input"] == DummyContext(value="123")
        assert context_inputs.contexts["custom_ctx"] == DummyContext(value="23.4")

    def test_resolve(self, context_inputs):
        a_context = context_inputs.contexts["test_str_input"]
        assert context_inputs.resolve("test_str_input") is a_context

        # test also the fact that b input is not provided
        b_context = context_inputs.resolve("test_int_input")
        assert b_context.value == "None"

        c_context = context_inputs.resolve("custom_ctx")
        assert c_context.value == "0.23"

    def test_build_context_with_input(self, context_inputs):
        a_context = context_inputs.build_context("test_str_input")
        assert a_context.value == "a"

    def test_build_context_without_input(self, context_inputs):
        b_context = context_inputs.build_context("test_int_input")
        assert b_context.value == "None"

    def test_build_context_without_input_raises_valueerror(self, context_inputs):
        with pytest.raises(ValueError):
            context_inputs.build_context("test_missing_input")
