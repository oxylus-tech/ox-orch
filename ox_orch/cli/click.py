from collections.abc import Callable, Iterable

import click


__all__ = ("DynamicChoice",)


class DynamicChoice(click.ParamType):
    """
    A Click parameter type whose choices are resolved dynamically.
    """

    name = "choice"

    def __init__(self, choices: Callable[[], Iterable[str]]) -> None:
        """
        Initialize the dynamic choice type.

        :params choices: Callable returning an iterable of valid choice values.
        """
        self.choices = choices

    def _get_choices(self) -> tuple[str, ...]:
        """
        Resolve the available choices.

        :returns: The currently available choices.
        """
        return tuple(self.choices())

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        """
        Validate and convert a value.

        :param value: Value supplied by the user.
        :param param: Click parameter being processed.
        :param ctx: Current Click context.
        :returns: The validated value.
        """
        choices = self._get_choices()

        if value not in choices:
            self.fail(
                f"{value!r} is not one of {', '.join(repr(choice) for choice in choices)}.",
                param,
                ctx,
            )
        return value

    def get_metavar(self, param: click.Parameter | None, ctx: click.Context | None) -> str:
        """
        Return the metavar displayed in Click help.

        :param param: Click parameter being documented.
        :param ctx: Current Click context.
        :returns: A representation of the available choices.
        """
        choices = self._get_choices()
        return f"[{'|'.join(choices)}]"
