"""Focused M5.1 tests that do not require Mongo or an external LLM."""
from models.domain import Project
from services.idea_understanding import IdeaUnderstandingOutput, build_understanding
from api.m5 import build_m5_router


def _project():
    return Project(
        id="project-1",
        creator_id="creator-1",
        workspace_id="workspace-1",
        title="AI leverage",
        content_type="instagram_reel",
        platform="instagram",
        objective="Reframe how creators think about AI",
    )


def test_build_understanding_marks_ai_fields_as_inferred():
    result = IdeaUnderstandingOutput(
        subject="AI leverage",
        creator_perspective="Saving time is the shallow framing; AI expands what one person can attempt.",
        core_claim="AI changes feasible scope for individuals.",
        intent="Reframe AI productivity",
        target_audience="Creators and solo founders",
        desired_effect="Make the viewer reconsider the size of projects they can attempt",
        assumptions=["Viewer already knows common AI productivity claims"],
        open_questions=["What concrete example best proves the shift?"],
        material_unknowns=["Whether the creator wants a personal story or an argument-led treatment"],
        confidence={
            "subject": 0.97,
            "creator_perspective": 0.92,
            "core_claim": 1.4,
            "intent": 0.8,
            "target_audience": -0.3,
            "desired_effect": 0.72,
        },
    )

    item = build_understanding(_project(), "  AI is bigger than time saving.  ", result)

    assert item.raw_idea == "AI is bigger than time saving."
    assert item.creator_perspective.origin.value == "inferred"
    assert item.creator_perspective.value.startswith("Saving time")
    assert item.core_claim.confidence == 1.0
    assert item.target_audience.confidence == 0.0
    assert item.material_unknowns == [
        "Whether the creator wants a personal story or an argument-led treatment"
    ]


def test_build_understanding_deduplicates_prompt_lists():
    result = IdeaUnderstandingOutput(
        assumptions=["Needs evidence", "needs evidence", "", "Use a real example"],
        open_questions=["Which example?", "Which example?"],
        material_unknowns=[],
    )

    item = build_understanding(_project(), "A sufficiently specific raw idea", result)

    assert item.assumptions == ["Needs evidence", "Use a real example"]
    assert item.open_questions == ["Which example?"]


def test_m5_router_exposes_expected_workflow_routes():
    router = build_m5_router(object())
    route_paths = {route.path for route in router.routes}

    assert "/v1/projects/{project_id}/idea-understanding" in route_paths
    assert "/v1/projects/{project_id}/idea-understanding/generate" in route_paths
    assert "/v1/projects/{project_id}/creative-directions" in route_paths
    assert "/v1/projects/{project_id}/creative-directions/generate" in route_paths
    assert "/v1/projects/{project_id}/creative-directions/{direction_id}/select" in route_paths
    assert "/v1/projects/{project_id}/creative-directions/{direction_id}/reject" in route_paths
