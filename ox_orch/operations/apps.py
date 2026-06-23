from __future__ import annotations
from dataclasses import dataclass, field
import logging
from typing import Any, Iterable

from pydantic import Field, field_validator

from ox_orch.apps import Application, AppState, AppStore, AppStateStore, AppStateMemoryStore, InstallOrigin
from ox_orch.core import register, Status, ChangeSet
from .base import Operation
from .install import InstallOperation
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

    app: Application
    """ Application metadata used for install. """
    target_version: str
    """ Version expected by registry update. """
    version: str | None = None
    """ Version detected in environment before execution. """
    facts: dict[str, Any] = Field(default_factory=dict)
    """
    Application's state changes that will be committed to apps registry
    once whole installation is done.
    """

    def add_facts(self, facts: dict[str, Any]):
        """
        Add application state change, correctly handling features update.
        """
        if features := facts.get("features", None):
            target = self.facts.setdefault("features", {})
            for key, feature in features.items():
                target.setdefault(key, {}).update(feature)

        self.facts.update((k, v) for k, v in facts.items() if k != "features")


@register("app")
class AppPlan(Plan):
    """
    Reconcile a Django application after package installation.

    Nested operations will be run with ``app_ctx`` (instance of :py:class:`AppContext`).
    """

    __state_class__ = AppPlanState
    _label = "Application Plan"
    _description = "Apply nested `operations` on a single application."

    app: Application | None = Field(default=None, description="The related application to work with.")

    def create_state(self, **kwargs):
        return super().create_state(
            app=self.app,
            target_version=self.app.version,
            version=self.app.get_installed_version(),
            **kwargs,
        )

    def get_inputs(self, state, apps_ctx, **inputs):
        inputs["app_ctx"] = self.get_app_context(state, apps_ctx)
        return super().get_inputs(state, apps_ctx=apps_ctx, **inputs)

    def get_app_context(self, state: AppPlanState, apps_ctx):
        return AppContext(
            app=self.app,
            app_state=apps_ctx.state_store.get_or_create(self.app),
            app_plan=self,
            app_plan_state=state,
        )


@register("reconciliation")
class ReconciliationState(ChangeSet, PlanState):
    """State for the reconciliation of applications."""

    pass


@register("reconciliation")
class ReconciliationPlan(Plan):
    """
    This operation is used to apply a nested operation on updated packages.

    It will first resolves which package have been updated after an installation,
    by comparing their version to the application state store.

    For each application that has been updated, it will run the nested
    :py:attr:`app_plan` operation. It then collect the :py:attr:`AppState.facts`
    as updates of application state to apply.
    """

    __state_class__ = ReconciliationState
    __apply_spec__ = ("apps_ctx",)
    __full_inputs__ = True
    _label = "Reconciliation Plan"
    _description = (
        "Detect updates based on provided applications and their dependencies, "
        "and run an Application Plan for each."
        ""
    )

    app_plan: AppPlan = Field(description="The application plan to apply.")

    def _apply(self, state, ctx, apps_ctx: AppsContext, **inputs):
        apps = apps_ctx.apps
        if not apps:
            return

        # Keep track of ids required by user
        ids = {app.id for app in apps}

        # Resolve dependencies
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
                "origin": InstallOrigin.USER if op_state.app.id in ids else InstallOrigin.DEPENDENCY,
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
        - Update state store with the gathered applications states updates.

    Operations flowchart:

        - :py:attr:`before_install` (optional): operations to run before packages install.
        - :py:attr:`install`: install python packages
        - :py:attr:`after_install` (optional): operations to run after packages install.
        - :py:attr:`reconciliation` (optional): application reconciliation
          (see :py:class:`Reconciliation` for more info).
        - :py:attr:`operations` (optional): other operations to run.

    .. note::

        This class assumes that any child's state that subclasses a
        :py:class:`~ox_orch.core.state.ChangeSet` is used
        to provide application state updates.

    """

    __apply_spec__ = {"apps_ctx": AppsContext}
    __rollback_spec__ = {"apps_ctx": AppsContext}
    __state_class__ = AppsState
    _label = "Applications Plan"
    _description = (
        "Run application packages installation, optional Reconciliation Plan and "
        "other operations. This is the main plan to use when you want to install "
        "or update applications.\n"
        "The flowchart of operations is:\n"
        "- `before_install`\n"
        "- `install`\n"
        "- `after_install`\n"
        "- `reconciliation`\n"
        "- declared `operations`"
    )

    install: InstallOperation = Field(description="The package install operation.")
    """ Installation plan (as PipInstall). """
    reconciliation: ReconciliationPlan | None = Field(
        default=None,
        description=(
            "The reconciliation plan for updated applications. Note that you can "
            "also provide an application plan or a list of operations."
        ),
    )
    """
    Implicit update plan that will be run for each updated application.

    You can provide it as a list of operations or an :py:class:`AppPlan`, as:

    .. code-block:: python

        AppsPlan(
            install=UvInstall(),
            reconciliation=[Migrations(), Enable()]
        )

        AppsPlan(
            install=UvInstall(),
            reconciliation=AppPlan()
        )

    The reconciliation will be built up with an :py:class:`AppPlan` containing
    those operations.
    """
    before_install: list[Operation] = Field(
        default_factory=list, description="Operations to run before package installation."
    )
    """ Operations to run before packages installation. """
    after_install: list[Operation] = Field(
        default_factory=list, description="Operations to run after packages installation, and before reconciliation."
    )
    """ Operations to run before packages installation. """

    @field_validator("reconciliation", mode="before")
    @classmethod
    def build_reconciliation(cls, value: ReconciliationPlan | list[Operation] | tuple[Operation]):
        """
        Reconciliation validator allowing to provide a list or tuple of operations.
        The operations will be added to the ReconciliationPlan's AppPlan.
        """
        match value:
            case AppPlan():
                return ReconciliationPlan(app_plan=value)
            case list() | tuple():
                return ReconciliationPlan(app_plan=AppPlan(operations=value))
            case _:
                return value

    def get_operations(self, state):
        items = [
            *self.before_install,
            self.install,
            *self.after_install,
        ]
        if self.reconciliation is not None:
            items.append(self.reconciliation)
        return items + self.operations

    def _apply(self, state, ctx, apps_ctx: AppsContext, **inputs):
        yield from super()._apply(state, ctx, apps_ctx=apps_ctx, apps=apps_ctx.apps, **inputs)

        state_store = apps_ctx.state_store
        state.merge_from(cs for cs in state.children if isinstance(cs, ChangeSet))
        app_states = {s.id: s for s in state_store.get_all(state.forward.keys())}
        for key, values in state.forward.items():
            state.set_backward(key, app_states.get(key))

        if state.forward:
            state_store.partial_commit(state.forward, allow_create=True, merge=True)

    def _rollback(self, state, ctx, apps_ctx: AppsContext, **inputs):
        yield from super()._rollback(state, ctx, apps_ctx=apps_ctx, **inputs)

        if state.backward:
            apps_ctx.state_store.partial_commit(state.backward, allow_create=True)
