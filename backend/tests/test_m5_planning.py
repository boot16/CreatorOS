"""M5.1 planning tests without external LLM calls."""
from models.m5 import ReelCreativePlan, ReelPlanBeat
from services.planning import requirements_for
from api.m5 import build_m5_router


def test_reel_requirements_are_deterministic_and_production_oriented():
    items = requirements_for("instagram_reel")
    keys = {item.key for item in items}

    assert {"beats", "spoken_audio", "visual", "shot_framing", "assets", "evidence"}.issubset(keys)
    assert len(items) >= 10
    assert requirements_for("youtube_video") == []


def test_reel_plan_is_structured_not_plain_outline():
    plan = ReelCreativePlan(
        project_id="p1",
        creator_id="c1",
        direction_id="d1",
        duration_seconds=40,
        objective="Reframe AI leverage",
        audience_takeaway="One person can attempt larger projects",
        hook_strategy="Challenge the time-saving frame",
        narrative_arc="misconception to capability shift",
        tone="direct",
        beats=[
            ReelPlanBeat(
                start_second=0,
                end_second=4,
                purpose="pattern interrupt",
                spoken_audio="AI saving you time is the least interesting part.",
                visual="Creator on camera, hard cut from productivity timer",
                shot_framing="tight medium shot",
            ),
            ReelPlanBeat(
                start_second=4,
                end_second=12,
                purpose="establish thesis",
                spoken_audio="The bigger change is what one person can now attempt.",
                visual="Split screen: solo creator vs old team workflow",
                shot_framing="split-screen composition",
            ),
        ],
    )

    dumped = plan.model_dump()
    assert dumped["beats"][0]["shot_framing"] == "tight medium shot"
    assert "outline" not in dumped


def test_m5_router_exposes_planning_routes():
    paths = {route.path for route in build_m5_router(object()).routes}
    assert "/v1/projects/{project_id}/planning-requirements" in paths
    assert "/v1/projects/{project_id}/creative-plan" in paths
    assert "/v1/projects/{project_id}/creative-plan/generate" in paths
    assert "/v1/projects/{project_id}/creative-plan/{plan_id}/approve" in paths
