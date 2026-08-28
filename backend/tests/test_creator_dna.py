"""Deterministic DNA-01 aggregation tests (no external LLM or YouTube required)."""
import os, sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_dna")
sys.path.insert(0, "/app/backend")

from models.domain import VideoContentAnalysis
from services.creator_dna import (
    CreatorDNAService, VideoAnalysisOutput, _distribution, normalize_topic,
    source_content_hash, MIN_COMBINATION_SAMPLE,
)


def _analysis(n, topic="ai", format="tutorial", hook="problem", confidence=.8):
    return VideoContentAnalysis(creator_id="c", creator_video_id=f"v{n}", topic=topic, format=format,
        hook_type=hook, tone="practical", storytelling_structure="problem_solution", presentation_style="educational",
        model="m", prompt_version="1", pipeline_version="1", source_content_hash=str(n), inference_confidence=confidence)


def _records(count=10):
    now = datetime.now(timezone.utc)
    result = []
    for n in range(count):
        experiment = n >= 6
        analysis = _analysis(n, format="experiment" if experiment else "tutorial", hook="challenge" if experiment else "problem")
        video = SimpleNamespace(id=f"v{n}", published_at=(now - timedelta(days=10+n)).isoformat())
        metric = SimpleNamespace(views=200 if experiment else 100, likes=10, comments=2)
        result.append((analysis, video, metric))
    return result


def test_topic_normalization_and_distribution_evidence():
    assert normalize_topic("Artificial intelligence tools") == "ai_tools"
    items = _distribution([("ai_tools", "v1"), ("ai_tools", "v2"), ("automation", "v3")], "topic", {"v1": .8, "v2": .8, "v3": .8})
    assert items[0]["label"] == "ai_tools"
    assert items[0]["share"] == 2 / 3
    assert items[0]["evidence"][0]["video_id"] == "v1"


def test_unknown_format_is_safe_other_and_hash_changes_with_content():
    output = VideoAnalysisOutput(topic="AI", format="unrecognised format", hook_type="what?", tone="Calm",
        storytelling_structure="simple", presentation_style="unrecognised", inference_confidence=.7)
    assert output.format == output.hook_type == output.presentation_style == "other"
    assert source_content_hash("A", "x") != source_content_hash("A", "changed")


def test_performance_uses_median_and_combination_threshold():
    service = object.__new__(CreatorDNAService)
    performance, per_video = service._performance(_records(), datetime.now(timezone.utc))
    assert performance["baseline"]["value"] == 100
    assert all(v["views_relative_to_creator_baseline"] >= 0 for v in performance["videos"])
    winning = performance["winning_combinations"]
    assert winning and all(x["sample_size"] >= MIN_COMBINATION_SAMPLE for x in winning)
    assert any(x["values"] == ["ai", "experiment"] for x in winning)
    assert per_video["v0"]["relative"] > 0


def test_zero_views_has_safe_engagement_rate():
    service = object.__new__(CreatorDNAService)
    records = _records(5)
    records[0][2].views = 0
    performance, _ = service._performance(records, datetime.now(timezone.utc))
    assert performance["videos"][0]["engagement_rate"] == 0


def test_evolution_requires_three_recent_videos_not_one_anomaly():
    service = object.__new__(CreatorDNAService)
    now = datetime.now(timezone.utc)
    relevant = []
    for n in range(10):
        topic = "ai_agents" if n == 9 else "ai"
        a = _analysis(n, topic=topic)
        v = SimpleNamespace(id=f"v{n}", published_at=(now - timedelta(days=20 if n >= 7 else 140+n)).isoformat())
        relevant.append((a, v, SimpleNamespace(views=100, likes=0, comments=0)))
    evo = service._evolution(relevant, {}, now, {a.creator_video_id: .8 for a, _, _ in relevant})
    assert not evo["emerging_identity"]["topics"]


def test_evolution_detects_sustained_recent_topic_shift():
    service = object.__new__(CreatorDNAService)
    now = datetime.now(timezone.utc)
    relevant = []
    for n in range(10):
        topic = "ai_agents" if n >= 7 else "ai"
        a = _analysis(n, topic=topic)
        # Seven historical AI videos; three current AI agents videos.
        days = 15 if n >= 7 else 140 + n
        relevant.append((a, SimpleNamespace(id=f"v{n}", published_at=(now - timedelta(days=days)).isoformat()),
                         SimpleNamespace(views=100, likes=0, comments=0)))
    evo = service._evolution(relevant, {}, now, {a.creator_video_id: .8 for a, _, _ in relevant})
    assert "ai" in [x["value"] for x in evo["core_identity"]["topics"]]
    assert [x["value"] for x in evo["emerging_identity"]["topics"]] == ["ai_agents"]


def test_confidence_is_bounded_and_more_evidence_is_not_less_confident():
    sparse = _distribution([("ai", "v1")], "topic", {"v1": .8})[0]["confidence"]
    broad = _distribution([("ai", f"v{n}") for n in range(10)], "topic", {f"v{n}": .8 for n in range(10)})[0]["confidence"]
    assert 0 <= sparse <= 1
    assert broad > sparse
