from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, TypeVar, Iterable, Iterator, Type

from pydantic import BaseModel, Field, TypeAdapter


from .files import FileBackend, JSONBackend
from .pydantic import PolymorphicModel


__all__ = ("StoreMetadata", "Store", "MemoryStore", "FileStoreModel", "FileStore")


K = TypeVar("K")
V = TypeVar("V", bound=BaseModel | TypeAdapter)


class StoreNotFoundError(KeyError):
    """
    Error raised when one or multiple items couldn't be found in the store.
    """

    missing_keys: list[K]
    """ Missing items keys. """

    def __init__(self, missing_keys: list[K], msg=None, **kwargs):
        if not msg:
            msg = f"The following items could not be found: {', '.join(missing_keys)}"
        self.missing_keys = missing_keys
        super().__init__(msg, **kwargs)


class StoreMetadata(BaseModel):
    """
    Structured metadata attached to a persistent store.

    This is persisted alongside stored data and can be used for:
    - versioning
    - cache invalidation
    - debugging
    - reconciliation tracking
    """

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    version: str | None = None
    backend: str | None = None

    extra: dict[str, Any] = Field(default_factory=dict)


class Store(ABC, Generic[K, V]):
    """
    Generic key-value store abstraction.

    This is responsible for:
    - access semantics (get/commit/delete)
    - in-memory structure (not persistence)
    """

    model_class: Type[BaseModel] | None = None
    key: str = "id"

    def __init__(self, model_class: Type[BaseModel] | None = None, key: str | None = None):
        if model_class:
            self.model_class = model_class
        if key:
            self.key = key

        if not (self.model_class and self.key):
            raise ValueError("Model class or key is not provided for this store.")

        if self.key not in self.model_class.model_fields:
            raise ValueError(f"Key field `{self.key}` not found on {self.model_class.__name__}")

    @abstractmethod
    def get_metadata(self) -> StoreMetadata | None:
        """Return store metadata."""
        pass

    @abstractmethod
    def get(self, key: K, exc: bool = False) -> V | None:
        """
        Get an item by key.

        :param key: Item key.
        :param exc: If True, raises :py:class:`StoreNotFoundError`
        :raises StoreNotFoundError: item was not found and ``exc=True``
        """
        pass

    def get_all(self, keys: Iterable[K], exc: bool = False) -> list[V]:
        """
        Get items by keys.

        Default implementation loops over keys and calls :py:meth:`get`

        :param keys: Item keys.
        :param exc: If True, raises :py:class:`StoreNotFoundError`
        :raises StoreNotFoundError: item was not found and ``exc=True``
        """
        items = []
        missing = [] if exc else None

        for key in keys:
            item = self.get(key, exc=False)
            match item:
                case BaseModel():
                    items.append(item)
                case None if exc:
                    missing.append(item)

        if missing:
            raise StoreNotFoundError(missing)

        return items

    @abstractmethod
    def all(self) -> Iterator[V]:
        """Return an iterator over all stored object."""
        pass

    @abstractmethod
    def commit(self, items: Iterable[V]) -> None:
        """Update items."""
        pass

    @abstractmethod
    def partial_commit(self, updates: dict[K, dict[str, Any] | None], allow_create: bool = False, merge: bool = False):
        """
        Partial update of items, provided as dict of updates by object key.

        When the value is None, then related object is removed from the
        store.
        When object is not present, either create new one (on ``allow_create``)
        or raises a ``KeyError``.

        The different backend implementations shall not try to deep merge the objects.
        However some subclasses may want to have specific behaviors, for example
        application state want its features to merge. They can implement it, on the
        condition this behavior is enabled by the ``merge`` attribute only.


        :param updates: dict of updates to apply
        :param allow_create: allow new object creation. You must ensure in this case to provide sufficient model data.
        :param merge: allow some attributes to merge.
        """
        pass

    @abstractmethod
    def delete(self, key: K) -> None:
        """Delete item from the store."""
        pass

    def item_update(self, item: V, values: dict[str, Any] | Iterable[tuple[str, Any]], merge: bool = False):
        """
        Update an item owned by the store inplace using the provided values.

        This method does NOT commit the updated object, it only provide a method
        to implement sub-classes specific behaviors on partial commits.

        The default implementation simply update the item attributes based on the
        provided fields. It thus can be reused for other objects than the model
        instance specified on the store.

        :param item: item to update
        :param values: new values
        :param merge: see :py:meth:`partial_commit` about this argument.
        """
        if isinstance(values, dict):
            values = values.items()

        if isinstance(item, dict):
            breakpoint()

        for field, value in values:
            setattr(item, field, value)

    def get_key(self, item) -> K:
        return getattr(item, self.key)

    def load(self) -> Any:
        """
        Load to the store to permanent memory.

        Default implementation does nothing.
        """
        pass

    def save(self):
        """
        Save to the store to permanent memory.

        Default implementation does nothing.
        """
        pass


