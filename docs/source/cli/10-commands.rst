.. _cli-commands:

Commands
========

Command format:

.. code-block:: bash

    ox-orch [OPTIONS] COMMAND ...


As options, there only currently is:

- ``--module`` ``-m``: import external modules (operations, features, etc.)


ox-orch schemas
---------------

The ``schemas [GROUP] ...`` command let you visualize the different data schemas available for your workflow.
It allows you to check up the arguments of an object, as an operation or a context, displaying information on standard output.


ox-orch run
-----------

The main command to run a workflow.


ox-orch apps
------------

This command allows you to manage application stores. Currently you:

- Import applications from Pypi packages in a store;
- List applications



ox-orch replay
--------------

TODO
