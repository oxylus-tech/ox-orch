from ox_orch import utils


def test_merge_nested_dicts():
    a = {"a": {"foo": 123, "bar": 234}, "b": {"foo": 234}}
    b = {"a": {"foo": 456}, "b": {"tee": 4567}}
    assert utils.merge_nested_dicts(a, b) == {"a": {"foo": 456, "bar": 234}, "b": {"foo": 234, "tee": 4567}}
