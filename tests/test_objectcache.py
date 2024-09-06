"""Test jigsawwm.objectcache module"""

from threading import Thread
from jigsawwm.objectcache import ObjectCache, ChangeDetector


class Foo:
    """A dummy class for testing"""


def test_object_cache_concurrency():
    """Test the ObjectCache class"""
    cache = ObjectCache()
    cache._create = Foo
    result = [None for i in range(100)]

    def concurrent_get(i):
        result[i] = cache.get("foo")
        return cache.get(i)

    thread = [Thread(target=concurrent_get, args=(i,)) for i in range(len(result))]

    for t in thread:
        t.start()
    for t in thread:
        t.join()

    id1 = id(result[0])
    for r in result[1:]:
        assert id1 == id(r)


def test_change_detector():
    """Test the ChangeDetector class"""
    # first round
    detector = ChangeDetector()
    detector.current_keys = lambda: {1, 2, 3}
    changed, new_keys, removed_keys = detector.detect_changes()
    assert changed
    assert new_keys == {1, 2, 3}
    assert removed_keys == set()
    # second round: no change
    changed, new_keys, removed_keys = detector.detect_changes()
    assert not changed
    assert new_keys == set()
    assert removed_keys == set()
    # second round: removed
    detector.current_keys = lambda: {2}
    changed, new_keys, removed_keys = detector.detect_changes()
    assert changed
    assert new_keys == set()
    assert removed_keys == {1, 3}
