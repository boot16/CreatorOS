"""Database index setup. Idempotent — call once at startup."""
from core.logging import get_logger

log = get_logger("db.indexes")


async def ensure_indexes(db):
    await db.users.create_index("id", unique=True)
    await db.users.create_index("google_sub", unique=True, sparse=True)
    await db.users.create_index("email")
    await db.sessions.create_index("sid", unique=True)
    await db.sessions.create_index("user_id")
    await db.sessions.create_index("expires_at")
    await db.workspaces.create_index("id", unique=True)
    await db.workspaces.create_index("owner_user_id")
    await db.workspaces.create_index("slug", unique=True)
    await db.workspace_members.create_index([("workspace_id", 1), ("user_id", 1)], unique=True)
    await db.creators.create_index("id", unique=True)
    await db.creators.create_index("user_id", unique=True)
    await db.creators.create_index("workspace_id")
    await db.connected_platforms.create_index("id", unique=True)
    await db.connected_platforms.create_index([("creator_id", 1), ("platform", 1)])
    await db.connected_platforms.create_index("external_channel_id", sparse=True)
    await db.platform_credentials.create_index("connected_platform_id", unique=True)
    await db.youtube_channel_snapshots.create_index([("creator_id", 1), ("captured_at", -1)])
    await db.creator_videos.create_index([("creator_id", 1), ("external_video_id", 1)], unique=True)
    await db.video_metric_snapshots.create_index([("creator_video_id", 1), ("captured_at", -1)])
    await db.creator_intent.create_index("creator_id", unique=True)
    await db.creator_dna_snapshots.create_index([("creator_id", 1), ("computed_at", -1)])
    await db.llm_cache_v2.create_index("key_hash", unique=True)
    await db.llm_cache_v2.create_index([("cache_kind", 1), ("entity_id", 1)])
    await db.llm_cache_v2.create_index("expires_at", sparse=True)
    await db.assistant_sessions.create_index("session_id", unique=True)
    await db.assistant_sessions.create_index("owner_key")
    await db.assistant_history.create_index([("session_id", 1), ("created_at", 1)])
    await db.assistant_history.create_index("owner_key")
    await db.video_content_analysis.create_index(
        [("creator_video_id", 1), ("source_content_hash", 1), ("prompt_version", 1), ("pipeline_version", 1), ("model", 1)],
        unique=True,
    )
    await db.video_content_analysis.create_index("creator_id")
    await db.oauth_states.create_index("created_at_ts", expireAfterSeconds=600)
    await db.projects.create_index("id", unique=True)
    await db.projects.create_index([("creator_id", 1), ("updated_at", -1)])
    await db.projects.create_index([("creator_id", 1), ("status", 1)])
    await db.creative_objects.create_index("id", unique=True)
    await db.creative_objects.create_index([("project_id", 1), ("created_at", 1)])
    await db.activity_events.create_index("id", unique=True)
    await db.activity_events.create_index([("project_id", 1), ("created_at", -1)])
    await db.project_sources.create_index("id", unique=True)
    await db.project_sources.create_index([("project_id", 1), ("created_at", 1)])
    await db.project_chats.create_index([("project_id", 1), ("created_at", 1)])
    await db.activity_events.create_index([("creator_id", 1), ("created_at", 1)])
    await db.creator_learned_prefs.create_index("creator_id", unique=True)

    # M5 living project foundation: one canonical context object per creator-owned project.
    await db.project_foundations.create_index("id", unique=True)
    await db.project_foundations.create_index([("project_id", 1), ("creator_id", 1)], unique=True)
    await db.project_foundations.create_index([("creator_id", 1), ("updated_at", -1)])

    # M5 learning foundation. Raw signals remain immutable evidence; preferences are derived state.
    await db.learning_signals.create_index("id", unique=True)
    await db.learning_signals.create_index([("creator_id", 1), ("created_at", -1)])
    await db.learning_signals.create_index([("project_id", 1), ("created_at", -1)], sparse=True)
    await db.learning_signals.create_index([("creator_id", 1), ("signal_type", 1)])
    await db.creator_preference_evidence.create_index("id", unique=True)
    await db.creator_preference_evidence.create_index([("creator_id", 1), ("key", 1), ("scope", 1)], unique=True)
    await db.creator_preference_evidence.create_index([("creator_id", 1), ("confidence", -1)])

    # M5.1 idea understanding (legacy compatibility while Foundation replaces the separate Idea/Brief UX).
    await db.idea_understandings.create_index("id", unique=True)
    await db.idea_understandings.create_index([("project_id", 1), ("creator_id", 1)], unique=True)
    await db.idea_understandings.create_index([("creator_id", 1), ("updated_at", -1)])

    await db.creative_directions.create_index("id", unique=True)
    await db.creative_directions.create_index([("project_id", 1), ("creator_id", 1), ("created_at", 1)])
    await db.creative_directions.create_index([("project_id", 1), ("batch_id", 1)])
    await db.creative_directions.create_index([("project_id", 1), ("status", 1)])
    await db.direction_readiness.create_index("id", unique=True)
    await db.direction_readiness.create_index(
        [("project_id", 1), ("creator_id", 1), ("direction_id", 1), ("direction_revision", 1)], unique=True,
    )
    await db.direction_readiness.create_index([("project_id", 1), ("updated_at", -1)])
    await db.creative_plans.create_index("id", unique=True)
    await db.creative_plans.create_index(
        [("project_id", 1), ("creator_id", 1), ("direction_id", 1), ("direction_revision", 1), ("version", -1)], unique=True,
    )
    await db.creative_plans.create_index([("project_id", 1), ("updated_at", -1)])

    log.info("indexes_ensured")
