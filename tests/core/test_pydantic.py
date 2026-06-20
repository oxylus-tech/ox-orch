import pytest

from ox_orch.core.pydantic import PolymorphicModel
from ox_orch.core.registry import register, Registry


TEST_REGISTRY = Registry()
TEST_REGISTRY_2 = Registry()


@register("model")
class Model(PolymorphicModel):
    __registry__ = TEST_REGISTRY

    name: str


@register("model-2")
class Model2(PolymorphicModel):
    __registry__ = TEST_REGISTRY


@register("sub-model")
class SubModel(Model):
    __type_id__ = "sub-model"

    value: str


@register("parent-model")
class ParentModel(PolymorphicModel):
    __registry__ = TEST_REGISTRY_2

    child: Model


class Unregistered(SubModel):
    pass


@pytest.fixture
def submodel():
    return SubModel(name="sub model", value="sub model value")


@pytest.fixture
def unregistered():
    return Unregistered(name="unregistered", value="unregistered value")


class TestPolymorphicModel:
    def test_registration(self):
        assert TEST_REGISTRY["model"] is Model
        assert TEST_REGISTRY["sub-model"] is SubModel
        assert Unregistered not in list(TEST_REGISTRY.values())

    def test_model_dump(self, submodel):
        assert submodel.model_dump() == {
            "__type_id__": "sub-model",
            "config": {"name": "sub model", "value": submodel.value},
        }

    def test_model_dump_no_key(self, unregistered):
        assert unregistered.model_dump() == {"name": "unregistered", "value": unregistered.value}

    def test_model_validate(self, submodel):
        assert (
            Model.model_validate({"__type_id__": "sub-model", "config": {"name": "sub model", "value": submodel.value}})
            == submodel
        )

    def test_model_validate_no_key(self, submodel):
        assert SubModel.model_validate({"name": "sub model", "value": submodel.value}) == submodel

    def test_nested_polymorphic_models(self, submodel):
        parent = ParentModel(child=submodel)

        data = parent.model_dump()
        assert data == {
            "__type_id__": "parent-model",
            "config": {
                "child": {"__type_id__": "sub-model", "config": {"name": "sub model", "value": "sub model value"}}
            },
        }

        parent_2 = ParentModel.model_validate(data)
        assert parent_2 == parent
        assert parent_2.child == parent.child
