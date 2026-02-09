from typing import Any

from django.utils.functional import Promise
from pydantic import BaseModel


__all__ = (
    "CloneBaseModel",
    "LazyTranslation",
)


class CloneBaseModel(BaseModel):
    """Pydantic BaseModel that can clone itself."""

    def clone(self, **kwargs):
        """Clone node overriding values using ``**kwargs``.

        Note that the values will be validated using ``model_validate``.
        """
        data = self.model_dump(mode="json")
        data.update(kwargs)
        return type(self).model_validate(data)


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
