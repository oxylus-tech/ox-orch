from collections.abc import Mapping
from typing import Any, get_origin, get_args

from pydantic import BaseModel, model_serializer, model_validator

from .registry import RegisteredClass


__all__ = (
    "PolymorphicModel",
    "LazyTranslation",
)


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


    .. note::

        There are currently some limitation to polymorphic models. Currently
        you can specify nested polymorphic fields in those forms:

            - either as polymorphic single object
            - a list of polymorphic objects
            - a dict whose values are polymorphic object.


    """

    @classmethod
    def from_type(cls, type_id, **values):
        return cls.get_subclass(type_id).model_validate(values)

    @classmethod
    def get_subclass(cls, type_id):
        return cls.__registry__.get(type_id)

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

    @model_validator(mode="before")
    def _dispatch_polymorphic(cls, data: Any):
        """Intercept raw input and dispatch to the correct subclass."""
        if not isinstance(data, dict):
            return data

        type_id = data.get("__type_id__")
        if not type_id:
            return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict):
            if type_id := obj.get("__type_id__"):
                raw = obj.get("config")
                if isinstance(raw, BaseModel):
                    raw = raw.model_dump()
                raw = cls.hydrate(raw)
                return cls.from_type(type_id, **raw)
        return super().model_validate(obj, **kwargs)

    @classmethod
    def hydrate(cls, data: dict | BaseModel):
        """
        Ensure nested polymorphic model fields are correctly initialized.
        """
        if isinstance(data, BaseModel):
            return data.model_dump()

        if not isinstance(data, Mapping):
            return data

        data = dict(data)
        for name, value in data.items():
            field = cls.model_fields.get(name)
            if not field:
                continue

            annotation = field.annotation
            origin = get_origin(annotation)
            args = get_args(annotation)

            if isinstance(value, dict) and isinstance(annotation, type):
                if issubclass(annotation, PolymorphicModel):
                    data[name] = annotation.model_validate(value)

            if origin in (list, list | None) and args:
                inner = args[0]
                if isinstance(inner, type) and issubclass(inner, PolymorphicModel):
                    data[name] = [inner.model_validate(v) for v in value]
        return data

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
