import pytest

from models.domain import ActivityEvent, CreatorLearnedPrefs
import services.learned_prefs as lp


class FakeEvents:
    def __init__(self, events): self.events = events
    async def list_for_creator(self, creator_id, since=None, limit=200):
        return [event for event in self.events if not since or event.created_at > since]


class FakePrefs:
    def __init__(self, existing=None): self.existing, self.saved = existing, None
    async def get(self, creator_id): return self.existing
    async def upsert(self, prefs): self.saved = prefs; return prefs


def event(day):
    return ActivityEvent(project_id="project", creator_id="creator", event_type="creative_object_updated",
                         metadata={"fields": ["content"]}, created_at=f"2026-09-0{day}T00:00:00+00:00")


@pytest.mark.asyncio
async def test_below_threshold_is_noop(monkeypatch):
    prefs = FakePrefs()
    monkeypatch.setattr(lp, "ActivityEventRepo", lambda db: FakeEvents([event(1)]))
    monkeypatch.setattr(lp, "LearnedPrefsRepo", lambda db: prefs)
    result = await lp.maybe_fold_in(None, "creator")
    assert result is None and prefs.saved is None


@pytest.mark.asyncio
async def test_fold_updates_existing_profile(monkeypatch):
    existing = CreatorLearnedPrefs(creator_id="creator", likes=["short titles"], signal_count=2)
    prefs = FakePrefs(existing)
    monkeypatch.setattr(lp, "ActivityEventRepo", lambda db: FakeEvents([event(i) for i in range(1, 5)]))
    monkeypatch.setattr(lp, "LearnedPrefsRepo", lambda db: prefs)

    async def llm(system, user, session_id, schema):
        assert "short titles" in user
        return lp._FoldedPrefs(likes=["short titles", "personal-story hooks"])
    monkeypatch.setattr(lp, "call_structured", llm)

    result = await lp.maybe_fold_in(None, "creator")
    assert result.likes == ["short titles", "personal-story hooks"]
    assert result.signal_count == 6 and result.last_event_at == event(4).created_at
    assert prefs.saved is result


@pytest.mark.asyncio
async def test_failure_preserves_existing_profile(monkeypatch):
    existing, prefs = CreatorLearnedPrefs(creator_id="creator"), FakePrefs(CreatorLearnedPrefs(creator_id="creator"))
    monkeypatch.setattr(lp, "ActivityEventRepo", lambda db: FakeEvents([event(i) for i in range(1, 5)]))
    monkeypatch.setattr(lp, "LearnedPrefsRepo", lambda db: prefs)
    async def fail(*args, **kwargs): raise RuntimeError("unavailable")
    monkeypatch.setattr(lp, "call_structured", fail)
    result = await lp.maybe_fold_in(None, "creator")
    assert result is prefs.existing and prefs.saved is None


@pytest.mark.asyncio
async def test_force_bypasses_threshold(monkeypatch):
    prefs = FakePrefs()
    monkeypatch.setattr(lp, "ActivityEventRepo", lambda db: FakeEvents([event(1)]))
    monkeypatch.setattr(lp, "LearnedPrefsRepo", lambda db: prefs)
    async def llm(*args, **kwargs): return lp._FoldedPrefs(patterns=["ships weekly"])
    monkeypatch.setattr(lp, "call_structured", llm)
    result = await lp.maybe_fold_in(None, "creator", force=True)
    assert result.patterns == ["ships weekly"] and prefs.saved is result


@pytest.mark.asyncio
async def test_no_new_events_preserves_existing_profile(monkeypatch):
    existing = CreatorLearnedPrefs(creator_id="creator", likes=["concise hooks"])
    prefs = FakePrefs(existing)
    monkeypatch.setattr(lp, "ActivityEventRepo", lambda db: FakeEvents([]))
    monkeypatch.setattr(lp, "LearnedPrefsRepo", lambda db: prefs)

    result = await lp.maybe_fold_in(None, "creator", force=True)
    assert result is existing and prefs.saved is None
