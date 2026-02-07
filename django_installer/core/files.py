from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Any, Optional, Type

import yaml
from pydantic import BaseModel


__all__ = ("FileBackend", "YAMLBackend", "JSONBackend")


class FileBackend(ABC):
    """
    This provides the base interface to read and write files, including
    serialization and deserialization using pydantic models.

    The pydantic model can be provided though :py:attr:`model_class`. If
    not, the backend assume to be itself a model class.

    .. note::

        This class can't be used directly. You should use :py:class:`YAMLFileBackend`
        or :py:class:`JSONFileBackend` instead.

    """

    model_class: Optional[Type[BaseModel]] = None
    """ The model class to deserialize into """

    def __init__(self, model_class: BaseModel):
        self.model_class = model_class

    def load(self, path: Path) -> BaseModel:
        with open(path, encoding="utf-8") as f:
            data = self.parse(f)
            return self.model_class.model_validate(data)

    def save(self, path: Path, obj: BaseModel):
        """Save store to the provided path."""
        with open(path, "w", encoding="utf-8") as f:
            dump = obj.model_dump(mode="json")
            self.write(f, dump)

    @abstractmethod
    def parse(self, f) -> dict[str, Any]:
        """From provided opened file stream, parse and return data."""
        pass

    @abstractmethod
    def write(self, f, data: dict[str, Any]):
        """Write provided data on the specified file stream."""
        pass


class YAMLBackend(FileBackend):
    """Load data saved as YAML file."""

    def parse(self, f):
        return yaml.safe_load(f)

    def write(self, f, data: dict[str, Any]):
        yaml.dump(data, f)


class JSONBackend(FileBackend):
    """Load data saved as JSON file."""

    def parse(self, f):
        return json.load(f)

    def write(self, f, data: dict[str, Any]):
        json.dump(data, f)
