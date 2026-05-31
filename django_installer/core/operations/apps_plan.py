from __future__ import annotations
from importlib import metadata
import logging
from typing import Iterable, Optional

from pydantic import Field, PrivateAttr

from ..apps import AppMetadata
from ..registry import AppRegistry
from .base import OperationState, AbstractOperation
from .plan import Plan
from .python import InstallState


__all__ = ("AppReconciliationState", "AppReconciliation", "ReconciliationPlan", "AppsPlan")


logger = logging.getLogger()


class AppReconciliationState(OperationState):
    """State for the AppPlan operation."""

    __type_id__ = "state:op:reconciliation"

    app_id: str
    """ Application id. """
    # version: str
    # """ App latest version. """
    package: str
    """ App package. """
    # current_version: Optional[str] = None
    # """ Installed version (read from app state or package metadata). """
    # previous_version: Optional[str] = None
    # """ Installed version (used for rollback). """
    target_version: str
    """ Version expected by registry update. """
    installed_version: str
    """ Version detected in environment before execution. """


class AppReconciliation(Plan):
    """
    Reconcile a Django application after package installation.
    """

    app: Optional[AppMetadata] = None
    __type_id__ = "op:reconciliation"
    _state_class = AppReconciliationState

    def create_state(self, **kwargs):
        return super().create_state(
            app_id=self.app.id,
            package=self.app.package,
            version=self.app.version,
            installed_version=self.get_installed_version(),
            **kwargs,
        )

    def get_installed_version(self):
        try:
            return metadata.version(self.app.package)
        except metadata.PackageNotFoundError:
            return None

    def get_context(self, state, **context):
        context["app"] = self.app
        return super().get_context(state, **context)


class ReconciliationPlan(Plan):
    """
    Run reconciliation for the provided applications.

    When a registry is provided, it will run only for the packages whose
    installed version differs from registry's one.
    """

    __type_id__ = "op:reconciliation_plan"

    app_reconciliation: AppReconciliation
    apps: list[AppMetadata] = Field(default_factory=[])

    def _apply(self, state, apps: Iterable[AppMetadata], registry: AppRegistry | None = None, **context):
        if not apps:
            return

        if registry:
            # 1. Detect package version drift in environment.
            # When no registry is provided, assume all apps are to be updated.
            apps = registry.get_full([m.id for m in apps])

        dirty = self.get_dirty_apps(apps)

        # 2. Reconcile
        for app in dirty:
            op = self.app_reconciliation.clone(app=app)
            op_state = op.create_state()
            state.children.append(op_state)

            yield from op.apply(state=op_state, app=app, **context)

    def _rollback(self, state, **context):
        for child_state in reversed(state.children):
            yield from self.app_reconciliation.rollback(state=child_state, **context)

    def get_dirty_apps(self, apps: Iterable[AppMetadata]) -> list[AppMetadata]:
        """
        Get applications that have been updated in the environment.

        Preserve initial input's order.
        """
        changed = []

        for app in apps:
            try:
                actual_version = metadata.version(app.package)
            except metadata.PackageNotFoundError:
                continue

            stored_version = app.state and app.state.installed_version or None
            if actual_version != stored_version:
                changed.append(app)

        return changed


class AppsPlan(Plan):
    """
    Global application orchestration plan.

    Pipeline:

        - Install packages (pip/poetry/uv/etc)
        - Detect implicit updates
        - Run reconciliation per affected app.
    """

    __type_id__ = "op:apps_plan"
    _registry: AppRegistry = PrivateAttr()

    apps: list[AppMetadata] = Field(exclude=True, default_factory=list)
    """ Ordered list of applications, set using :py:meth:`set_apps`. """
    install_plan: AbstractOperation
    """ Installation plan (as PipInstall). """
    reconciliation_plan: ReconciliationPlan = Field(default_factory=ReconciliationPlan)
    """ Implicit update plan. """

    @classmethod
    def from_registry(cls, registry: AppRegistry, names: list[str], **init_kwargs) -> AppsPlan:
        """
        Create a new AppsPlan with application loaded from the provided registry.
        """
        init_kwargs["_registry"] = registry
        init_kwargs["apps"] = registry.get_full(names)
        return cls(**init_kwargs)

    def get_operations(self, state):
        return iter([self.install_plan, self.reconciliation_plan])

    def _apply(self, state, **context):
        context.setdefault("registry", self._registry)
        context.setdefault("apps", self.apps)

        yield from super()._apply(state, **context)
        self.sync_registry(state)

    def sync_registry(self, state):
        install_state = next((child for child in state.children if isinstance(child, InstallState)), None)

        if install_state:
            self._registry.commit(
                {app_id: {"installed_version": version} for app_id, version in install_state.after_versions.items()}
            )
