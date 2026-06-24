from __future__ import annotations
from typing import ClassVar, Type, Iterable

from pydantic import BaseModel
from pydantic.fields import PydanticUndefined


__all__ = (
    "Registry",
    "RegisteredClass",
    "register",
    "ModelFieldInfo",
    "ModelInfo",
    "DocumentedClass",
    "DocumentedRegistry",
)


class RegisteredClass:
    """
    Base class for all registry-enabled types.

    This provides:
    - __type_id__ declaration
    - optional __registry__ binding
    """

    __type_id__: str | None = None
    __registry__: Registry | None = None

    @classmethod
    def from_type(cls, type_id, **kwargs):
        return cls.get_subclass(type_id)(**kwargs)

    @classmethod
    def get_subclass(cls, type_id):
        return cls.__registry__.get(type_id)


class Registry:
    """Stores class mappings per domain."""

    _enforce_subclass: Type[RegisteredClass] = RegisteredClass

    def __init__(self):
        self._registry: dict[str, Type] = {}

    def register(self, key: str, cls: Type):
        if not issubclass(cls, self._enforce_subclass):
            raise ValueError(f"[{key}] {cls.__name__} is not a subclass of {self._enforce_subclass.__name__}.")

        if obj := self._registry.get(key):
            raise ValueError(f"[{key} Duplicate type_id, already declared in {obj.__module__}.")
        self._registry[key] = cls

    def get(self, key: str) -> Type:
        """
        Get object by key.

        :raises ValueError: when object is not registered.
        """
        try:
            return self._registry[key]
        except KeyError:
            raise ValueError(f"Unknown type_id: {key}")

    def items(self) -> Iterable[tuple[str, Type]]:
        return self._registry.items()

    def keys(self) -> Iterable[str]:
        return self._registry.keys()

    def values(self) -> Iterable[Type]:
        return self._registry.values()

    def __getitem__(self, key: str) -> Type:
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self._registry


class ModelFieldInfo(BaseModel):
    name: str
    description: str = ""
    """ Human description of the field. """
    default: str | None = None
    """ Default value as displayed to human.

    When None, field is required.
    """

    @property
    def required(self):
        return self.default is None


class ModelInfo(BaseModel):
    """
    Provide information about a model that is registered to a :py:`DocumentedRegistry`.
    """

    type_id: str
    label: str
    description: str
    fields: list[ModelFieldInfo]

    @classmethod
    def from_model_class(cls, model: Type[DocumentedClass], skip_no_doc: bool = False) -> ModelInfo | None:
        """
        Return instance of ModelInfo using the provided model class.

        It will interpret the declared information on the model as:

        - label and description;
        - declared fields and their default value or description

        :param model: the pydantic model class;
        :param skip_no_doc: if true, skip fields not providing description;
        """
        if not model.__dict__.get("__type_id__"):
            return None

        fields = []
        for name, field in model.__pydantic_fields__.items():
            if skip_no_doc and not field.description:
                continue

            default = ""
            if field.default != PydanticUndefined:
                default = str(field.default)
            elif field.default_factory:
                default = field.default_factory.__name__

            fields.append(
                ModelFieldInfo(
                    name=name,
                    description=field.description or "",
                    default=default,
                )
            )
        return cls(
            type_id=model.__type_id__,
            label=model._label or model.__type_id__,
            description=model._description,
            fields=fields,
        )


class DocumentedClass(RegisteredClass):
    """
    Subclass to use in conjunction with a :py:class:`DocumentedRegistry`
    """

    _label: ClassVar[str]
    """ Human readable name of the object. """
    _description: ClassVar[str] = ""
    """ Human readable description of the object. """


class DocumentedRegistry(Registry):
    """
    A registry that provides human readable information about its registered classes.

    Those information can be fetched using :py:meth:`get_info`.

    Only :py:class:`DocumentedClass` subclasses can be registered here.
    """

    _enforce_subclass = DocumentedClass

    def get_infos(self, skip_no_doc: bool = False) -> list[ModelInfo]:
        """Return information about the registered elements."""
        return [
            ModelInfo.from_model_class(op_cls, skip_no_doc=skip_no_doc)
            for op_cls in self.values()
            if op_cls.__dict__.get("__type_id__")
        ]


def register(type_id: str | None = None, registry: Registry | None = None):
    """
    Decorator to register a class into a registry.

    If type_id is not provided, uses cls.__type_id__.
    If registry is not provided, uses cls.__registry__.
    """

    def decorator(cls: Type):
        resolved_id = type_id or getattr(cls, "__type_id__", None)
        if not resolved_id:
            raise ValueError(f"Missing type_id for {cls.__name__}")

        resolved_registry = registry or getattr(cls, "__registry__", None)
        if not resolved_registry:
            raise ValueError(f"Missing registry for {cls.__name__}")

        cls.__type_id__ = resolved_id
        resolved_registry.register(resolved_id, cls)
        cls.__registry__ = resolved_registry

        return cls

    return decorator
