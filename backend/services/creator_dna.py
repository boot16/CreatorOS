"""DNA-01: evidence-backed Creator DNA computation.

The LLM only understands one video. All percentages, baselines, confidence,
status and evolution are deterministic aggregations of persisted records.
"""
import asyncio
import hashlib
import math
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from core.config import get_settings
from models.domain import CreatorDNASnapshot, DNAStatus, VideoContentAnalysis
from repositories import DNARepo, VideoAnalysisRepo, YouTubeSourceRepo
from services.llm import call_structured

DNA_PIPELINE_VERSION = "1.0"
VIDEO_ANALYSIS_PROMPT_VERSION = "1.0"
VIDEO_ANALYSIS_MODEL = f"anthropic/{get_settings().LLM_MODEL}"
MIN_PROVISIONAL_VIDEOS = 5
MIN_COMPUTED_VIDEOS = 10
MIN_COMBINATION_SAMPLE = 3
RECENT_DAYS = 90
MAX_CONCURRENT_ANALYSES = 3

FORMATS = {"tutorial", "experiment", "comparison", "commentary", "review", "explainer",
           "case_study", "interview", "challenge", "list", "news", "story", "vlog", "reaction", "other"}
HOOKS = {"question", "challenge", "bold_claim", "curiosity_gap", "problem", "result_first",
         "story", "contrarian", "demonstration", "other"}
PRESENTATION = {"first_person", "educational", "demonstration", "narrative", "analysis",
                "conversation", "documentary", "other"}
