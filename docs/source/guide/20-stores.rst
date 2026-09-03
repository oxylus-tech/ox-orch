Stores
======

:py:class:`~ox_orch.core.stores.Store` provide generic multi-backend data storage, mapping to/from pydantic models. We currently only implement two stores:

- :py:class:`ox_orch.core.stores.MemoryStore`: keep data in memory;
- :py:class:`ox_orch.core.stores.FileStore`: store data in files;

Stores expect to handle multiple items that are pydantic models, where each item shall have a unique key attribute (defaults to ``id``).


In practice
-----------

.. code-block:: python

    from ox_orch.core import MemoryStore
    from ox_orch.operations import Operation

    store = MemoryStore(
        model_class=Operation,
        # Optional: provide unique item's lookup key
        # key="id",
        # Optional: if you want to already provide custom items
        items=[Operation(id="op-test-1")]
    )

    # Get an item by key
    store.get("op-test-1")

    # Iterate over all keys
    for item in store.all():
        print(item.id)

Batch updates:

.. code-block:: python

    # Update items from the provided iterable, here a generator.
    # It overrides existing data.
    store.commit(
        Operation(id=f"op-test-{i}") for i in range(0,10)
    )

    # Partially update items from the provided dict of values.
    store.partial_commit(
        {
            f"op-test-{i}": {"value":i}
                for i in range(0,10)
        }
    )

    # Partially update items from the provided dict of values, allowing
    # to create new ones if missing.
    store.partial_commit(
        {
            f"OP-{i}": {"value": i}
                for i in range(0, 10)
        },
        allow_create=True
    )

    # You can also delete using partial commit, by assigning None...
    store.partial_commit({"OP-1": None})
    # ... or using delete
    store.delete("OP-2")


Loading and saving
------------------

The :py:class:`~ox_orch.core.stores.Store` provides two methods empty by default: ``load`` and ``save``. What it assumes is that data are not directly written on the disk (or whatever static memory), but instead are explicitely loaded and saved.

Currently only file storage is supported, using the :py:class:`~ox_orch.core.stores.FileStore` class. This class has a :py:attr:`~ox_orch.core.stores.FileStore.backend` attribute that handle de-serialization. Here again, :py:mod:`~ox_orch.core.files` module provides support for JSON (default), and YAML formats.

Example:

.. code-block:: python

    from ox_orch.core import FileStore, YAMLBackend

    # Example using YAML
    store = FileStore(
        "./path/to/file.yaml",
        model_class=Operation,
        # Optional: defaults to JSONBackend
        backend=YAMLBackend(),
    )

    # Load data from disk
    store.load()

    # Save data to disk
    store.save()
