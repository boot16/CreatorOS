# CreatorOS — Production Foundation (Phase 1)

## Overview
Phase 1 establishes the architectural boundaries required before real Creator DNA, recommendations, workspaces, or collaboration can be built on top. It does **not** implement DNA calculation, opportunity generation, or trend ingestion — those are subsequent phases.

## Domain entities

```
User               (auth identity, one per Google account)
  └── Workspace        (owned by user; slug-unique)
        ├── WorkspaceMember (role: owner | member)
        └── Creator        (one creator profile per user in Phase 1)
              ├── ConnectedPlatform  (per external platform: youtube today)
              │     └── PlatformCredential (encrypted OAuth tokens, isolated collection)
              ├── YouTubeChannelSnapshot   (versioned raw source snapshots)
              ├── CreatorVideo             (canonical video record)
              │     └── VideoMetricSnapshot (views/likes/comments over time)
              ├── CreatorIntent            (goals, topics, formats, audience)
              └── CreatorDNASnapshot       (versioned; status enum; NOT populated yet)
```

## Identity flow

Every request enters:
```
core.identity.resolve_identity(db, session_cookie) → CurrentUser
```

`CurrentUser` fields: `user_id`, `creator_id`, `workspace_id`, `is_authenticated`, `is_demo`.

Rules:
- Valid session → real, server-owned identity
- No session + `DATA_MODE=demo` → demo identity (Alex workspace)
- No session + `DATA_MODE=production` → anonymous (never authorized to mutate)

**The frontend can never override `creator_id` / `workspace_id`.** Any caller-supplied `from_creator_id` in requests is ignored in production paths.

## Data mode

`DATA_MODE` env var: `demo` or `production`.

- Providers are selected at request time via `providers.make_*_provider()` factories.
- Demo providers return fixtures (Alex, Sarah, seeded trends/opportunities).
- Production providers return authenticated persisted entities **or** an honest `not_computed` / empty state — never Alex.

## Ownership model

- `Workspace.owner_user_id` is the canonical owner.
- `Creator.workspace_id` establishes membership.
- Production creator lookups verify `creator.workspace_id == requester.workspace_id`.
- Repositories are the only layer that touches Mongo directly — no route touches `db.<collection>` for domain writes.

## YouTube sync flow

```
POST /api/v1/sync/youtube (rate-limited: 5 / 5 min per user)
  ↓ services.youtube_sync.YouTubeSyncService(db).sync(creator_id)
  ↓ resolve ConnectedPlatform + PlatformCredential (decrypt access_token)
  ↓ fetch channel, uploads playlist, videos, metrics via YouTube Data API v3
  ↓ persist YouTubeChannelSnapshot
  ↓ upsert CreatorVideo (unique on (creator_id, external_video_id) — idempotent)
  ↓ insert VideoMetricSnapshot (append-only)
  ↓ mark ConnectedPlatform.last_synced_at
  ← SyncResultResponse { videos_seen, videos_created, videos_updated, ... }
```

Second run with same channel state: **0 created, N updated, no duplicates.**

## Creator Intent

Onboarding goals now persist. Frontend calls `PUT /api/v1/creator-intent` when logged in; ignored (no error) when not, so demo works. Load with `GET /api/v1/creator-intent`.

## Creator DNA (schema only)

`CreatorDNASnapshot` exists with fields: `topic_dna`, `format_dna`, `creative_dna`, `audience_dna`, `performance_dna`, `evolution_dna`, `source_snapshot_ids`, `pipeline_version`, `version`, `status` (`not_computed | insufficient_data | computing | ready | error`).

Production creators without DNA receive `{ status: "not_computed" }` — never Alex's DNA.

## Encryption

`APP_ENCRYPTION_KEY` (Fernet key, 32-byte urlsafe base64) is required in production. Access + refresh tokens are encrypted at rest via `core.encryption.encrypt/decrypt`. Tokens never traverse `/api/**` responses.

## Sessions

`Session.expires_at` is set server-side; `resolve_identity` validates + deletes expired sessions. Cookie is `HttpOnly`, `Secure`, `SameSite=lax`, 30-day max age (configurable via `SESSION_MAX_AGE`).

## CORS

`CORS_ORIGINS` is a comma-separated whitelist. `*` is refused when `DATA_MODE=production`.

## Rate limiting

`core.rate_limit.RateLimiter` is a simple in-memory sliding window (single-process). Preset budgets in `BUDGETS`:
- `llm_idea_lab` — 20 / hour per identity
- `llm_script_refine` — 30 / hour
- `llm_studio_chat` — 60 / hour
- `oauth_login` — 10 / 10 min
- `collab_proposal` — 10 / hour

