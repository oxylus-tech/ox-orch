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

        When nesting, you MUST have a root PolymorphicModel object.


    """

    @classmethod
    def from_type(cls, type_id, **values):
        return cls.get_subclass(type_id).model_validate(values)

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

        if key := type(self).get_type_id():
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
                real_cls = cls.get_subclass(type_id)
                if isinstance(raw, BaseModel):
                    raw = raw.model_dump()
                return hydrate(real_cls, raw)
        return super().model_validate(obj, **kwargs)

    @classmethod
    def get_type_id(cl):
        """Return registry key for the provided class."""
        # type_id MUST be provided as class's direct attribute
        return cl.__dict__.get("__type_id__")


TYPE_FIELD = "__type_id__"


def hydrate(model_class: type[BaseModel], data: dict[str, Any]) -> BaseModel:
    """
    Hydrate nested polymorphic models before validating the root model.

    Supports:

    - nested polymorphic models
    - list[PolymorphicModel]
    - dict[str, PolymorphicModel]
    - deep nesting
    """

    data = _hydrate_value(model_class, data)
    return model_class.model_validate(data)


def _hydrate_value(annotation: Any, value: Any):
    """Recursively hydrate a value according to its declared type."""

    if value is None:
        return None

    origin = get_origin(annotation)

    # list[T]
    if origin is list:
        (item_type,) = get_args(annotation)
        return [_hydrate_value(item_type, item) for item in value]

    # dict[K, V]
    if origin is dict:
        _, value_type = get_args(annotation)
        return {key: _hydrate_value(value_type, item) for key, item in value.items()}

    # BaseModel subclasses
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        # Polymorphic model
        if hasattr(annotation, "__registry__"):
            if isinstance(value, dict) and TYPE_FIELD in value:
                registry = annotation.__registry__
                type_id = value[TYPE_FIELD]
                concrete = registry.get(type_id)

                if concrete is None:
                    raise ValueError(f"Unknown type '{type_id}' for registry " f"{registry.__class__.__name__}")
                annotation = concrete

        # Recurse through declared fields
        if isinstance(value, dict):
            hydrated = {}

            for field_name, field in annotation.model_fields.items():
                if field_name not in value:
                    continue
                hydrated[field_name] = _hydrate_value(
                    field.annotation,
                    value[field_name],
                )

            # preserve extra fields
            for key, val in value.items():
                if key not in hydrated:
                    hydrated[key] = val

            return annotation.model_validate(hydrated)

    return value


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
