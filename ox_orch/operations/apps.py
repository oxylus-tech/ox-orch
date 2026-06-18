from __future__ import annotations
from dataclasses import dataclass, field
import logging
from typing import Any, Iterable

from pydantic import Field, field_validator

from ox_orch.apps import Application, AppState, AppStore, AppStateStore, AppStateMemoryStore
from ox_orch.core import register, Status, ChangeSet
from .base import Operation
from .plan import Plan, PlanState


__all__ = ("AppsContext", "AppPlanState", "AppPlan", "ReconciliationPlan", "AppsPlan")


logger = logging.getLogger()


@dataclass
class AppContext:
    """Context provided to AppPlan's operations."""

    app: Application
    app_state: AppState
    app_plan: AppPlan
    app_plan_state: AppPlanState


@dataclass
class AppsContext:
    """Context provided to app related operation."""

    apps: list[Application]
    store: AppStore
    state_store: AppStateStore = field(default_factory=AppStateMemoryStore)

    @classmethod
    def from_apps_ids(cls, apps: list[str], store: AppStore, **kwargs):
        """
        Create a new instance using provided application references.
        """
        apps = store.get_all(apps, exc=True)
        return cls(apps=apps, store=store, **kwargs)


@register("app")
class AppPlanState(PlanState):
    """State for the AppPlan operation."""

    app_id: str
    """ Application id. """
    app: Application
    """ Application metadata used for install. """
    target_version: str
    """ Version expected by registry update. """
    version: str
    """ Version detected in environment before execution. """
    facts: dict[str, Any] = Field(default_factory=dict)
    """
    Application's state changes that will be committed to apps registry
    once whole installation is done.
    """


@register("app")
class AppPlan(Plan):
    """
    Reconcile a Django application after package installation.

    Nested operations will be run with ``app_ctx`` (instance of :py:class:`AppContext`).
    """

    __state_class__ = AppPlanState

    app: Application | None = None

    def create_state(self, **kwargs):
        return super().create_state(
            app_id=self.app.id,
            app=self.app,
            target_version=self.app.version,
            version=self.app.get_installed_version(),
            **kwargs,
        )

    def get_inputs(self, state, apps_ctx, **inputs):
        inputs["app_ctx"] = AppContext(
            app=self.app,
            app_state=apps_ctx.state_store.get_or_create(self.app),
            app_plan=self,
            app_plan_state=state,
        )
        return super().get_inputs(state, apps_ctx=apps_ctx, **inputs)


@register("reconciliation")
class ReconciliationState(ChangeSet, PlanState):
    """State for the reconciliation of applications."""

    pass


@register("reconciliation")
class ReconciliationPlan(Operation):
    """
    Run reconciliation for the provided applications.

    When a registry is provided, it will run only for the packages whose
    installed version differs from registry's one.
    """

    __state_class__ = ReconciliationState
    __apply_spec__ = ("apps_ctx",)
    __full_inputs__ = True

    app_plan: AppPlan

    def _apply(self, state, ctx, apps_ctx: AppsContext, **inputs):
        apps = apps_ctx.apps
        if not apps:
            return

        if store := apps_ctx.store:
            apps = store.resolve([a.ref for a in apps])

        # 1. Detect package version drift in environment.
        dirty = self.get_dirty_apps(apps, apps_ctx.state_store)

        if not apps:
            return

        # 2. Reconcile
        for app in dirty:
            op = self.app_plan.model_copy(update={"app": app.model_copy(deep=True)})
            op_state = op.create_state()
            state.children.append(op_state)

            yield from op.apply(op_state, ctx, app=app, apps_ctx=apps_ctx, **inputs)

        # 3. Collect registry update
        for op_state in state.children:
            kw = {
                **op_state.facts,
                "status": Status.COMPLETED,
                "package": op_state.app.package,
            }
            state.add_changes(op_state.app.id, kw)

        # 4. Ensure all apps are enabled on enable
        # if inputs.get("app_enable"):
        #    for app in apps:
        #        state.add_update(app, enabled=True)

    def get_dirty_apps(self, apps: Iterable[Application], state_store: AppStateStore) -> list[Application]:
        """
        Get applications that have been updated in the environment.

        Preserve initial input's order.
        """
        changed = []

        for app in apps:
            if actual_version := app.get_installed_version():
                app_state = state_store.get(app.id)
                stored_version = app_state and app_state.version or None
                if actual_version != stored_version:
                    changed.append(app)

        return changed


class AppsState(ChangeSet, PlanState):
    pass


@register("apps")
class AppsPlan(Plan):
    """
    Global application orchestration plan.

    Pipeline:

        - Install packages (pip/poetry/uv/etc)
        - Detect implicit updates & run reconciliation
        - Update state store with the installed versions

    Typical workflow induces:

        - :py:attr:`before_install` (optional): operations to run before packages install.
        - :py:attr:`install`: install python packages
        - :py:attr:`after_install` (optional): operations to run after packages install.
        - :py:attr:`reconciliation` (optional): application reconciliation.
        - :py:attr:`after_reconciliation` (optional): operations to run after reconciliation.
    """

    __apply_spec__ = {"apps_ctx": AppsContext}
    __rollback_spec__ = {"apps_ctx": AppsContext}
    __state_class__ = AppsState

    install: Operation
    """ Installation plan (as PipInstall). """
    reconciliation: ReconciliationPlan | None = None
    """
    Implicit update plan that will be run for each updated application.

    You can provide it as a list of operations, as:

    .. code-block:: python

        AppsPlan(
            install=UvInstall(),
            reconciliation=[
                Migrations(),
                Enable(),
            ]
        )

    The reconciliation will be built up with an :py:class:`AppPlan` containing
    those operations.
    """
    before_install: list[Operation] = Field(default_factory=list)
    """ Operations to run before packages installation. """
    after_install: list[Operation] = Field(default_factory=list)
    """ Operations to run before packages installation. """
    after_reconciliation: list[Operation] = Field(default_factory=list)
    """ Operations to run after applications reconciliation. """

    @field_validator("reconciliation", mode="before")
    @classmethod
    def build_reconciliation(cls, value: ReconciliationPlan | list[Operation] | tuple[Operation]):
        """
        Reconciliation validator allowing to provide a list or tuple of operations.
        The operations will be added to the ReconciliationPlan's AppPlan.
        """
        if isinstance(value, ReconciliationPlan):
            return value

        if isinstance(value, (list, tuple)):
            return ReconciliationPlan(app_plan=AppPlan(operations=value))

        return value

    def get_operations(self, state):
        items = [
            *self.before_install,
            self.install,
            *self.after_install,
        ]
        if self.reconciliation is not None:
            items.append(self.reconciliation)
        return items + self.after_reconciliation

    def _apply(self, state, ctx, apps_ctx: AppsContext, **inputs):
        yield from super()._apply(state, ctx, apps_ctx=apps_ctx, apps=apps_ctx.apps, **inputs)

        state_store = apps_ctx.state_store
        state.merge_from(cs for cs in state.children if isinstance(cs, ChangeSet))
        app_states = {s.id: s for s in state_store.get_all(state.forward.keys())}
        for key, values in state.forward.items():
            state.set_backward(key, app_states.get(key))

        if state.forward:
            state_store.partial_commit(state.forward, allow_create=True)

    def _rollback(self, state, ctx, apps_ctx: AppsContext, **inputs):
        yield from super()._rollback(state, ctx, apps_ctx=apps_ctx, **inputs)

        if state.backward:
            apps_ctx.state_store.partial_commit(state.backward, allow_create=True)
