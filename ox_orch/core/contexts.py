from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from pydantic import BaseModel, Field

from .shell import Shell


__all__ = ("RunContext", "ExecutionContext")


class RunContext(BaseModel):
    """
    Running context of operations, provided to the root state of operations.
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


@dataclass
class ExecutionContext:
    """
    Runtime-only orchestration data shared across all operations.

    This object is not persisted nor serialized.
    """

    run: RunContext = field(default_factory=RunContext)
    """ The current run context for operations. """
    shell: Shell | None = field(default_factory=lambda: Shell.from_spec())
    """ Shell backend used to run commands. """
    data: dict[str, Any] = field(default_factory=dict)
    """ Extra input data. """

    def get(self, key: str, default=None) -> Any:
        """Return data by key."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        """Set data to the context."""
        self.data[key] = value
