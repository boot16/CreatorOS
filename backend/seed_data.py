"""Seed data for CreatorOS demo. All fictional creators & channels."""

ALEX = {
    "id": "alex-morgan",
    "name": "Alex Morgan",
    "handle": "@alexmorganai",
    "niche": "AI + Entrepreneurship",
    "subscribers": 124000,
    "avatar_gradient": ["#8A2BE2", "#4C1D95"],
    "initials": "AM",
    "bio": "Building the future with AI. Experiments, tools, and startup lessons — twice a week.",
    "pillars": [
        {"name": "AI Tools", "pct": 32},
        {"name": "Business Experiments", "pct": 29},
        {"name": "Startup Challenges", "pct": 21},
        {"name": "Productivity", "pct": 11},
        {"name": "News", "pct": 7},
    ],
    "formats": [
        {"name": "Experiments", "multiplier": 2.4, "label": "Best"},
        {"name": "Tool Reviews", "multiplier": 1.6, "label": "Strong"},
        {"name": "Tutorials", "multiplier": 1.2, "label": "Solid"},
        {"name": "Interviews", "multiplier": 1.0, "label": "Baseline"},
        {"name": "Generic News", "multiplier": 0.7, "label": "Weak"},
    ],
    "style": {
        "tone": "Direct, curious, first-person",
        "pace": "Fast cuts, sub-8s scenes",
        "hook_style": "Question or bold claim in first 3s",
        "visual": "Screen-heavy with reaction cam",
    },
    "audience_interests": [
        {"name": "AI Agents", "affinity": 94},
        {"name": "Solo Founders", "affinity": 88},
        {"name": "No-code Tools", "affinity": 81},
        {"name": "Newsletter Growth", "affinity": 76},
        {"name": "Personal Branding", "affinity": 68},
    ],
}

SARAH = {
    "id": "sarah-chen",
    "name": "Sarah Chen",
    "handle": "@sarahbuildsai",
    "niche": "Technical AI & Engineering",
    "subscribers": 80000,
    "avatar_gradient": ["#F59E0B", "#B45309"],
    "initials": "SC",
    "bio": "AI engineer breaking down agents, RAG, and eval systems for builders.",
    "pillars": [
        {"name": "AI Engineering", "pct": 38},
        {"name": "Agents & RAG", "pct": 27},
        {"name": "Model Deep Dives", "pct": 19},
        {"name": "Career", "pct": 10},
        {"name": "Live Builds", "pct": 6},
    ],
    "formats": [
        {"name": "Live Builds", "multiplier": 2.1, "label": "Best"},
        {"name": "Deep Dives", "multiplier": 1.7, "label": "Strong"},
        {"name": "Tutorials", "multiplier": 1.3, "label": "Solid"},
    ],
    "style": {
        "tone": "Technical, calm, precise",
        "pace": "Measured, whiteboard-driven",
        "hook_style": "Concrete problem statement",
        "visual": "Terminal + diagrams",
    },
    "audience_interests": [
        {"name": "AI Agents", "affinity": 96},
        {"name": "LLM Evals", "affinity": 89},
        {"name": "AI Employees", "affinity": 74},
    ],
}

COMPATIBILITY = {
    "creator_a": "alex-morgan",
    "creator_b": "sarah-chen",
    "overall": 92,
    "breakdown": {
        "AudienceCompat": 94,
        "TopicCompat": 91,
        "ContentComplementarity": 96,
        "CreatorSizeCompat": 82,
        "FormatCompat": 90,
    },
    "why_bullets": [
        "94% audience overlap in AI Agents interest — but Sarah goes deeper technical while Alex stays business-facing.",
        "Sarah's 'how it works' complements Alex's 'why it matters' — different angles on the same trends.",
        "Sarah's audience is 2.1× more likely to convert on founder-tool recommendations vs. baseline.",
        "Channel sizes within 2× range — cross-promo is balanced, not lopsided.",
    ],
    "collab_ideas": [
        "48-hour AI agent build-off (Sarah engineers, Alex ships to real users)",
        "Two-part series: 'The AI Employee' — Alex's business case, Sarah's technical blueprint",
        "Live stream: React to and rebuild the same viral AI app",
    ],
}

