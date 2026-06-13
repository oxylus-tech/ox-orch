from dataclasses import dataclass
from typing import Any, ClassVar, Type, Iterable


from .registry import Registry


__all__ = ("Hook", "HookEmitter")


@dataclass
class Hook:
    """
    This is base class for a registered hook.

    You can subclass and add methods with the name of events yielded
    by the emitter class.

    The :py:meth:`emit` method will check if event is supported, if so
    call the related method.
    """

    def emit(self, event, *args, **kwargs):
        if hook := getattr(self, event, None):
            hook(*args, **kwargs)


class HookEmitter:
    """Hook events emitter.

    The hooks must subclass the provided :py:attr:`hook_class`.

    It is aimed as a mixin class, so you MUST provide initial hooks and
    hook_class at init.
    """

    hook_registry: ClassVar[Registry] | None = None
    """
    Hooks registry, used to get the hooks when provided as string to :py:meth:`listen`.
    """
    hook_class: ClassVar[Type[Hook]] = Hook
    """ Supported hook class. """
    hooks: list[Hook] = None
    """ The list of hooks. """

    def emit(self, event: str, *args, **kwargs: Any):
        if not self.hooks:
            return

        for hook in self.hooks:
            hook.emit(event, *args, **kwargs)

    def listen(self, hooks: Hook | str | Iterable[Hook | str], reset: bool = False):
        """
        Add multiple hooks handlers.

        :param hooks: hook(s) to add;
        :param reset: reset hooks;

        :raises ValueError: when hook does not match :py:attr:`hook_class`.
        :raises ValueError: when hook is a string and no registry is provided.
        """
        # ensure agains't missing initialization.
        if self.hooks is None:
            self.hooks = []

        if isinstance(hooks, (Hook, str)):
            self.hooks.append(self.__get_hook(hooks))
        else:
            self.hooks.extend(self.__get_hook(hook) for hook in hooks)

    def __get_hook(self, hook: Hook | str) -> Hook:
        """
        Get the real hook from provided one.

        :raises ValueError: when no registry is provided or hook is of wrong subclass.
        """
        if isinstance(hook, str):
            if self.hook_registry is None:
                raise ValueError(f"Hook registry is not provided on {type(self)}.")
            hook = self.hook_registry.get(hook)()

        if not isinstance(hook, self.hook_class):
            raise ValueError(f"Hook {hook} must be a subclass of {self.hook_class.__name__}")

        return hook
