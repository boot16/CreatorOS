# Creator DNA (DNA-01)

Creator DNA is a versioned, evidence-backed model of what a creator has published, how it is packaged, how it performs, and how those observable characteristics change. It is not a biography, a single score, an opportunity recommendation, or Creator Intent. Intent remains a separate, user-provided record and is never read by the DNA computation.

## Inputs and evidence

The YouTube sync stores canonical `creator_videos`, append-only metric snapshots, and channel snapshots. Video titles and descriptions, publish time, duration, and the latest views/likes/comments are **OBSERVED**. Distributions, age, views-per-day, engagement, median baseline, percentiles, relative performance, and evolution deltas are **CALCULATED**. A structured LLM classifies only an individual video’s topic, subtopics, format, hook, tone, story structure, presentation style, content promise, entities, and likely content intent; these are **INFERRED**. Creator Intent is **USER_PROVIDED** and outside this pipeline.

Each conclusion carries classification, normalized confidence, and references to supporting canonical video IDs. Snapshots retain source snapshot IDs; analyses retain the exact content hash. No transcript or long content copy is stored in DNA.

## Per-video analysis and reuse

`VideoContentAnalysis` is append-only and indexed by video, source hash, pipeline version, prompt version, model, and creation time. The source hash is SHA-256 of normalized title and description. An unchanged video with compatible `DNA_PIPELINE_VERSION=1.0`, `VIDEO_ANALYSIS_PROMPT_VERSION=1.0`, and the configured `LLM_MODEL` uses its saved analysis; changed content or model is classified again. Analyses run with a maximum of three concurrent LLM calls. A malformed answer is retried once by the shared structured-output service, then that video is counted as a failure instead of poisoning the entire run.

## Six dimensions

- Topic DNA: normalized per-video topics/subtopics, share, confidence, observed-video evidence, and topic performance.
- Format DNA: primary/secondary format aggregation; preferred means most published, while high-performing means historically highest relative performance.
- Creative DNA: distributions of hook, tone, story structure, presentation, and content promises.
- Audience DNA: only likely content intent from the creator’s published content. Engagement affinity, demographics, questions, and detailed interests are unavailable until comment/audience signals are ingested.
- Performance DNA: latest observed metrics, engagement rate `(likes + comments) / views` (zero when views are zero), age days, views/day, median creator views baseline, percentile, and age-cohort relative performance.
- Evolution DNA: core identity, current identity, and emerging identity for topics, formats, and hooks.

## Deterministic aggregation

The creator baseline is median current views. A video is compared with its age cohort (`0–7`, `8–30`, `31–90`, `90+` days) when that cohort has at least three videos; otherwise it uses the creator median. Percentile is the share of available videos at or below that video’s view count. This is descriptive historical correlation, never causal language.

Topic/format/hook combinations are emitted only with at least three supporting videos. Their relative performance is the mean of the constituent videos’ normalized performance.

Recent means the last 90 days, with older content as historical. Because initial sync only imports recent uploads, when no older record exists the code explicitly falls back to an available-data chronological split and labels the method. A characteristic is emerging only with at least three recent videos, at least 25% recent share, and at least a 20 percentage-point rise versus historical share. A one-video anomaly is not emerging.

Aggregate confidence is deterministic: `0.35 * evidence_amount + 0.30 * agreement + 0.25 * mean_inference_confidence + 0.10 * successful_analysis_rate`, where evidence amount is `min(1, sqrt(sample_size / 10))`. Values are rounded to three decimal places.

## Thresholds, snapshots, and API

Fewer than five usable videos returns `insufficient_data`; five to nine returns `provisional`; ten or more returns `computed`. Usable means a titled canonical video with a latest metric snapshot. Every terminal run persists a new immutable `creator_dna_snapshots` document with window metadata, source references, versions, model, result dimensions, and safe run metadata. Identical current source content/metrics plus matching versions returns the existing equivalent snapshot; its source fingerprint prevents an identical sync from causing re-analysis. A changed title/description invokes one analysis; changed metrics recompute only deterministic aggregates.

`POST /api/v1/dna/compute` resolves the creator solely from the authenticated session, persists a `computing` state, and starts bounded background work. `GET /api/v1/dna` returns that creator’s latest state/snapshot. The current in-process FastAPI background task is deliberately bounded but not durable across a process restart; replace it with a persistent job queue before multi-instance production deployment.

## Known limitations

YouTube current cumulative metrics do not provide a true historical growth curve, retention, CTR, watch time, comment text, detailed audience analytics, or demographics. Views/day is therefore descriptive only and no forecasting is performed. Sync currently fetches up to 20 recent uploads, so available history may be incomplete. Demo mode continues to render seeded Alex data, visibly isolated by the existing demo mode; production endpoints never return it.
