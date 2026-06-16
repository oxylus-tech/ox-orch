import inspect
import bisect
import importlib
from typing import Any, Callable, Iterable, Type, TypeVar


__all__ = ("import_string", "merge_nested_dicts", "consume_iter", "map_or_return")


T = TypeVar("T")
K = TypeVar("K")


def load_modules(modules: list[str] | None):
    """
    Import modules so their decorators register
    operations and hooks.

    :param modules: module paths
    """
    for module in modules or []:
        importlib.import_module(module)


def import_string(ref: str, instanceof: Type | None = None, typeof: Type | None = None) -> Any:
    """
    Load and return the object provided by path.

    Path is a string composed of a module path and a module object, separated
    by a colon, as ``ox_orch.operations:Plan``.

    :param ref: the path to the object
    :param instanceof: object must be an instance of this type;
    :param typeof: object must be a subclass of this type;
    :return the object
    :raises ModuleNotFoundError: module not found.
    :raises AttributeError: object not found in the module
    :raises TypeError: if object is not the required subclass or instance.
    """

    module_path, name = ref.split(":")
    module = importlib.import_module(module_path)
    obj = getattr(module, name)

    if instanceof is not None and not isinstance(obj, instanceof):
        raise TypeError(f"The object {ref} is not an instance of {instanceof}")

    if typeof is not None and not (inspect.isclass(obj) and issubclass(obj, typeof)):
        raise TypeError(f"The object {ref} is not a subclass of {typeof}")

    return obj


def merge_nested_dicts(*dicts: Iterable[dict[Any, dict[Any, Any]]]) -> dict[Any, dict[Any, Any]]:
    """
    Merge multiple dict of dicts by keys.

    .. code-block:: python

        a = {"a": {"foo": 123, "bar": 234}, "b": {"foo": 234}}
        b = {"a": {"foo": 456}, "b": {"tee": 4567}}

        assert merge_nested_dicts(a, b) == {
            "a": {"foo": 456, "bar": 234},
            "b": {"foo": 234, "tee": 4567}
        }

    """
    result = {}
    for parent_dict in dicts:
        for key, child_dict in parent_dict.items():
            assert isinstance(child_dict, dict)

            if key not in result:
                result[key] = dict(child_dict)
            else:
                result[key].update(child_dict)
    return result


def consume_iter(iterator):
    """Consume iterator."""
    for _ in iterator:
        pass


def map_or_return(
    items: list[T],
    predicate: Callable[[T], bool],
    mapper: Callable[[T], T],
) -> list[T]:
    """
    Conditionally map items or return the original list.

    Once the first match is encountered, a new list is created:
    - matching items are transformed with ``mapper``
    - non-matching items are copied unchanged

    If no item matches the predicate, the original list instance is returned.

    :param items: source list.
    :param predicate: predicate identifying items to transform.
    :param mapper: transformation applied to matching items.
    :returns: Either the original list or a transformed copy.
    """
    result = None

    for index, item in enumerate(items):
        matches = predicate(item)

        if result is None:
            if not matches:
                continue
            result = items[:index]
        result.append(mapper(item) if matches else item)

    return items if result is None else result


def sorted_insert(
    items: list[T],
    item: T,
    key: Callable[[T], K] | None = None,
) -> None:
    """
    Insert an item into a sorted list.

    .. important::

        The list must already be sorted according to the same key.

    :param items: Sorted list.
    :param item: Item to insert.
    :param key: Optional sort key. If omitted, items are compared directly.
    """
    bisect.insort_left(items, item, key=key)


def sorted_find(
    items: list[T],
    value: T,
    *,
    key: Callable[[T], K] | None = None,
) -> int | None:
    """
    Find an item in a sorted list.

    Parameters
    ----------
    items:
        Sorted list.
    value:
        Value to search for.
    key:
        Optional sort key.

    Returns
    -------
    int | None
        Index of the item if found, otherwise None.
    """
    if key is None:
        pos = bisect.bisect_left(items, value)
        if pos < len(items) and items[pos] == value:
            return pos

        return None

    search_key = key(value)
    pos = bisect.bisect_left(items, search_key, key=key)
    if pos < len(items) and key(items[pos]) == search_key:
        return pos

    return None
