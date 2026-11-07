from dedup_cleaner import paths


def test_preferred_recursive_and_boundary():
    assert paths.is_preferred("/mnt/a/v.mkv", ["/mnt/a"])
    assert paths.is_preferred("/mnt/a/sub/deep/v.mkv", ["/mnt/a"])
    assert paths.is_preferred("/mnt/a", ["/mnt/a"])          # inclusive root
    assert not paths.is_preferred("/mnt/a2/v.mkv", ["/mnt/a"])  # NOT a substring
    assert not paths.is_preferred("/mnt/a/v.mkv", [])


def test_excluded_boundary():
    assert paths.is_excluded("/mnt/ignore/x.mp4", ["/mnt/ignore"])
    assert not paths.is_excluded("/mnt/ignore2/x.mp4", ["/mnt/ignore"])
    assert not paths.is_excluded("/mnt/x.mp4", [])


def test_parse_list():
    assert paths.parse_list("a b,c") == ["a", "b", "c"]
    assert paths.parse_list("") == []
    assert paths.parse_list("a/") == ["a"]
