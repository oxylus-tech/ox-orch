from typing import TypeVar


__all__ = ("OperationAbort", "StoreNotFoundError")


class OperationAbort(RuntimeError):
    """This exception is raised when the operation is aborted."""

    pass


K = TypeVar("K")


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
