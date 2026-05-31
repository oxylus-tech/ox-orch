from copy import deepcopy
from typing import Any

from django.utils.functional import Promise
from pydantic import BaseModel, model_serializer
from pydantic._internal._model_construction import ModelMetaclass


__all__ = (
    "CloneBaseModel",
    "model_registry",
    "PolymorphicModel",
    "LazyTranslation",
)


class CloneBaseModel(BaseModel):
    """Pydantic BaseModel that can clone itself."""

    def clone(self, **kwargs):
        """Clone node overriding values using ``**kwargs``.

        Note that the values will be validated using ``model_validate``.
        """
        # data = self.model_dump(mode="json")
        # print('clone self', type(self), data)
        # breakpoint()
        # obj = type(self).model_validate(data)
        obj = deepcopy(self)
        # For some reason updating data doesn't work.
        for k, v in kwargs.items():
            setattr(obj, k, v)
        return obj


model_registry = {}


class PolymorphicMeta(ModelMetaclass):
    def __new__(mcls, name, bases, attrs, **kwargs):
        key = attrs.pop("__type_id__", None)
        cls = super().__new__(mcls, name, bases, attrs, **kwargs)
        setattr(cls, "__type_id__", key)

        if key:
            if key in model_registry:
                raise ValueError(f"A model is already registered for key `{key}`: " + str(model_registry[key]))
            model_registry[key] = cls
        return cls


class PolymorphicModel(BaseModel, metaclass=PolymorphicMeta):
    """
    A Pydantic model allowing its subclasses to be de-serialized.

    At the class creation, the registry :py:class:`ModelRegistry` will be
    fullfill only if the :py:attr:`_type_id` is set.

    .. code-block:: python

        class State(PolymorphicModel):
            status: str

            __type_id__ = "state"

        class SubState(State):
            extra: str

            __type_id__ = "state:sub"

        class SomeParent(BaseModel):
            state: State

        parent = SomeParent(SubState(status="pending", extra="extra data"))

        data = parent.model_dump()
        assert data == {
            "state": {
                "__type__": "state:sub",
                "config": {"status": "pending", "extra": "extra-data"}
            }
        }

        obj = SomeParent.model_validate(data)
        assert isinstance(obj.state, SubState)
    """

    __type_id__: str = None

    @model_serializer(mode="wrap")
    def serialize(self, serializer, info) -> dict[str, Any]:
        data = serializer(self)

        def recurse(v):
            if isinstance(v, PolymorphicModel):
                return v.model_dump()
            elif isinstance(v, list):
                return [recurse(i) for i in v]
            elif isinstance(v, dict):
                return {k: recurse(val) for k, val in v.items()}
            return v

        if key := PolymorphicModel._get_model_type(type(self)):
            return {"__type_id__": key, "config": recurse(vars(self))}
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if not isinstance(obj, dict):
            raise TypeError("Data must be a dict.")
        if key := obj.get("__type_id__"):
            cl = PolymorphicModel._get_registered_model(cls, key)
            return cl(**obj.get("config"))
        return cls(**obj)

    @staticmethod
    def _get_model_type(cl):
        """Return registry key for the provided class."""
        # type_id MUST be provided as class's direct attribute
        return cl.__type_id__

    @staticmethod
    def _get_registered_model(cl, key):
        """
        Return model by key. The resulting class must be a subclass
        of the provided one.
        """
        try:
            item = model_registry[key]
            if not issubclass(item, cl):
                raise ValueError(f"For model type {key}, {item} is not a subclass of {cl}")
            return item
        except KeyError:
            raise ValueError(f"Unknown model type for: {key}")


class LazyTranslation:
    """
    This allows to pass down a lazy translation string as pydantic field.

    .. code-block:: python

        from django.utils.translation import gettext_lazy as _
        from pydantic import BaseModel
        from ox.utils.pydantic import LazyTranslation


        class MyModel(BaseModel):
            value: LazyTranslation|None = None


        obj = MyModel(value=_("Translated string"))

    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        from pydantic_core import core_schema

        def validate(v: Any):
            if isinstance(v, (str, Promise)):
                return v
            raise ValueError("Expected str or Django lazy translation")

        def serialize(v: Any):
            return str(v)

        return core_schema.no_info_plain_validator_function(
            validate, serialization=core_schema.plain_serializer_function_ser_schema(serialize, when_used="json")
        )
