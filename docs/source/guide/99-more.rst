More info
---------

Registries
..........

In ``ox-orch``, the :py:class:`~ox_orch.core.registry.Registry` class is used
at different places, mostly to handle different kind of :py:class:`~ox_orch.core.pydantic.PolymorphicModel`.

Classes as ``Operation``, ``OperationState`` are subclass the ``Registry`` one,
set the register to use on the attribute ``__registry__``:

.. code-block:: python

    from ox_orch.core import RegisteredClass, Registry


    POLYGON_REGISTRY = Registry()

    class Polygon(RegisteredClass):
        __registry__ = Registry()


The subclasses will then register using the :py:func:`~ox_orch.core.registry.register` decorator:

.. code-block:: python

    from ox_orch.core import register

    @register("square")
    class Square(Polygon):
        pass

    @register("Circle")
    class Circle(Polygon):
        pass

    # ...

    assert "square" in POLYGON_REGISTRY
    assert "circle" in POLYGON_REGISTRY

    square_cls = POLYGON_REGISTRY.get("square")

    # raises a ValueError
    POLYGON_REGISTRY.get("not_a_polygon")
