import pytest

from ox_orch import utils


class Model(utils.CloneBaseModel, utils.PolymorphicModel):
    __type_id__ = "model"

    name: str


class Model2(utils.PolymorphicModel):
    __type_id__ = "model-2"


class SubModel(Model):
    __type_id__ = "sub-model"

    value: str


class Unregistered(SubModel):
    pass


@pytest.fixture
def submodel():
    return SubModel(name="sub model", value="sub model value")


@pytest.fixture
def unregistered():
    return Unregistered(name="unregistered", value="unregistered value")


def test_merge_nested_dicts():
    a = {"a": {"foo": 123, "bar": 234}, "b": {"foo": 234}}
    b = {"a": {"foo": 456}, "b": {"tee": 4567}}
    assert utils.merge_nested_dicts(a, b) == {"a": {"foo": 456, "bar": 234}, "b": {"foo": 234, "tee": 4567}}


class TestCloneBaseModel:
    def test_clone(self, submodel):
        obj = submodel.clone(value="other value")
        assert obj.name == submodel.name
        assert obj.value == "other value"


class TestPolymorphicModel:
    def test__init_subclass_(self):
        assert utils.model_registry["model"] is Model
        assert utils.model_registry["sub-model"] is SubModel
        assert Unregistered not in list(utils.model_registry.values())

    def test_get_model_type(self):
        assert utils.PolymorphicModel._get_model_type(SubModel) == "sub-model"
        assert utils.PolymorphicModel._get_model_type(Unregistered) is None

    def test_get_registered_model(self):
        assert utils.PolymorphicModel._get_registered_model(Model, "sub-model") is SubModel

    def test_get_registered_model_raise_not_a_subclass(self):
        with pytest.raises(ValueError):
            utils.PolymorphicModel._get_registered_model(Model, "model-2")

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
