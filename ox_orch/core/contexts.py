from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from .pydantic import PolymorphicModel
from .registry import DocumentedRegistry, DocumentedClass


__all__ = ("CONTEXT_INPUT_REGISTRY", "ContextInput", "ContextInputs", "Context", "RunContext")


CONTEXT_INPUT_REGISTRY = DocumentedRegistry()


class ContextInput(PolymorphicModel, DocumentedClass, ABC):
    """
    Input data provided by user and converted into a context class.

    This class shall be registered using ``register`` decorator. The provided
    key is the one used as operation apply/rollback arguments.

    Its :py:meth:`build_context` MUST be provided.

    .. important::

        This object is not aimed as to fully deserialize and handle permissions,
        rather provide a simple layer between context and raw input data.

        For example, it can handle conversion between a store information and the
        actual store instance but you don't wan't user being able to edit file
        though a rest API.

    """

    __registry__ = CONTEXT_INPUT_REGISTRY

    @abstractmethod
    def build_context(self, context_inputs: ContextInputs, **kwargs) -> Context:
        """
        Return the context based on the provided execution specification and
        contexts.

        It is not expected to add the new object into the contexts dict

        :param context_inputs: the calling ContextInputs;
        :param **kwargs: extra initial attributes;
        """
        pass


@dataclass
class ContextInputs:
    """
    Handle contexts building using :py:class:`ContextInput`.

    Basically:

        - User provide input data, which are deserialized as ContextInput;
        - The class uses them to build the contexts;
        - Those contexts can then provided as input values to operations;

    """

    inputs: dict[str, ContextInput] = field(default_factory=dict)
    contexts: dict[str, Context] = field(default_factory=dict)
    registry: DocumentedRegistry = CONTEXT_INPUT_REGISTRY

    def build(self, reset: bool = False):
        """
        Build all contexts of provided inputs, skipping existing ones.

        :param reset: clear all previous contexts.
        """
        if reset:
            self.contexts = {}

        for key in self.inputs.keys():
            if key not in self.contexts:
                self.contexts[key] = self.build_context(key)

    def resolve(self, key: str) -> Context:
        """
        Get or create context by key.

        When the user didn't provide any input for generating a context, it
        will raises a ValueError.

        See :py:meth:`build_context` for more information about context creation.
        """
        if context := self.contexts.get(key):
            return context
        return self.build_context(key)

    def build_context(self, key: str) -> Context:
        """
        Build a new context and save it to :py:attr:`contexts`.

        When there is no ContextInput provided in :py:attr:`inputs`, it will try
        to find a corresponding registered one to instanciate the context.

        :yields ValueError: when creating a context for which user has provided no input.
        :yields ValueError: when there is no registered ContextInput class handling the context creation.
        :yields pydantic.ValidationError: when there are missing input value from the user to create the context.
        """
        context_input = self.inputs.get(key)
        if not context_input:
            # input not provided by user, instanciate it.
            # pydantic will raise a validation error, if there are missing required
            # fields.
            context_input = self.registry.get(key)()
            self.inputs[key] = context_input

        context = context_input.build_context(self)
        self.contexts[key] = context
        return context


@dataclass
class Context:
    """Base class for all contexts."""

    pass


class RunContext(BaseModel, Context):
    """
    Running context of operations, provided to the root state of operations.

    Must be serializable as it is assigned to root operation state.
    """

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    """ Run id. """
    started_at: datetime | None = None
    """ Run execution start. """
    finished_at: datetime | None = None
    """ Run execution end. """
    trigger: str = "cli"
    """ What triggered this execution, as cli, api, scheduler,... """
    dry_run: bool = False
    """ Ran in dry run mode. """

    def start(self):
        """Tag context as started."""
        self.started_at = datetime.now(timezone.utc)

    def finish(self):
        """Tag context as finished.

        :raises RuntimeError: when the context hasn't been started first.
        """
        if self.started_at is None:
            raise RuntimeError("You must first call start to finish it.")

        self.finished_at = datetime.now(timezone.utc)
