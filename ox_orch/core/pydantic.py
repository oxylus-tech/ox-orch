from copy import deepcopy
from typing import Any

from pydantic import BaseModel, model_serializer

from .registry import RegisteredClass


__all__ = (
    "CloneBaseModel",
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


class PolymorphicModel(RegisteredClass, BaseModel):
    """
    A Pydantic model allowing its subclasses to be de-serialized.

    At the class creation, the registry :py:class:`ModelRegistry` will be
    fullfill only if the :py:attr:`_type_id` is set.

    .. code-block:: python

        from ox_orch.utils.registry import Registry, register


        STATE_REGISTRY = Registry()

        class State(PolymorphicModel):
            status: str

            __registry__ = STATE_REGISTRY


        @register("state:sub")
        class SubState(State):
            extra: str


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

        if key := type(self)._get_model_type(type(self)):
            return {"__type_id__": key, "config": recurse(vars(self))}
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if not isinstance(obj, dict):
            raise TypeError("Data must be a dict.")
        if key := obj.get("__type_id__"):
            cl = cls.__registry__.get(key)
            return cl(**obj.get("config"))
        return cls(**obj)

    @staticmethod
    def _get_model_type(cl):
        """Return registry key for the provided class."""
        # type_id MUST be provided as class's direct attribute
        return cl.__dict__.get("__type_id__")


class LazyTranslation:
    """
    This allows to pass down a lazy translation string as pydantic field.

    Example using Django:

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
            if isinstance(v, str) or hasattr(v, "__str__"):
                return v
            raise ValueError("Expected str or Django lazy translation")

        def serialize(v: Any):
            return str(v)

        return core_schema.no_info_plain_validator_function(
            validate, serialization=core_schema.plain_serializer_function_ser_schema(serialize, when_used="json")
        )
