from dataclasses import dataclass
from typing import Any, Type


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

    def emit(self, event, **payload: Any):
        if hook := getattr(self, event, None):
            hook(**payload)


class HookEmitter:
    """Hook events emitter.

    The hooks must subclass the provided :py:attr:`hook_class`.

    It is aimed as a mixin class, so you'll have to provide initial hooks.
    """

    hook_class: Type[Hook] | None = None
    """ Supported hook class. """
    hooks: list[Hook] = None
    """ The list of hooks. """

    def _emit(self, event: str, **payload: Any):
        if not self.hooks:
            return

        for hook in self.hooks:
            hook.emit(event, **payload)

    def listen(self, *hooks: list[Hook]):
        """
        Add multiple hooks handlers.

        :raises: ValueError when hook does not match :py:attr:`hook_class`.
        """
        # ensure agains't missing initialization.
        if self.hooks is None:
            self.hooks = []
        for hook in hooks:
            if self.hook_class is not None and not isinstance(hook, self.hook_class):
                raise ValueError(f"Hook {hook} must be a subclass of {self.hook_class.__name__}")
        self.hooks.extend(hook)