TOPIC_ALIASES = {
    "ai tools": "ai_tools", "artificial intelligence tools": "ai_tools", "ai software": "ai_tools",
    "ai apps": "ai_tools", "artificial intelligence": "ai", "artificial intelligence productivity": "ai_productivity",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _slug(value: str) -> str:
    return "_".join("".join(c.lower() if c.isalnum() else " " for c in (value or "")).split()) or "other"


def normalize_topic(value: str) -> str:
    raw = _slug(value)
    return TOPIC_ALIASES.get(raw.replace("_", " "), raw)


def source_content_hash(title: str, description: str) -> str:
    return hashlib.sha256(f"{title.strip()}\n{description.strip()}".encode("utf-8")).hexdigest()


class VideoAnalysisOutput(BaseModel):
    """Strict contract for the *single-video* inference, not final DNA."""
    topic: str = Field(min_length=1, max_length=80)
    subtopics: list[str] = Field(default_factory=list, max_length=8)
    format: str
    secondary_format: Optional[str] = None
    hook_type: str
    tone: str = Field(min_length=1, max_length=80)
    storytelling_structure: str = Field(min_length=1, max_length=120)
    presentation_style: str
    audience_intent: Optional[str] = Field(default=None, max_length=160)
    content_promise: Optional[str] = Field(default=None, max_length=240)
    entities: list[str] = Field(default_factory=list, max_length=12)
    inference_confidence: float = Field(ge=0, le=1)

    @field_validator("format", "secondary_format", mode="before")
    @classmethod
    def valid_format(cls, value):
        if value is None:
            return value
        return _slug(str(value)) if _slug(str(value)) in FORMATS else "other"

    @field_validator("hook_type", mode="before")
    @classmethod
    def valid_hook(cls, value):
        return _slug(str(value)) if _slug(str(value)) in HOOKS else "other"

    @field_validator("presentation_style", mode="before")
    @classmethod
    def valid_presentation(cls, value):
        return _slug(str(value)) if _slug(str(value)) in PRESENTATION else "other"


ANALYSIS_SYSTEM = """You classify one YouTube video. Return only JSON matching the supplied schema.
Do not calculate distributions, performance, creator traits, demographics, or confidence beyond this video's inference_confidence.
Use `other` when a canonical format, hook, or presentation style is not supported by the source."""


def _evidence(video_ids: list[str], signal: str, source: str = "youtube_api") -> list[dict]:
    return [{"video_id": video_id, "signal": signal, "source": source} for video_id in video_ids]


def _fact(value, classification: str, confidence: float, video_ids: list[str], signal: str) -> dict:
    return {"value": value, "classification": classification, "confidence": round(max(0, min(1, confidence)), 3),
            "evidence": _evidence(video_ids, signal)}


def _distribution(values: list[tuple[str, str]], field: str, confidences: Optional[dict[str, float]] = None) -> list[dict]:
    grouped = defaultdict(list)
    for value, video_id in values:
        grouped[value].append(video_id)
    total = len(values) or 1
    result = []
    for value, ids in grouped.items():
        agreement = len(ids) / total
        inference = statistics.mean(confidences.get(video_id, 1.0) for video_id in ids) if confidences else 1.0
        confidence = _aggregate_confidence(len(values), agreement, inference)
        result.append({"label": value, "share": round(len(ids) / total, 4), "sample_size": len(ids),
                       "classification": "CALCULATED", "confidence": confidence,
                       "evidence": _evidence(ids, f"{field} classification")})
    return sorted(result, key=lambda item: (-item["share"], item["label"]))


def _aggregate_confidence(sample_size: int, agreement: float, inference_confidence: float, success_rate: float = 1.0) -> float:
    # Evidence amount (up to 10), agreement, inference certainty and partial-failure penalty.
    amount = min(1.0, math.sqrt(sample_size / MIN_COMPUTED_VIDEOS))
    return round(0.35 * amount + 0.30 * agreement + 0.25 * inference_confidence + 0.10 * success_rate, 3)


class CreatorDNAService:
    def __init__(self, db, analysis_callable=None):
        self.sources = YouTubeSourceRepo(db)
        self.analyses = VideoAnalysisRepo(db)
        self.dna = DNARepo(db)
        self.db = db
        self.analysis_callable = analysis_callable

    async def current_source_fingerprint(self, creator_id: str) -> str:
        videos = await self.sources.list_videos(creator_id, limit=None)
        metrics = await self.sources.latest_metrics([v.id for v in videos])
        usable = [v for v in videos if v.title.strip() and v.id in metrics]
        return hashlib.sha256(repr(sorted([
            (v.id, source_content_hash(v.title, v.description or ""), metrics[v.id].views,
             metrics[v.id].likes, metrics[v.id].comments, v.published_at) for v in usable
        ])).encode()).hexdigest()

    async def compute_creator_dna(self, creator_id: str) -> CreatorDNASnapshot:
        self._run_started_at = time.monotonic()
        videos = await self.sources.list_videos(creator_id, limit=None)
        metrics = await self.sources.latest_metrics([v.id for v in videos])
        usable = [v for v in videos if v.title.strip() and v.id in metrics]
        source_ids = sorted([metrics[v.id].id for v in usable])
        channel = await self.sources.latest_channel_snapshot(creator_id)
        if channel:
            source_ids.append(channel.id)
        source_fingerprint = hashlib.sha256(repr(sorted([
            (v.id, source_content_hash(v.title, v.description or ""), metrics[v.id].views,
             metrics[v.id].likes, metrics[v.id].comments, v.published_at) for v in usable
        ])).encode()).hexdigest()
        existing = await self.dna.equivalent(creator_id, source_fingerprint, DNA_PIPELINE_VERSION,
                                             VIDEO_ANALYSIS_PROMPT_VERSION, [VIDEO_ANALYSIS_MODEL])
        if existing:
            return existing

        if len(usable) < MIN_PROVISIONAL_VIDEOS:
            return await self._persist(creator_id, DNAStatus.insufficient_data, source_ids, source_fingerprint, [], metrics, 0, 0, 0)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_ANALYSES)
        async def one(video):
            async with semaphore:
                try:
                    analysis, was_cached = await self._get_analysis(video)
                    return analysis, was_cached, None
                except Exception as exc:  # one video must not erase an otherwise useful snapshot
                    return None, False, str(exc)
        results = await asyncio.gather(*(one(v) for v in usable))
        completed = [r[0] for r in results if r[0] is not None]
        cache_hits = sum(1 for r in results if r[1])
        failed = sum(1 for r in results if r[2] is not None)
        if not completed and failed:
            return await self._persist(creator_id, DNAStatus.failed, source_ids, source_fingerprint, [], metrics, 0, cache_hits, failed)
        if len(completed) < MIN_PROVISIONAL_VIDEOS:
            return await self._persist(creator_id, DNAStatus.insufficient_data, source_ids, source_fingerprint, completed, metrics,
                                       len(completed) - cache_hits, cache_hits, failed)
        status = DNAStatus.computed if len(completed) >= MIN_COMPUTED_VIDEOS else DNAStatus.provisional
        return await self._persist(creator_id, status, source_ids, source_fingerprint, completed, metrics,
                                   len(completed) - cache_hits, cache_hits, failed)

    async def _get_analysis(self, video):
        content_hash = source_content_hash(video.title, video.description or "")
        cached = await self.analyses.compatible(video.id, content_hash, DNA_PIPELINE_VERSION,
                                                VIDEO_ANALYSIS_PROMPT_VERSION, VIDEO_ANALYSIS_MODEL)
        if cached:
            return cached, True
        prompt = (f"Title: {video.title}\nDescription: {video.description or '(none)'}\n"
                  "Classify this video. Use canonical format, hook_type, and presentation_style values where possible.")
        if self.analysis_callable:
            output = await self.analysis_callable(video, prompt)
            output = VideoAnalysisOutput.model_validate(output)
        else:
            output = await call_structured(ANALYSIS_SYSTEM, prompt, f"dna-video-{video.id}", VideoAnalysisOutput)
        analysis = VideoContentAnalysis(
            creator_id=video.creator_id, creator_video_id=video.id, topic=normalize_topic(output.topic),
            original_topic=output.topic, subtopics=[_slug(v) for v in output.subtopics], format=output.format,
            format_secondary=output.secondary_format, hook_type=output.hook_type, tone=_slug(output.tone),
            storytelling_structure=_slug(output.storytelling_structure), presentation_style=output.presentation_style,
            audience_intent=output.audience_intent, content_promise=output.content_promise, entities=output.entities,
            inference_confidence=output.inference_confidence, model=VIDEO_ANALYSIS_MODEL,
            prompt_version=VIDEO_ANALYSIS_PROMPT_VERSION, pipeline_version=DNA_PIPELINE_VERSION,
            source_content_hash=content_hash,
        )
        return await self.analyses.create(analysis), False

    async def _persist(self, creator_id, status, source_ids, source_fingerprint, analyses, metrics, llm_calls, cache_hits, failed):
        now = datetime.now(timezone.utc)
        video_docs = {v.id: v for v in await self.sources.list_videos(creator_id, limit=None)}
        relevant = [(a, video_docs.get(a.creator_video_id), metrics.get(a.creator_video_id)) for a in analyses]
        relevant = [(a, v, m) for a, v, m in relevant if v and m]
        dates = [_parse_dt(v.published_at) for _, v, _ in relevant if _parse_dt(v.published_at)]
        recent_cutoff = now.timestamp() - RECENT_DAYS * 86400
        recent_count = sum(1 for _, v, _ in relevant if _parse_dt(v.published_at) and _parse_dt(v.published_at).timestamp() >= recent_cutoff)
        meta = {"videos_analyzed": len(relevant), "cache_hits": cache_hits, "llm_calls": llm_calls,
                "failed_analyses": failed, "duration_ms": round((time.monotonic() - getattr(self, "_run_started_at", time.monotonic())) * 1000),
                "analysis_windows": {"ALL_AVAILABLE": len(relevant), "RECENT": recent_count,
                                     "HISTORICAL": len(relevant) - recent_count, "recent_days": RECENT_DAYS}}
        topic_counts = Counter(a.topic for a, _, _ in relevant)
        overall_confidence = (_aggregate_confidence(
            len(relevant), max(topic_counts.values()) / len(relevant),
            statistics.mean(a.inference_confidence for a, _, _ in relevant),
            len(relevant) / max(1, len(relevant) + failed),
        ) if relevant else 0.0)
        base = dict(creator_id=creator_id, version=await self.dna.next_version(creator_id), status=status,
                    source_snapshot_ids=source_ids, source_fingerprint=source_fingerprint, analysis_window="ALL_AVAILABLE", video_count=len(relevant),
                    confidence=overall_confidence,
                    earliest_video_at=min(dates).isoformat() if dates else None,
                    latest_video_at=max(dates).isoformat() if dates else None, computed_at=_now(),
                    pipeline_version=DNA_PIPELINE_VERSION, prompt_version=VIDEO_ANALYSIS_PROMPT_VERSION,
                    model_versions=[VIDEO_ANALYSIS_MODEL], computation_metadata=meta)
        if status in (DNAStatus.insufficient_data, DNAStatus.failed):
            return await self.dna.create(CreatorDNASnapshot(**base))
        performance, per_video = self._performance(relevant, now)
        confidence_by_id = {a.creator_video_id: a.inference_confidence for a, _, _ in relevant}
        topic = _distribution([(a.topic, a.creator_video_id) for a, _, _ in relevant], "topic", confidence_by_id)
        formats = _distribution([(a.format, a.creator_video_id) for a, _, _ in relevant], "format", confidence_by_id)
        success_rate = len(relevant) / max(1, len(relevant) + failed)
        topic_dna = {"core_topics": topic[:5], "topic_distribution": topic,
                     "subtopics": _distribution([(s, a.creator_video_id) for a, _, _ in relevant for s in a.subtopics], "subtopic", confidence_by_id),
                     "topic_performance": self._dimension_performance(relevant, per_video, "topic"),
                     "emerging_topics": []}
        format_dna = {"format_distribution": formats, "preferred_formats": formats[:3],
                      "high_performing_formats": self._dimension_performance(relevant, per_video, "format"),
                      "weak_formats": [x for x in self._dimension_performance(relevant, per_video, "format") if x["relative_performance"] < 1]}
        creative = {}
        for attr in ("hook_type", "tone", "storytelling_structure", "presentation_style"):
            creative[attr] = _distribution([(getattr(a, attr), a.creator_video_id) for a, _, _ in relevant], attr, confidence_by_id)
        creative["content_promises"] = _distribution([(a.content_promise or "unavailable", a.creator_video_id) for a, _, _ in relevant], "content promise", confidence_by_id)
        audience_intents = _distribution([(a.audience_intent or "unavailable", a.creator_video_id) for a, _, _ in relevant], "audience intent", confidence_by_id)
        audience = {"likely_content_intents": audience_intents, "recurring_interest_themes": "unavailable",
                    "content_needs": "unavailable", "engagement_affinity": "unavailable",
                    "limitations": "No comment text or audience analytics are ingested; demographics and recurring questions are unavailable."}
        evolution = self._evolution(relevant, per_video, now, confidence_by_id)
        topic_dna["emerging_topics"] = evolution["emerging_identity"]["topics"]
        base.update(topic_dna=topic_dna, format_dna=format_dna, creative_dna=creative, audience_dna=audience,
                    performance_dna=performance, evolution_dna=evolution)
        return await self.dna.create(CreatorDNASnapshot(**base))

    def _performance(self, relevant, now):
        records = []
        for analysis, video, metric in relevant:
            published = _parse_dt(video.published_at)
            age = max(0, (now - published).days) if published else None
            cohort = "unknown" if age is None else ("0_7" if age <= 7 else "8_30" if age <= 30 else "31_90" if age <= 90 else "90_plus")
            engagement = (metric.likes + metric.comments) / metric.views if metric.views > 0 else 0.0
            records.append({"analysis": analysis, "video": video, "metric": metric, "age": age, "cohort": cohort,
                            "views_per_day": metric.views / max(1, age or 1), "engagement": engagement})
        global_median = statistics.median([r["metric"].views for r in records])
        cohort_medians = {c: statistics.median([r["metric"].views for r in records if r["cohort"] == c])
                          for c in {r["cohort"] for r in records}}
        per_video = {}
        for r in records:
            cohort_values = [x["metric"].views for x in records if x["cohort"] == r["cohort"]]
            baseline = cohort_medians[r["cohort"]] if len(cohort_values) >= 3 else global_median
            views = r["metric"].views
            per_video[r["analysis"].creator_video_id] = {"relative": views / baseline if baseline else 0.0,
                "percentile": round(sum(x["metric"].views <= views for x in records) / len(records), 4), **r}
        combinations = self._combinations(records, per_video)
        return ({"baseline": {"metric": "views", "method": "median", "sample_size": len(records), "value": global_median,
                                "classification": "CALCULATED", "evidence": _evidence([r["video"].id for r in records], "latest metric snapshot")},
                 "age_normalization": {"method": "compare to cohort median when cohort has >=3 videos; otherwise creator median", "cohorts": ["0_7", "8_30", "31_90", "90_plus"]},
                 "videos": [{"video_id": r["video"].id, "views": r["metric"].views, "likes": r["metric"].likes, "comments": r["metric"].comments,
                              "video_age_days": r["age"], "views_per_day": round(r["views_per_day"], 3),
                              "engagement_rate": round(r["engagement"], 5), "views_relative_to_creator_baseline": round(per_video[r["analysis"].creator_video_id]["relative"], 4),
                              "performance_percentile": per_video[r["analysis"].creator_video_id]["percentile"], "classification": "CALCULATED"} for r in records],
                 "winning_combinations": combinations}, per_video)

    def _dimension_performance(self, relevant, per_video, attr):
        groups = defaultdict(list)
        for a, _, _ in relevant:
            groups[getattr(a, attr)].append(a.creator_video_id)
        return sorted([{"label": value, "sample_size": len(ids), "relative_performance": round(statistics.mean(per_video[i]["relative"] for i in ids), 4),
                        "confidence": _aggregate_confidence(len(relevant), len(ids) / len(relevant), statistics.mean(per_video[i]["analysis"].inference_confidence for i in ids)),
                        "classification": "CALCULATED", "evidence": _evidence(ids, f"{attr} x latest metrics")}
                       for value, ids in groups.items()], key=lambda x: -x["relative_performance"])

    def _combinations(self, records, per_video):
        groups = defaultdict(list)
        for r in records:
            a = r["analysis"]
            for label, values in (("topic_format", (a.topic, a.format)), ("format_hook", (a.format, a.hook_type)),
                                  ("topic_hook", (a.topic, a.hook_type)), ("topic_format_hook", (a.topic, a.format, a.hook_type))):
                groups[(label, values)].append(a.creator_video_id)
        results = []
        for (kind, values), ids in groups.items():
            if len(ids) < MIN_COMBINATION_SAMPLE:
                continue
            relative = statistics.mean(per_video[i]["relative"] for i in ids)
            results.append({"combination_type": kind, "values": list(values), "sample_size": len(ids),
                            "relative_performance": round(relative, 4), "confidence": _aggregate_confidence(len(records), len(ids) / len(records), statistics.mean(per_video[i]["analysis"].inference_confidence for i in ids)),
                            "classification": "CALCULATED", "supporting_video_ids": ids,
                            "evidence": _evidence(ids, "topic/format/hook and latest metrics")})
        return sorted(results, key=lambda x: -x["relative_performance"])

    def _evolution(self, relevant, per_video, now, confidence_by_id):
        recent_cutoff = now.timestamp() - RECENT_DAYS * 86400
        recent = [(a, v) for a, v, _ in relevant if (_parse_dt(v.published_at) and _parse_dt(v.published_at).timestamp() >= recent_cutoff)]
        historical = [(a, v) for a, v, _ in relevant if (a, v) not in recent]
        # Phase 1 imports recent data only: explicitly use an available chronological split if no 90-day history.
        method = "90-day recent vs older available content"
        if not historical and len(relevant) >= MIN_PROVISIONAL_VIDEOS:
            ordered = sorted([(a, v) for a, v, _ in relevant], key=lambda x: x[1].published_at or "")
            historical, recent = ordered[:len(ordered)//2], ordered[len(ordered)//2:]
            method = "available-data chronological split (no older-than-90-day source data)"
        def dist(items, attr):
            c = Counter(getattr(a, attr) for a, _ in items)
            return {k: v / len(items) for k, v in c.items()} if items else {}
        outputs = {"method": method, "core_identity": {}, "current_identity": {}, "emerging_identity": {}}
        for attr, name in (("topic", "topics"), ("format", "formats"), ("hook_type", "hooks")):
            all_d, recent_d, historical_d = dist([(a, v) for a, v, _ in relevant], attr), dist(recent, attr), dist(historical, attr)
            core = [k for k, share in all_d.items() if share >= 0.2]
            current = [k for k, share in recent_d.items() if share >= 0.2]
            emerging = [k for k, share in recent_d.items() if share >= 0.25 and share - historical_d.get(k, 0) >= 0.20 and sum(getattr(a, attr) == k for a, _ in recent) >= 3]
            ids_for = lambda value, group: [a.creator_video_id for a, _ in group if getattr(a, attr) == value]
            outputs["core_identity"][name] = [_fact(k, "CALCULATED", _aggregate_confidence(len(relevant), all_d[k], statistics.mean(confidence_by_id[i] for i in ids_for(k, [(a, v) for a, v, _ in relevant]))), ids_for(k, [(a, v) for a, v, _ in relevant]), f"stable {attr}") for k in core]
            outputs["current_identity"][name] = [_fact(k, "CALCULATED", _aggregate_confidence(len(recent), recent_d[k], statistics.mean(confidence_by_id[i] for i in ids_for(k, recent))), ids_for(k, recent), f"recent {attr}") for k in current]
            outputs["emerging_identity"][name] = [_fact(k, "CALCULATED", _aggregate_confidence(len(recent), recent_d[k] - historical_d.get(k, 0), statistics.mean(confidence_by_id[i] for i in ids_for(k, recent))), ids_for(k, recent), f"increased recent {attr}") for k in emerging]
        return outputs