TRENDS = [
    {"id": "ai-agents", "name": "AI Agents", "category": "AI", "momentum": 183, "stage": "Accelerating",
     "volume": 92, "saturation": 41, "sparkline": [12, 18, 25, 38, 55, 74, 92]},
    {"id": "ai-employees", "name": "AI Employees", "category": "AI", "momentum": 267, "stage": "Emerging",
     "volume": 61, "saturation": 18, "sparkline": [4, 7, 11, 19, 32, 48, 61]},
    {"id": "vibe-coding", "name": "Vibe Coding", "category": "Tech", "momentum": 148, "stage": "Accelerating",
     "volume": 78, "saturation": 34, "sparkline": [15, 22, 30, 45, 58, 68, 78]},
    {"id": "solo-saas", "name": "Solo SaaS", "category": "Business", "momentum": 62, "stage": "Mainstream",
     "volume": 84, "saturation": 71, "sparkline": [72, 74, 76, 79, 81, 83, 84]},
    {"id": "ai-newsletter", "name": "AI-First Newsletters", "category": "Business", "momentum": 41, "stage": "Mainstream",
     "volume": 66, "saturation": 68, "sparkline": [55, 58, 60, 62, 64, 65, 66]},
    {"id": "focus-stack", "name": "Deep Work Stacks", "category": "Productivity", "momentum": 24, "stage": "Mainstream",
     "volume": 58, "saturation": 62, "sparkline": [50, 52, 53, 55, 56, 57, 58]},
    {"id": "gpt-wrappers", "name": "GPT Wrapper Fatigue", "category": "AI", "momentum": -18, "stage": "Saturated",
     "volume": 44, "saturation": 88, "sparkline": [78, 72, 66, 58, 52, 47, 44]},
    {"id": "ai-hardware", "name": "Personal AI Hardware", "category": "Tech", "momentum": 112, "stage": "Emerging",
     "volume": 47, "saturation": 22, "sparkline": [8, 12, 18, 26, 34, 41, 47]},
]

# Opportunity Score = 0.25*TrendFit + 0.25*CreatorFit + 0.20*HistoricalFormatFit + 0.10*AudienceFit + 0.10*Freshness + 0.10*(100-Saturation)
OPPORTUNITIES = [
    {
        "id": "opp-1", "creator_id": "alex-morgan", "trend_id": "ai-employees",
        "title": "I Replaced My First Employee With an AI Agent — 30 Day Log",
        "format": "Experiment",
        "sub_scores": {"TrendFit": 96, "CreatorFit": 94, "HistoricalFormatFit": 92,
                        "AudienceFit": 88, "Freshness": 90, "Saturation": 18},
        "why_bullets_seed": "AI Employees trend is Emerging (+267%). Alex's experiment format is 2.4x baseline. His audience over-indexes on solo founder tools. Saturation is low (18) so first-mover advantage still exists.",
    },
    {
        "id": "opp-2", "creator_id": "alex-morgan", "trend_id": "ai-agents",
        "title": "The 5-Agent Stack That Runs My Whole Business",
        "format": "Tool Review + Experiment",
        "sub_scores": {"TrendFit": 92, "CreatorFit": 88, "HistoricalFormatFit": 82,
                        "AudienceFit": 94, "Freshness": 72, "Saturation": 41},
        "why_bullets_seed": "AI Agents is peak-Accelerating (+183%). Audience affinity is 94. Format blends best two performers. Saturation moderate — differentiation via personal stack angle.",
    },
    {
        "id": "opp-3", "creator_id": "alex-morgan", "trend_id": "vibe-coding",
        "title": "I Built and Shipped an App in 4 Hours (No Code Written)",
        "format": "Experiment",
        "sub_scores": {"TrendFit": 84, "CreatorFit": 82, "HistoricalFormatFit": 92,
                        "AudienceFit": 78, "Freshness": 80, "Saturation": 34},
        "why_bullets_seed": "Vibe Coding is Accelerating. Timed experiment format is Alex's strongest. Audience skew toward no-code tools (81 affinity).",
    },
    {
        "id": "opp-4", "creator_id": "alex-morgan", "trend_id": "ai-hardware",
        "title": "I Wore an AI Pin for a Week — Here's What Actually Happened",
        "format": "Experiment",
        "sub_scores": {"TrendFit": 78, "CreatorFit": 74, "HistoricalFormatFit": 92,
                        "AudienceFit": 62, "Freshness": 94, "Saturation": 22},
        "why_bullets_seed": "Personal AI Hardware is Emerging with low saturation. High freshness, format fit strong, but audience affinity is softer — angle it toward productivity ROI.",
    },
    {
        "id": "opp-5", "creator_id": "alex-morgan", "trend_id": "solo-saas",
        "title": "Every Solo SaaS Playbook Everyone Copies — Ranked",
        "format": "Analysis",
        "sub_scores": {"TrendFit": 62, "CreatorFit": 70, "HistoricalFormatFit": 66,
                        "AudienceFit": 72, "Freshness": 40, "Saturation": 71},
        "why_bullets_seed": "Solo SaaS is Mainstream — saturation is high (71). Format is not Alex's strongest. Rank/tier content can still cut through with a strong opinion angle.",
    },
]

WEIGHTS_OPP = {"TrendFit": 0.25, "CreatorFit": 0.25, "HistoricalFormatFit": 0.20,
                "AudienceFit": 0.10, "Freshness": 0.10, "Saturation": 0.10}

