"""M5 router composition.

The legacy M5 endpoints are preserved in api.m5_legacy while the new workflow
architecture is mounted alongside them under the same /api/v1 namespace.
"""
from api.m5_legacy import build_m5_router as build_legacy_m5_router
from api.workflow import build_workflow_router


def build_m5_router(db):
    router = build_legacy_m5_router(db)
    router.include_router(build_workflow_router(db))
    return router
