from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Any, Optional, Type

import yaml
from pydantic import BaseModel


__all__ = ("FileBackend", "YAMLBackend", "JSONBackend", "backends")


class FileBackend(ABC):
    """
    This provides the base interface to read and write files, including
    serialization and deserialization using pydantic models.

    The pydantic model can be provided though :py:attr:`model_class`. If
    not, the backend assume to be itself a model class.

    .. note::

        This class can't be used directly. You should use :py:class:`YAMLBackend`
        or :py:class:`JSONBackend` instead.

    """

    model_class: Optional[Type[BaseModel]] = None
    """ The model class to deserialize file content. """
    as_list: bool = False
    """ Save and load data as list of items. """

    def __init__(self, model_class: BaseModel, as_list: bool = False):
        self.model_class = model_class
        self.as_list = as_list

    def load(self, path: Path, **init_kwargs) -> BaseModel:
        """
        Load data from file, with extra initial arguments (overriding
        existing ones).
        """
        with open(path, encoding="utf-8") as f:
            data = self.parse(f)
            if self.as_list:
                if not isinstance(data, list):
                    raise ValueError("Read data must be a list.")

                return [self.model_class.model_validate({**init_kwargs, **dat}) for dat in data]

            return self.model_class.model_validate({**init_kwargs, **data})

    def save(self, path: Path, obj: BaseModel | list[BaseModel]):
        """Save store to the provided path."""
        if isinstance(obj, (list, tuple)):
            all(self._assert_obj_type(o) for o in obj)
        else:
            self._assert_obj_type(obj)

        with open(path, "w", encoding="utf-8") as f:
            if self.as_list:
                if not isinstance(obj, (list, tuple)):
                    obj = [obj]
                dump = [o.model_dump(mode="json") for o in obj]
            else:
                dump = obj.model_dump(mode="json")
            self.write(f, dump)

    def _assert_obj_type(self, obj):
        if not isinstance(obj, self.model_class):
            raise ValueError(f"Provided object {obj} is not a subclass of {self.model_class}")

    def append(self, path: Path, obj: BaseModel):
        """
        Optional append capability for streaming logs.
        Default implementation falls back to read-modify-write.
        """
        raise NotImplementedError

    @abstractmethod
    def parse(self, f) -> dict[str, Any]:
        """From provided opened file stream, parse and return data."""
        pass

    @abstractmethod
    def write(self, f, data: dict[str, Any] | list[dict[str, Any]]):
        """Write provided data on the specified file stream."""
        pass

    def assert_as_list(self):
        if not self.as_list:
            raise RuntimeError("Backend is_list must be True")


class YAMLBackend(FileBackend):
    """Load data saved as YAML file."""

    def append(self, path: Path, obj):
        # We avoid to reload the whole document. This however assumes the
        # document to be in the right format.
        self.assert_as_list()
        with open(path, "a", encoding="utf-8") as f:
            if isinstance(obj, (list, tuple)):
                self.write(f, [o.model_dump(mode="json") for o in obj])
            else:
                self.write(f, [obj.model_dump(mode="json")])

    def parse(self, f):
        return yaml.safe_load(f)

    def write(self, f, data: dict[str, Any] | list[dict[str, Any]]):
        yaml.dump(data, f)


class JSONBackend(FileBackend):
    """Load data saved as JSON file."""

    def append(self, path: Path, obj):
        self.assert_as_list()
        if path.exists():
            items = self.load(path)
        else:
            items = []

        if isinstance(obj, (list, tuple)):
            items.extend(obj)
        else:
            items.append(obj)
        self.save(path, items)

    def parse(self, f):
        return json.load(f)

    def write(self, f, data: dict[str, Any] | list[dict[str, Any]]):
        json.dump(data, f)


class JSONLBackend(FileBackend):
    """
    Load data saved as JSON lines file.

    This is always used for list, never for a single item.
    """

    def __init__(self, model_class):
        # Ensure to always be a list.
        super().__init__(model_class, False)

    def parse(self, f):
        return [json.loads(line) for line in f if line.strip()]

    def write(self, f, data):
        if not isinstance(data, (list, tuple)):
            data = [data]

        for item in data:
            f.write(json.dumps(item) + "\n")

    def append(self, path: Path, obj):
        with open(path, "a", encoding="utf-8") as f:
            if isinstance(obj, (list, tuple)):
                for o in obj:
                    f.write(o.model_dump_json() + "\n")
            else:
                f.write(obj.model_dump_json() + "\n")


backends = {
    "yaml": YAMLBackend,
    "json": JSONBackend,
    "jsonl": JSONLBackend,
}
""" File backends available by format name. """
