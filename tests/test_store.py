from league_finder.models import League
from league_finder.store import Store


def league(source_id, **kw):
    return League(source="bowlero", source_id=source_id, name=f"League {source_id}", url="u", **kw)


def sync(store, leagues):
    return store.sync(store.start_run("bowlero"), "bowlero", leagues)


def test_add_update_remove():
    store = Store(":memory:")
    r = sync(store, [league("a"), league("b")])
    assert (r.added, r.updated, r.removed) == (2, 0, 0)

    r = sync(store, [league("a", day_of_week="Tuesday")])
    assert (r.seen, r.added, r.updated, r.removed) == (1, 0, 1, 1)
    [only] = store.active_leagues()
    assert only.source_id == "a" and only.day_of_week == "Tuesday"


def test_unchanged_is_not_an_update():
    store = Store(":memory:")
    sync(store, [league("a")])
    r = sync(store, [league("a")])
    assert (r.added, r.updated, r.removed) == (0, 0, 0)


def test_removed_league_reappears():
    store = Store(":memory:")
    sync(store, [league("a")])
    sync(store, [])
    assert store.active_leagues() == []
    r = sync(store, [league("a")])
    assert r.updated == 1 and len(store.active_leagues()) == 1


def test_failed_run_keeps_existing_leagues():
    store = Store(":memory:")
    sync(store, [league("a")])
    store.fail_run(store.start_run("bowlero"), "boom")
    assert len(store.active_leagues()) == 1