WEIGHTS_COMPAT = {"AudienceCompat": 0.25, "TopicCompat": 0.25, "ContentComplementarity": 0.25,
                   "CreatorSizeCompat": 0.125, "FormatCompat": 0.125}


def compute_opportunity_score(sub: dict) -> int:
    """Deterministic formula from spec — never call LLM for this."""
    return round(
        WEIGHTS_OPP["TrendFit"] * sub["TrendFit"]
        + WEIGHTS_OPP["CreatorFit"] * sub["CreatorFit"]
        + WEIGHTS_OPP["HistoricalFormatFit"] * sub["HistoricalFormatFit"]
        + WEIGHTS_OPP["AudienceFit"] * sub["AudienceFit"]
        + WEIGHTS_OPP["Freshness"] * sub["Freshness"]
        + WEIGHTS_OPP["Saturation"] * (100 - sub["Saturation"])
    )


def compute_compatibility_score(sub: dict) -> int:
    return round(
        WEIGHTS_COMPAT["AudienceCompat"] * sub["AudienceCompat"]
        + WEIGHTS_COMPAT["TopicCompat"] * sub["TopicCompat"]
        + WEIGHTS_COMPAT["ContentComplementarity"] * sub["ContentComplementarity"]
        + WEIGHTS_COMPAT["CreatorSizeCompat"] * sub["CreatorSizeCompat"]
        + WEIGHTS_COMPAT["FormatCompat"] * sub["FormatCompat"]
    )


# Historical videos for Alex — thumbnails as gradient seeds
HISTORICAL_VIDEOS = [
    {"title": "I Let GPT Run My Business For 24 Hours", "format": "Experiment", "views": 412000, "grad": ["#8A2BE2","#4C1D95"]},
    {"title": "The Only 3 AI Tools You Actually Need in 2026", "format": "Tool Review", "views": 287000, "grad": ["#F59E0B","#B45309"]},
    {"title": "I Cloned Myself With AI — Investors Couldn't Tell", "format": "Experiment", "views": 634000, "grad": ["#10B981","#065F46"]},
    {"title": "Why I Deleted All My Productivity Apps", "format": "Analysis", "views": 156000, "grad": ["#EF4444","#7F1D1D"]},
    {"title": "$0 to $10K MRR in 30 Days — The Full Playbook", "format": "Experiment", "views": 892000, "grad": ["#3B82F6","#1E3A8A"]},
    {"title": "AI Agents Explained (Without the Hype)", "format": "Tutorial", "views": 341000, "grad": ["#8A2BE2","#4C1D95"]},
    {"title": "I Fired My Assistant — An AI Took Over", "format": "Experiment", "views": 521000, "grad": ["#EC4899","#831843"]},
    {"title": "The Newsletter Stack That Prints Money", "format": "Tool Review", "views": 198000, "grad": ["#F59E0B","#B45309"]},
    {"title": "One Prompt That 10x'd My Output", "format": "Tutorial", "views": 267000, "grad": ["#8A2BE2","#4C1D95"]},
    {"title": "I Talked to 100 Founders — Here's What's Broken", "format": "Interview", "views": 143000, "grad": ["#06B6D4","#155E75"]},
    {"title": "Why 'Vibe Coding' Actually Works", "format": "Analysis", "views": 224000, "grad": ["#10B981","#065F46"]},
    {"title": "The AI Job Market is a Lie — Here's the Truth", "format": "Analysis", "views": 176000, "grad": ["#EF4444","#7F1D1D"]},
    {"title": "I Built 3 SaaS in a Week Using AI", "format": "Experiment", "views": 458000, "grad": ["#3B82F6","#1E3A8A"]},
    {"title": "Claude vs GPT — I Ran the Real Test", "format": "Tool Review", "views": 312000, "grad": ["#8A2BE2","#4C1D95"]},
    {"title": "Solo Founder Morning Routine (Real, Not Aesthetic)", "format": "Analysis", "views": 122000, "grad": ["#F59E0B","#B45309"]},
    {"title": "This AI Agent Books My Meetings Better Than Me", "format": "Tool Review", "views": 289000, "grad": ["#EC4899","#831843"]},
    {"title": "I Automated Customer Support in 1 Hour", "format": "Experiment", "views": 384000, "grad": ["#10B981","#065F46"]},
    {"title": "The Truth About AI-First Startups", "format": "Interview", "views": 167000, "grad": ["#06B6D4","#155E75"]},
    {"title": "Why I Stopped Posting Generic AI News", "format": "News", "views": 84000, "grad": ["#6B7280","#374151"]},
    {"title": "My Actual Tech Stack (Nothing Fancy)", "format": "Tool Review", "views": 231000, "grad": ["#3B82F6","#1E3A8A"]},
]
