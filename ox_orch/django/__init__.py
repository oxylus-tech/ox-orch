"""
This module adds Django install and update capabilities.

The core idea is that each Application, its states and the state store have
a features enabling Django capabilities on those applications.

A typical setup will be:

- The Django project INSTALLED_APPS will include the :py:meth:`~.project.DjangoProject`
  using :py:meth:`~.project.DjangoProject.get_installed_apps`.
- The AppsPlan includes:
    - :py:class:`~.operations.DjangoEnable`: enable Django applications on the project;
    - :py:class:`~.operations.DjangoReconciliation`: ensure whole initialization/update
      pipeline. Note that you'll have to ensure to run it in a distinct sub-process (see below).


Multiprocessing and Django
--------------------------

It is by design not possible to setup Django multiple times, or add a new
Django application once the Django apps registry has been fullfilled. Django
just does not allow it.

It means that you can run DjangoReconciliation only for *one project per process*,
and that you can't expect to dynamically update the INSTALLED_APPS.

This leaves us two strategies:

- Either ox_orch workflow is run within the project, and you don't expect new
  applications to be enabled.
- Or you run DjangoReconciliation in a :py:class:`~ox_orch.operations.multiprocess.ForkOperation`:
  the operation will be run from a new subprocess.

The latest solution allows to use :py:class:`~project.DjangoProject` to declare
installed applications from within Django project, or you to enable/disable
Django settings. Typical workflow:

- After installation, update the Django settings, enable application, etc.
- Then, run Django reconciliation within a ForkOperation (spawn into a child process).


"""

from .project import DjangoAppFeature, DjangoStateFeature, DjangoStateStoreFeature, DjangoProject
from .operations import (
    DjangoContext,
    DjangoEnable,
    DjangoSetup,
    ManageCommand,
    CollectStatic,
    MigrationState,
    Migrate,
    DjangoReconciliation,
)
from .shell import ManageCommandShell


__all__ = (
    "DjangoAppFeature",
    "DjangoStateFeature",
    "DjangoStateStoreFeature",
    "DjangoProject",
    "DjangoContext",
    "DjangoEnable",
    "DjangoSetup",
    "ManageCommand",
    "CollectStatic",
    "MigrationState",
    "Migrate",
    "DjangoReconciliation",
    "ManageCommandShell",
)
