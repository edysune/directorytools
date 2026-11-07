from dedup_cleaner import dedup as D
from dedup_cleaner.models import FileInfo


def F(path):
    return FileInfo(name=path.rsplit("/", 1)[-1], path=path, size=10)


def test_one_preferred_is_actionable():
    res, act = D.resolve_group([F("/mnt/a/v.mkv"), F("/mnt/b/v.mkv")], ["/mnt/a"])
    assert res and act.kind == "DEDUP_KEEP"
    assert act.keeper.path == "/mnt/a/v.mkv"
    assert [x.path for x in act.removed] == ["/mnt/b/v.mkv"]


def test_all_preferred_is_skip():
    res, act = D.resolve_group([F("/mnt/a/v.mkv"), F("/mnt/a/sub/v.mkv")], ["/mnt/a"])
    assert not res and act.kind == "DEDUP_SKIP"
    assert act.removed == []                    # preferred is never deleted


def test_none_preferred_is_skip():
    res, act = D.resolve_group([F("/mnt/b/v.mkv"), F("/mnt/c/v.mkv")], ["/mnt/a"])
    assert not res and act.kind == "DEDUP_SKIP"
    assert act.removed == []


def test_multiple_preferred_plus_nonpref():
    res, act = D.resolve_group(
        [F("/mnt/a/v.mkv"), F("/mnt/az/v.mkv"), F("/mnt/c/v.mkv")], ["/mnt/a"])
    # /mnt/az is NOT under /mnt/a -> only /mnt/a/v.mkv is preferred
    assert res and act.keeper.path == "/mnt/a/v.mkv"
    assert len(act.removed) == 2                # both non-preferred removed


def test_bad_type_detection():
    files = [F("/mnt/a/junk.part"), F("/mnt/a/ok.mp4"), F("/mnt/a/x.tmp")]
    out = D.find_bad_type_files(files, [".part", ".tmp"])
    assert [r.removed[0].path for r in out] == ["/mnt/a/junk.part", "/mnt/a/x.tmp"]
    assert D.find_bad_type_files(files, []) == []


def test_plan_cap_stops_scanning():
    by_ns = {
        ("a1", 1): [F("/mnt/a1"), F("/mnt/b1")],
        ("a2", 1): [F("/mnt/a2"), F("/mnt/b2")],
        ("a3", 1): [F("/mnt/a3"), F("/mnt/b3")],
    }
    actions, stopped = D.plan_dedup(by_ns, ["/mnt/a1", "/mnt/a2", "/mnt/a3"], cap=2)
    assert len(actions) == 2 and stopped is True


def test_hash_confirm_drops_mismatch():
    class FakeK:  # keeper with same name+size but different bytes
        path = "/mnt/a/v.mkv"
        name = "v.mkv"
    def confirm(keeper, victims):
        return []                                 # simulate: bytes differ
    by_ns = {("v.mkv", 10): [F("/mnt/a/v.mkv"), F("/mnt/b/v.mkv")]}
    actions, _ = D.plan_dedup(by_ns, ["/mnt/a"], cap=10, confirm=confirm)
    assert len(actions) == 1 and actions[0].kind == "DEDUP_SKIP"
