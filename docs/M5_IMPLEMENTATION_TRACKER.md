# CreatorOS M5 Implementation Tracker

**Branch:** `auth-stabilization`  
**Objective:** Turn the working project workflow into a creative planning system that carries a creator from a raw thought to an execution-ready creative specification, then add creator intelligence/strategy on top.

## Product contract

CreatorOS must understand the creator's idea and perspective before generating. It must develop genuinely different creative directions, let the creator choose/refine, determine what is required to execute the selected direction, resolve research/evidence gaps, build a medium-aware creative plan, generate from that plan, and critique the result against the plan.

Chat is a control interface. Persistent project state is the source of truth. Generation is the consequence of planning, not a substitute for planning.

## Status vocabulary

- TODO — not started
- IN PROGRESS — implementation underway
- IMPLEMENTED — code committed, runtime not yet verified
- TESTED — automated/local test passed
- RUNTIME VERIFIED — exercised successfully in the real local workflow
- PRODUCT VALIDATED — output/UX judged materially useful in creator use

## M5.1 — Creative Workflow Engine

| ID | Deliverable | Status | Acceptance criteria |
|---|---|---|---|
| 5.1.0 | Audit current project workflow | IMPLEMENTED | Existing Project, Brief, Directions, Outline, CreativeObject, Source, Chat and AI service mapped before changes |
| 5.1.1 | Idea Understanding model | IMPLEMENTED | Raw thought becomes structured idea/perspective/intent/audience/unknowns; creator-provided vs inferred information remains distinguishable |
| 5.1.2 | Idea Understanding API | IMPLEMENTED | Owned project can request, retrieve, confirm/edit and persist understanding |
| 5.1.3 | Idea Understanding UX | IN PROGRESS | Creator sees “what CreatorOS understood”, can correct it, and is not forced through a questionnaire |
| 5.1.4 | Creative Direction v2 | TODO | 2–3 meaningfully different treatments, not rewritten hooks; direction records premise, angle, promise, treatment, risks and unresolved questions |
| 5.1.5 | Direction actions | TODO | Select, reject, refine and combine without losing project state |
| 5.1.6 | Readiness assessment | TODO | System identifies only material unresolved decisions before planning |
| 5.1.7 | Format Requirements Engine | TODO | Deterministic schema defines required planning fields per medium; AI reasons/fills within that schema |
| 5.1.8 | Reel Creative Plan v1 | TODO | Reel plan contains objective, takeaway, duration, beats, timing, script/audio, shot/framing, visual/B-roll, on-screen text, assets and evidence requirements |
| 5.1.9 | Research/evidence orchestration | TODO | Research is triggered by plan gaps/claims; provenance and uncertainty are preserved; no fabricated citations |
| 5.1.10 | Generation from plan | TODO | Content generation consumes approved creative specification instead of rediscovering decisions |
| 5.1.11 | Plan-aware critique | TODO | Output is checked against intent, selected direction, plan, evidence, format and duration |
| 5.1.12 | Workflow progress UX | TODO | Workspace communicates Idea → Direction → Develop → Plan → Create → Review and preserves state across refresh/login |
| 5.1.13 | M5.1 regression suite | IN PROGRESS | Ownership, persistence, structured-output validation, stage transitions and existing M3/M4 workflow remain covered |
| 5.1.14 | Product validation set | TODO | At least 5 weak starting ideas across creator types produce plans materially stronger than a one-shot generic outline |

## M5.2 — Creator Intelligence + Strategy

This includes the previously defined M5 creator-intelligence work. It is deliberately layered on top of M5.1 so intelligence improves real creative decisions rather than becoming another dashboard.

