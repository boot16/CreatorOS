"""Focused M5.1 direction-development tests without Mongo or external LLM calls."""
from models.domain import Project
from models.m5 import CreativeDirectionV2, DirectionReadiness, DirectionReadinessCriterion
from services.direction_development import DirectionDraftOutput, _build_direction
from api.m5 import build_m5_router


def _project():
    return Project(
        id="project-1",
        creator_id="creator-1",
        workspace_id="workspace-1",
        title="AI leverage",
        content_type="instagram_reel",
        platform="instagram",
    )


def _direction():
    return CreativeDirectionV2(
        id="direction-1",
        project_id="project-1",
        creator_id="creator-1",
        batch_id="batch-1",
        source_understanding_version=2,
        title="Contrarian argument",
        premise="AI changes what one person can attempt.",
        angle="Capability, not time saving",
        audience_promise="Reconsider the scale of work you can take on",
        creative_treatment="Contrast the old team boundary with the new solo boundary",
        narrative_shape="comparison",
        format_fit="Works as a 45 second reel",
        why_this_direction="Makes the thesis concrete",
        revision=2,
    )


def test_refined_direction_preserves_lineage_and_advances_revision():
    output = DirectionDraftOutput(
        title="Visual capability gap",
        premise="Show the old and new capability boundary visually.",
        angle="Make the capability expansion visible",
        audience_promise="See how the feasible scope of solo work changed",
        creative_treatment="Use a visual before/after split",
        narrative_shape="visual comparison",
        emotional_movement="skepticism to possibility",
        format_fit="Designed for a short reel",
        why_this_direction="The visual mechanism carries the argument",
        risks=["Needs a concrete example"],
        unresolved_questions=["Which example is strongest?"],
    )

    item = _build_direction(_project(), _direction(), output, parents=["direction-1"])

    assert item.revision == 3
    assert item.parent_direction_ids == ["direction-1"]
    assert item.status.value == "proposed"
    assert item.source_understanding_version == 2


def test_readiness_has_no_numeric_quality_score():
    item = DirectionReadiness(
        project_id="project-1",
        creator_id="creator-1",
        direction_id="direction-1",
        direction_revision=2,
        overall_status="needs_work",
        criteria=[
            DirectionReadinessCriterion(
                key="evidence",
                status="needs_resolution",
                note="The factual example still needs support.",
                evidence_needed=True,
            )
        ],
    )

    dumped = item.model_dump()
    assert "score" not in dumped
    assert dumped["criteria"][0]["evidence_needed"] is True


def test_m5_router_exposes_direction_development_routes():
    router = build_m5_router(object())
    paths = {route.path for route in router.routes}

    assert "/v1/projects/{project_id}/creative-directions/{direction_id}/refine" in paths
    assert "/v1/projects/{project_id}/creative-directions/{direction_id}/combine" in paths
    assert "/v1/projects/{project_id}/direction-readiness" in paths
    assert "/v1/projects/{project_id}/direction-readiness/assess" in paths