class MemoryStore(Store[K, V]):
    """Simple in-memory store implementation."""

    data: dict[K, V]

    def __init__(self, model_class: BaseModel | None = None, key: str | None = None, items: Iterable[V] | None = None):
        super().__init__(model_class, key)
        self.metadata = StoreMetadata()
        self.data = {}
        if items:
            self.commit(items)

    def get_metadata(self):
        return self.metadata

    def get(self, key: K, exc=None) -> V | None:
        # FIXME: model_copy?
        return self.data.get(key)

    def all(self) -> Iterator[V]:
        return iter(self.data.values())

    def commit(self, items: Iterable[V] | None) -> None:
        self.data.update((self.get_key(item), item) for item in items)

    def partial_commit(self, updates, allow_create: bool = False, merge: bool = False):
        for key, values in updates.items():
            if values is None:
                self.delete(key)
                continue

            if self.key in values and values[self.key] != key:
                raise ValueError(f"Inconsistent key vs payload one: {key} != {values[self.key]}")

            obj = self.data.get(key)
            if not obj:
                if not allow_create:
                    raise KeyError(f"Object not found for key: {key}")
                values = {**values, self.key: key}
                self.data[key] = self.model_class(**values)
            else:
                if isinstance(obj, dict):
                    breakpoint()
                self.item_update(obj, values, merge)

    def delete(self, key: K) -> None:
        self.data.pop(key, None)

    def __len__(self):
        return len(self.data)

    def __contains__(self, key):
        return key in self.data


class FileStoreModel(PolymorphicModel, Generic[K, V]):
    """
    Persistent representation of a Store.

    This is what is serialized to disk.
    """

    data: dict[Any, Any] = Field(default_factory=dict)
    metadata: StoreMetadata = Field(default_factory=StoreMetadata)


class FileStore(MemoryStore[K, V]):
    """
    Persistent store backed by a file backend.

    Serialization is delegated to FileBackend.
    """

    backend: FileBackend = JSONBackend(FileStoreModel)
    hydrate: bool = True

    def __init__(
        self,
        path: Path,
        model_class: Type[BaseModel] | None = None,
        *args,
        backend: FileBackend | None = None,
        **kwargs,
    ):
        super().__init__(model_class, *args, **kwargs)

        if backend:
            self.backend = backend
        self.path = path

        if not issubclass(self.backend.model_class, FileStoreModel):
            raise TypeError("File backend model class does not subclasses FileStoreModel")
        if self.backend.as_list:
            raise ValueError("File backend can not be configured for lists (as_list).")

    def load(self) -> FileStoreModel:
        if not self.path.exists():
            return

        model = self.backend.load(self.path, hydrate=self.hydrate)
        self.data = model.data
        self.metadata = model.metadata
        return model

    def save(self) -> None:
        data = self.get_save_data()
        model = self.backend.model_class(**data)
        self.backend.save(self.path, model)

    def get_save_data(self, **kwargs) -> dict[str, Any]:
        """Return FileStoreModel arguments when saving it."""
        return {"data": self.data, "metadata": self.metadata, **kwargs}
