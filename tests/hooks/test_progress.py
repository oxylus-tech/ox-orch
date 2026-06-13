from ox_orch.hooks.progress import ProgressHook


class TestProgressHook:
    def test_init(self):
        hook = ProgressHook()

        assert hook.total_updates == 0
        assert hook.last_state is None
        assert hook.progress["statuses"] == {}

    def test_reset(self):
        hook = ProgressHook()

        hook.total_updates = 10
        hook.last_state = {"foo": "bar"}

        hook.reset()

        assert hook.total_updates == 0
        assert hook.last_state is None
        assert hook.progress["statuses"] == {}

    def test_before_apply_resets(self, op, op_state):
        hook = ProgressHook()

        hook.total_updates = 3

        hook.before_apply(op, op_state, {})

        assert hook.total_updates == 0

    def test_state_update(self, op_state):
        hook = ProgressHook()

        hook.state_update(op_state)

        assert hook.total_updates == 1
        assert hook.last_state is not None

        progress = hook.progress

        assert progress["updates"] == 1
        assert progress["last_state"]["state_type"] == op_state.__type_id__

    def test_after_apply(self, op, op_state):
        hook = ProgressHook()

        hook.after_apply(op, op_state, {})

        assert hook.total_updates == 1

    def test_after_rollback(self, op, op_state):
        hook = ProgressHook()

        hook.after_rollback(op, op_state, {})

        assert hook.total_updates == 1

    def test_multiple_updates(self, op_state):
        hook = ProgressHook()

        hook.state_update(op_state)
        hook.state_update(op_state)
        hook.state_update(op_state)

        assert hook.total_updates == 3

        status = str(op_state.status)

        assert hook.progress["statuses"][status] == 3