Swap for Redis in Phase 3 without touching call sites.

## LLM cache versioning

`llm_cache_v2` doc:
```
{ cache_kind, entity_id, entity_version, data_version, prompt_version, model, key_hash, value, created_at, expires_at }
```

`key_hash` is `sha256(cache_kind|entity_id|entity_version|data_version|prompt_version|model)`. Bumping any component invalidates the cache without deletion.

## Structured LLM output

Responses that must be structured (`IdeaLabOutput`, `OppBulletsOutput`, `TrendExplanationOutput`) go through `services.llm.call_structured(schema=...)` which validates via Pydantic, retries once with a repair prompt, and raises `LLM_PARSE_ERROR` (502) with a safe message on failure.

## Error contract

All errors return:
```json
{ "error": { "code": "YOUTUBE_NOT_CONNECTED", "message": "..." } }
```

Codes are in `core.errors.Codes`.

## Indexes

Created idempotently on startup by `db.indexes.ensure_indexes(db)`:
- unique: `users.id`, `users.google_sub`, `sessions.sid`, `workspaces.id`, `workspaces.slug`, `workspace_members(workspace_id,user_id)`, `creators.id`, `creators.user_id`, `connected_platforms.id`, `platform_credentials.connected_platform_id`, `creator_videos(creator_id,external_video_id)`, `creator_intent.creator_id`, `llm_cache_v2.key_hash`
- non-unique: `sessions.user_id`, `sessions.expires_at`, `workspaces.owner_user_id`, `creators.workspace_id`, `connected_platforms(creator_id,platform)`, `youtube_channel_snapshots(creator_id,captured_at)`, `video_metric_snapshots(creator_video_id,captured_at)`, `creator_dna_snapshots(creator_id,computed_at)`, `llm_cache_v2(cache_kind,entity_id)`
- TTL: `oauth_states.created_at_ts` (600s)

## Required environment variables

```
MONGO_URL, DB_NAME              — Mongo connection
DATA_MODE=demo|production       — Data source selection
EMERGENT_LLM_KEY                — LLM (Claude via emergentintegrations)
APP_ENCRYPTION_KEY              — Fernet key for platform credentials (production)
CORS_ORIGINS                    — Comma-separated whitelist (no '*' in production)
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_URI  — YouTube OAuth
FRONTEND_URL                    — Post-login redirect target
SESSION_SECRET, SESSION_MAX_AGE — Session config
SLACK_WEBHOOK_URL               — Optional handoff channel
```

## Migration procedure

Legacy `users` documents from earlier iterations stored OAuth tokens inline. Migration:

1. Copy each user's `access_token` / `refresh_token` into `platform_credentials` via `PlatformRepo` + `CredentialRepo` (encrypt with `core.encryption.encrypt`).
2. Create `Workspace` + `Creator` records for each legacy user (idempotent — repos are upserts).
3. Copy any embedded `youtube_channel` fields into `connected_platforms`.
4. Optionally unset the inline fields on legacy users after verifying migration.

Legacy fields on `users` are no longer read by any code path but are not automatically deleted.

## Automated tests

`/app/backend/tests/test_phase1_foundation.py` — 16 tests covering:
- Identity resolution (demo, production, expired session)
- Workspace ownership isolation
- Creator uniqueness per user
- Provider workspace isolation
- Demo vs production isolation
- Intent CRUD + ownership isolation
- YouTube sync idempotency + missing-connection failure
- LLM cache version invalidation
- Encryption roundtrip
- Rate limiter
- Caller-cannot-override-identity via shortlist

Run: `cd /app/backend && python -m pytest tests/test_phase1_foundation.py -v`.

## Frontend states

`useBootstrap()` (from `lib/bootstrap.js`) provides one canonical read of:
- `loading | is_authenticated | is_demo | data_mode | user | creator | workspace | youtube_connected | dna_status`

DNADashboard handles:
- Demo → seeded Alex
- Authenticated + no YouTube → connect-state screen
- Authenticated + connected + `dna_status = not_computed` → sync CTA
- Ready → real DNA

`DemoBadge` renders a subtle "Demo data" pill in demo mode only.

## Remaining risks

- **Rate limiter is per-process** — will need Redis for multi-instance deployment.
- **DNA card image is still seeded-only** — real per-user rendering deferred.
- **Real DNA computation** is not yet implemented; production users see `not_computed` until Phase 2.
- **Existing `llm_cache` collection** (v1) is unused after v2 was introduced; safe to drop after verification.
- **Migration script** for legacy users is documented but not automated — no live users yet.

## Next phase

Phase 2 (DNA-01) — Real Creator Intelligence Pipeline. Await approval before starting.
