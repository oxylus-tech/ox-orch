from __future__ import annotations
import logging
from typing import Any, Iterable, Optional

from pydantic import Field

from ..utils import merge_nested_dicts
from ox_orch.core.apps import AppMetadata
from ox_orch.core.app_registry import AppRegistry, AppStateDiffs
from ox_orch.core.registry import register
from ox_orch.core.state import Status
from .base import AbstractOperation
from .plan import Plan, PlanState


__all__ = ("AppPlanState", "AppPlan", "ReconciliationPlan", "AppsPlan")


logger = logging.getLogger()


@register("app")
class AppPlanState(PlanState):
    """State for the AppPlan operation."""

    app_id: str
    """ Application id. """
    app: AppMetadata
    """ Application metadata used for install. """
    target_version: str
    """ Version expected by registry update. """
    installed_version: str
    """ Version detected in environment before execution. """
    state_facts: dict[str, Any] = Field(default_factory=dict)
    """
    Application's state changes that will be committed to apps registry
    once whole installation is done.
    """


@register("app")
class AppPlan(Plan):
    """
    Reconcile a Django application after package installation.

    Nested operations will be run with two extra context:

        - ``app``: AppPlan instance;
        - ``app_state``: the state of the AppPlan
    """

    __state_class__ = AppPlanState

    app: Optional[AppMetadata] = None

    def create_state(self, **kwargs):
        return super().create_state(
            app_id=self.app.id,
            app=self.app,
            target_version=self.app.version,
            installed_version=self.app.get_installed_version(),
            **kwargs,
        )

    def get_inputs(self, state, **inputs):
        inputs["app"] = self.app
        inputs["app_state"] = state
        return super().get_inputs(state, **inputs)


@register("reconciliation")
class ReconciliationState(AppStateDiffs, PlanState):
    """State for the reconciliation of applications."""

    pass


@register("reconciliation")
class ReconciliationPlan(AbstractOperation):
    """
    Run reconciliation for the provided applications.

    When a registry is provided, it will run only for the packages whose
    installed version differs from registry's one.
    """

    __state_class__ = ReconciliationState
    __apply_spec__ = ("apps",)

    app_plan: AppPlan

    def _apply(self, state, ctx, apps: Iterable[AppMetadata], apps_registry: AppRegistry | None = None, **inputs):
        if not apps:
            return

        registry = inputs.get("app_registry")
        if registry:
            apps = registry.get_full([a.id for a in apps])

        # 1. Detect package version drift in environment.
        dirty = self.get_dirty_apps(apps)

        if not apps:
            return

        # 2. Reconcile
        for app in dirty:
            op = self.app_plan.clone(app=app.clone())
            op_state = op.create_state()
            state.children.append(op_state)

            yield from op.apply(op_state, ctx, app=app, **inputs)

        # 3. Collect registry update
        for op_state in state.children:
            kw = {**op_state.state_facts, "status": Status.COMPLETED}
            state.add_update(op_state.app, **kw)

        # 4. Ensure all apps are enabled on enable
        # if inputs.get("app_enable"):
        #    for app in apps:
        #        state.add_update(app, enabled=True)

    def get_dirty_apps(self, apps: Iterable[AppMetadata]) -> list[AppMetadata]:
        """
        Get applications that have been updated in the environment.

        Preserve initial input's order.
        """
        changed = []

        for app in apps:
            if actual_version := app.get_installed_version():
                stored_version = app.state and app.state.installed_version or None
                if actual_version != stored_version:
                    changed.append(app)

        return changed


@register("apps")
class AppsPlan(Plan):
    """
    Global application orchestration plan.

    Pipeline:

        - Install packages (pip/poetry/uv/etc)
        - Detect implicit updates & run reconciliation
        - Update registry with the installed versions
    """

    __apply_spec__ = {"apps": (list, None), "app_registry": (AppRegistry, None)}
    __rollback_spec__ = {"apps": (list, None), "app_registry": (AppRegistry, None)}

    install: AbstractOperation
    """ Installation plan (as PipInstall). """
    reconciliation: ReconciliationPlan
    """ Implicit update plan. """
    before_install: list[AbstractOperation] = Field(default_factory=list)
    """ Operations to run before packages installation. """
    after_install: list[AbstractOperation] = Field(default_factory=list)
    """ Operations to run before packages installation. """

    def get_operations(self, state):
        return [*self.before_install, self.install, *self.after_install, self.reconciliation]

    def _apply(self, state, ctx, apps: list[AppMetadata], app_registry: AppRegistry, **inputs):
        yield from super()._apply(state, ctx, apps=apps, app_registry=app_registry, **inputs)
        self.sync_registry(state, app_registry)

    def _rollback(self, state, ctx, apps: list[AppMetadata], app_registry: AppRegistry, **inputs):
        yield from super()._rollback(state, ctx, apps=apps, app_registry=app_registry, **inputs)
        self.sync_registry(state, app_registry, "backward")

    def sync_registry(self, state, registry, direction="forward"):
        if direction not in ("forward", "backward"):
            raise ValueError('Direction must be either "forward" or "backward"')

        diffs = []
        for child_state in state.children:
            if isinstance(child_state, AppStateDiffs):
                child_state.validate_diffs()
                diffs.append(getattr(child_state, direction))

        updates = merge_nested_dicts(*diffs)
        if updates:
            registry.commit(updates)
