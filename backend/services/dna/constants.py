"""Constants for DNA-01 pipeline. Bumping these versions invalidates cached analyses/snapshots."""

DNA_PIPELINE_VERSION = "1.0"
VIDEO_ANALYSIS_PROMPT_VERSION = "1.0"
VIDEO_ANALYSIS_MODEL = ("anthropic", "claude-sonnet-4-6")

# Data-sufficiency thresholds
THRESHOLD_INSUFFICIENT = 5   # < 5 usable videos → insufficient_data
THRESHOLD_PROVISIONAL = 10   # 5-9 → provisional, >=10 → computed

# Analysis windows (days)
RECENT_WINDOW_DAYS = 90

# Winning-combination requirements
MIN_COMBO_SAMPLE = 3

# Evolution thresholds
EMERGING_MIN_RECENT_SHARE = 0.10   # ≥10% share of recent
EMERGING_MIN_LIFT = 1.5              # recent share ≥ 1.5× historical share
CORE_MIN_SHARE = 0.15                # ≥15% of ALL_AVAILABLE

# Canonical enums (frozensets so validation is cheap)
CANONICAL_FORMATS = frozenset({
    "tutorial", "experiment", "comparison", "commentary", "review",
    "explainer", "case_study", "interview", "challenge", "list",
    "news", "story", "vlog", "reaction", "other",
})
CANONICAL_HOOK_TYPES = frozenset({
    "question", "challenge", "bold_claim", "curiosity_gap", "problem",
    "result_first", "story", "contrarian", "demonstration", "other",
})
CANONICAL_TONES = frozenset({
    "energetic", "calm", "analytical", "casual", "authoritative",
    "conversational", "instructive", "personal", "other",
})
CANONICAL_STRUCTURES = frozenset({
    "linear", "problem_solution", "before_after", "list", "compare_contrast",
    "narrative", "how_to", "discovery", "other",
})
CANONICAL_STYLES = frozenset({
    "first_person", "educational", "demonstration", "narrative",
    "analysis", "conversation", "documentary", "other",
})
