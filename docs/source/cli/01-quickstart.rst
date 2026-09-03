.. _cli-quickstart:

Quickstart
==========

Simple example
--------------

Lets setup a simple installation workflow. The minimal you'll need to provide to run a workflow is the execution specification file which maps to the :py:class:`~ox_orch.operations.execution.ExecutionSpec` class.

.. code-block:: yaml

    # hello.yaml
    name: Hello
    description: Say hello to the world
    operation:
      __type_id__: shell
      forward: ["echo", "Hello world!"]
      backward: ["echo" "Goodbye world!"]

Here the specification is really a dummy one as you may recognize it. Lets explain it:

- ``name``, ``description``: simply a name and a description
- ``operation``: the operation to run. Here it is to execute a shell command.

    - ``__type_id__``: specify the type of the operation which here is ``shell`` (run a shell command). This key is used at different places when we have polymorphic objects (an object can be of any subtype of an expected one).
    - ``forward``, ``backward``: print the provided command on apply and rollback.

Lets run it:

.. code-block:: bash

    ox-orch run apply hello.yaml

Application installation


Lets go one step further, by adding a package installation step:

.. code-block:: yaml

    # install.yaml
    name: UV Install
    operation:
      # A Plan allows to run multiple operations sequentially
      __type_id__: plan
      operations:
      # Keep our hello world
      - __type_id__: shell
        forward: ["echo", "Hello world!"]
        backward: ["echo" "Goodbye world!"]
      # Add an installation step
      - __type_id__: install:uv

As you might see, there is no package list here. That's because packages is an input argument, not a pipeline specification. Those are provided as input value to the command line tool either as a config file or argument.

Let's use a file:

.. code-block:: yaml

    # context.yaml
    install:
      packages:
        httpx: 0.28.1
        pyyaml: 6.0.3

Then you can pass this file with the ``--context/-c`` argument:

.. code-block:: bash

    ox-orch run -c context.yaml apply hello.yaml

You can also provide extra input arguments using the ``--input/-i`` argument:

.. code-block:: bash

    ox-orch run -i "{\"install\":{\"packages\":{\"httpx\":\"0.28.1\"}}}" apply hello.yaml

States
------

What if the installation fails? This leave us with an inconsistent environment, where some package may be installed and other no. This is not acceptable on production grade deployments.

Here come the states: they keep track of each operation processing and status, allowing to inspect what happened and to revert the operation (aka **rollback**).

To automatically revert back on apply operations that fails, you can use the ``--rollback`` argument on the ``apply`` command:

.. code-block:: bash

    ox-orch run -c context.yaml apply hello.yaml --rollback

You also should keep the resulting state into a file, this is the role of the ``--save/-S`` argument:

.. code-block:: bash

    ox-orch run -S state.json -c context.yaml apply install.yaml

This file thus can be reused to ``rollback`` command. Later it is planned to allow continuing an interrupted operation processing using this file.


.. code-block:: bash

    ox-orch run -S rollback_state.json -c context.yaml rollback install.yaml state.json
