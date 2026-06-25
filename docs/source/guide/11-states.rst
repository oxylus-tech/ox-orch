.. _guide-states:

States
======

The whole story of states start with :py:class:`~ox_orch.core.state.State` base class.

It is responsible for:

- Keeping track of the actual :py:class:`Status`;
- Validate transition between the different status;
- Optionally provide extra information;

There are different subclasses of this class providing additional functionalities:

- :py:class:`~ox_orch.core.state.TreeState`: support for nested states in :py:attr:`~ox_orch.core.state.TreeState.children`;
- :py:class:`~ox_orch.core.state.HistoryState`: keep track of status updates in :py:attr:`~ox_orch.core.state.HistoryState.history`;
- :py:class:`~ox_orch.core.state.ChangeSet`: provide  :py:attr:`~ox_orch.core.state.ChangeSet.forward` and :py:attr:`~ox_orch.core.state.ChangeSet.backward` attributes allowing forward and backward objects changes (used with store's :py:meth:`~ox_orch.core.stores.Store.partial commit`).



Operation State
---------------

For an operation, the actual state class is :py:class:`~ox_orch.operations.base.OperationState` that:

- Link to an operation (by id);
- Keeping information required to rollback the operation;
- Keep the run context (only on the root operation state);
- Nested states for plan state and derived (subclassing :py:class:`~ox_orch.core.state.TreeState`);
- Allows interrupted executions to resume safely;
