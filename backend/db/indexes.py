"""Database index setup. Idempotent — call once at startup."""
from core.logging import get_logger

log = get_logger("db.indexes")


async def ensure_indexes(db):
    # Users
    await db.users.create_index("id", unique=True)
    await db.users.create_index("google_sub", unique=True, sparse=True)
    await db.users.create_index("email")

    # Sessions
    await db.sessions.create_index("sid", unique=True)
    await db.sessions.create_index("user_id")
    await db.sessions.create_index("expires_at")

    # Workspaces
    await db.workspaces.create_index("id", unique=True)
    await db.workspaces.create_index("owner_user_id")
    await db.workspaces.create_index("slug", unique=True)

    # Workspace members
    await db.workspace_members.create_index([("workspace_id", 1), ("user_id", 1)], unique=True)

    # Creators
    await db.creators.create_index("id", unique=True)
    await db.creators.create_index("user_id", unique=True)
    await db.creators.create_index("workspace_id")

    # Connected platforms
    await db.connected_platforms.create_index("id", unique=True)
    await db.connected_platforms.create_index([("creator_id", 1), ("platform", 1)])
    await db.connected_platforms.create_index("external_channel_id", sparse=True)

    # Platform credentials
    await db.platform_credentials.create_index("connected_platform_id", unique=True)

    # YouTube snapshots
    await db.youtube_channel_snapshots.create_index([("creator_id", 1), ("captured_at", -1)])
    await db.creator_videos.create_index([("creator_id", 1), ("external_video_id", 1)], unique=True)
    await db.video_metric_snapshots.create_index([("creator_video_id", 1), ("captured_at", -1)])

    # Intent + DNA
    await db.creator_intent.create_index("creator_id", unique=True)
    await db.creator_dna_snapshots.create_index([("creator_id", 1), ("computed_at", -1)])

    # LLM cache v2
    await db.llm_cache_v2.create_index("key_hash", unique=True)
    await db.llm_cache_v2.create_index([("cache_kind", 1), ("entity_id", 1)])
    await db.llm_cache_v2.create_index("expires_at", sparse=True)

    # OAuth states (short-lived) — TTL 10 minutes
    await db.oauth_states.create_index("created_at_ts", expireAfterSeconds=600)

    log.info("indexes_ensured")
