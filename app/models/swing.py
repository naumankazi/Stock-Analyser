"""Structured single-stock swing assessment, separate from screener AI output."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SwingModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class SwingSetup(SwingModel):
    name: Literal["BREAKOUT", "RETEST", "FLAG", "EMA_PULLBACK"]
    status: Literal["VALID", "WAITING", "ABSENT", "UNAVAILABLE"]
    quality_score: float | None = Field(..., ge=0, le=10)
    evidence: list[str]
    # Include the pivot, base/flag/retest range, EMA support, confirmation and invalidation.
    levels: dict[str, float | None]


class SwingTarget(SwingModel):
    label: Literal["Target 1", "Target 2", "Extended target"]
    price: float | None = Field(..., gt=0)
    basis: str
    reward_pct: float | None = None
    reward_risk: float | None = None


class SwingAnswers(SwingModel):
    entry_today: str
    biggest_risk: str
    better_setup: str
    strength_or_chasing: str
    one_event_to_wait_for: str
    bullish_thesis_invalidation: str


class SwingSections(SwingModel):
    current_market_data: list[str]
    stage_analysis: list[str]
    extension_risk: list[str]
    current_setup: list[str]
    support_resistance: list[str]
    technical_stop: list[str]
    risk_reward: list[str]
    trade_management: list[str]
    position_sizing: list[str]
    relative_strength: list[str]
    volume_analysis: list[str]
    fundamental_sanity: list[str]
    reentry_plan: list[str]
    final_decision: list[str]


class SwingAnalysis(SwingModel):
    decision: Literal[
        "ENTER NOW", "ENTER ON CONFIRMATION", "WAIT FOR RETEST", "WAIT FOR PULLBACK",
        "WAIT FOR CONSOLIDATION", "TOO EXTENDED — DO NOT CHASE",
        "TREND STRUCTURE WEAK — AVOID", "RISK/REWARD UNATTRACTIVE — AVOID",
    ]
    stage: Literal["Stage 1", "Stage 2", "Stage 3", "Stage 4", "UNAVAILABLE"]
    stage2_score: float | None = Field(..., ge=0, le=10)
    current_setup: str
    entry_now: bool
    entry_zone_low: float | None = Field(..., gt=0)
    entry_zone_high: float | None = Field(..., gt=0)
    proposed_entry: float | None = Field(..., gt=0)
    confirmation_trigger: str
    technical_stop: float | None = Field(..., gt=0)
    stop_anchor: float | None = Field(..., gt=0)
    stop_reason: str
    targets: list[SwingTarget] = Field(..., min_length=3, max_length=3)
    partial_profit_plan: str
    trailing_method: str
    full_exit_trigger: str
    major_support: float | None = Field(..., gt=0)
    major_resistance: float | None = Field(..., gt=0)
    extension_risk: Literal["NOT EXTENDED", "SLIGHTLY EXTENDED", "EXTENDED", "SEVERELY EXTENDED / DO NOT CHASE", "UNAVAILABLE"]
    relative_strength: Literal["STRONG LEADER", "OUTPERFORMER", "MARKET-LIKE", "UNDERPERFORMER", "UNAVAILABLE"]
    volume_quality: str
    setup_score: float | None = Field(..., ge=0, le=10)
    setups: list[SwingSetup] = Field(..., min_length=4, max_length=4)
    sections: SwingSections
    answers: SwingAnswers
    risk_per_share: float | None = None
    stop_distance_pct: float | None = None
    stop_classification: str = "Unavailable"
    position_sizing: list[dict] = Field(default_factory=list)
    validation_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_members(self):
        if {s.name for s in self.setups} != {"BREAKOUT", "RETEST", "FLAG", "EMA_PULLBACK"}:
            raise ValueError("All four setup assessments are required")
        if [t.label for t in self.targets] != ["Target 1", "Target 2", "Extended target"]:
            raise ValueError("Three ordered target areas are required")
        return self