| ID | Deliverable | Status | Acceptance criteria |
|---|---|---|---|
| 5.2.1 | Creator Graph v1 | TODO | Structured creator identity, goals, audience, strengths, interests, constraints, formats and stated preferences |
| 5.2.2 | Cold-start creator understanding | TODO | New creator with zero social/content history receives useful hypotheses without pretending inference is fact |
| 5.2.3 | Learned preference evidence model | TODO | Preference includes classification/source, confidence, evidence count and recency instead of flat permanent likes/dislikes |
| 5.2.4 | Behavioral learning | TODO | Select/reject/refine/regenerate/keep/edit/finish signals can update creator intelligence conservatively |
| 5.2.5 | Creator-aware planning | TODO | Relevant creator intelligence is injected into idea development, directions, planning, generation and critique |
| 5.2.6 | Creator-market-fit hypotheses | TODO | System can represent/test audience × positioning × format × creator-strength hypotheses |
| 5.2.7 | Experiments | TODO | New creators can test territories/assumptions rather than being assigned a permanent niche |
| 5.2.8 | Strategy / next-best-action | TODO | CreatorOS can recommend the next useful creative experiment/action with traceable reasons |
| 5.2.9 | External opportunity evidence foundation | TODO | Opportunities can later combine creator fit with real external evidence without fabricated trend metrics |
| 5.2.10 | Longitudinal validation | TODO | Project B recommendations demonstrably use evidence learned from Project A while preserving user control |

## Cross-cutting engineering work

| ID | Deliverable | Status | Acceptance criteria |
|---|---|---|---|
| X.1 | Separate environment from data mode | TODO | `APP_ENV=development|staging|production` is independent of `DATA_MODE=demo|real`; local real-user testing no longer requires demo mode |
| X.2 | User isolation | IN PROGRESS | User A cannot read/write User B project intelligence or creative plans |
| X.3 | Observability | TODO | Structured logs identify workflow stage/task without leaking prompts/secrets |
| X.4 | Failure/recovery UX | TODO | AI/research failures preserve prior project state and support retry |
| X.5 | Cost/context controls | TODO | Prompt context is bounded, relevant and observable; no repeated full-project dumping where avoidable |

## Current architecture audit (2026-09-11)

Preserve and extend:
- `Project` + ownership model
- `ProjectBrief` as legacy/basic project metadata
- `CreativeObject` for generated/editable artifacts
- `ProjectSource` for attached user evidence
- `ProjectChatMessage` for conversation, not canonical project state
- `ActivityEvent` as behavioral signal stream
- `CreatorLearnedPrefs` temporarily; supersede in M5.2 with evidence-bearing preferences
- `services.llm` provider abstraction and structured Pydantic validation
- `ProjectContext` owner-scoped context assembly

Implemented M5.1 foundation:
- Dedicated `IdeaUnderstanding` domain model with per-field origin and confidence.
- Dedicated `idea_understandings` Mongo collection with one canonical document per project/creator.
- Generate, retrieve and confirm/edit endpoints under `/api/v1/projects/{project_id}/idea-understanding`.
- AI extraction service uses structured output and never marks AI extraction as creator-confirmed.
- User edits are promoted to `confirmed` with confidence 1.0.
- Activity events record understanding generation/confirmation without storing the full raw prompt in event metadata.
- Focused unit tests cover origin behavior, confidence clamping, list deduplication and route registration. No CI runner is currently attached to the branch, so these tests are committed but not yet classified TESTED.

Current gaps relevant to M5:
- `ProjectBrief` cannot represent raw idea vs creator perspective vs inference/unknowns; M5 now uses the dedicated `IdeaUnderstanding` model for this state.
- Direction schema is shallow (`angle`, `takeaway`, `format`, `tone`, `why_it_works`).
- Reel planning is currently a generic short outline (`hook`, 3–5 beats, ending), not a production specification.
- Research currently summarizes only supplied context/sources; there is no evidence-task orchestration yet.
- `CreativeObject.content` is plain text, so canonical structured planning state needs dedicated models rather than encoding critical state into prose.
- Current learned preferences are flat lists and lack confidence/evidence provenance.

## Implementation rule

Do not mark a milestone complete because an endpoint returns HTTP 200. Each increment moves through IMPLEMENTED → TESTED → RUNTIME VERIFIED → PRODUCT VALIDATED. Existing working workflow must remain usable while M5 is introduced incrementally.
