from __future__ import annotations
import logging

from .base import ExecutorHook


__all__ = ("LoggingHook",)


class LoggingHook(ExecutorHook):
    """
    Log executor activity using Python's standard logging framework.

    This hook provides high-level visibility over execution and rollback
    operations without modifying business logic.
    """

    def __init__(self, logger: logging.Logger | None = None):
        """
        :param logger: Logger instance to use.
            Defaults to this module's logger.
        """
        self.logger = logger or logging.getLogger(__name__)

    def before_apply(self, operation, state, context):
        """
        Log execution start.
        """
        self.logger.info(
            "Starting operation",
            extra={
                "operation": operation.__type_id__,
                "state": state.__type_id__,
            },
        )

    def after_apply(self, operation, state):
        """
        Log successful execution.
        """
        self.logger.info(
            "Operation completed",
            extra={
                "operation": operation.__type_id__,
                "state": state.__type_id__,
                "status": state.status,
            },
        )

    def apply_failed(self, operation, state, error):
        """
        Log execution failure.
        """
        self.logger.exception(
            "Operation failed",
            extra={
                "operation": operation.__type_id__,
                "state": state.__type_id__,
                "status": state.status,
            },
            exc_info=error,
        )

    def before_rollback(self, operation, state):
        """
        Log rollback start.
        """
        self.logger.info(
            "Starting rollback",
            extra={
                "operation": operation.__type_id__,
                "state": state.__type_id__,
            },
        )

    def after_rollback(self, operation, state):
        """
        Log successful rollback.
        """
        self.logger.info(
            "Rollback completed",
            extra={
                "operation": operation.__type_id__,
                "state": state.__type_id__,
                "status": state.status,
            },
        )

    def rollback_failed(self, operation, state, error):
        """
        Log rollback failure.
        """
        self.logger.exception(
            "Rollback failed",
            extra={
                "operation": operation.__type_id__,
                "state": state.__type_id__,
                "status": state.status,
            },
            exc_info=error,
        )

    def state_update(self, state):
        """
        Log state updates emitted during execution.
        """
        self.logger.debug(
            "State updated",
            extra={
                "state": state.__type_id__,
                "status": state.status,
            },
        )
