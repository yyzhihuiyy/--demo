"""Canonical public DTOs. Generate frontend types; do not manually duplicate them."""
from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[int, Field(strict=True, gt=0)]
Cents = Annotated[int, Field(strict=True, ge=0)]
Count = Annotated[int, Field(strict=True, ge=0)]
T = TypeVar("T")


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Envelope(BaseModel, Generic[T]):
    data: T


class Health(DTO):
    status: Literal["ok"]
    database: Literal["ok"]
    contract_version: str
    modules: dict[str, str]
    model_configured: bool


class User(DTO):
    id: Id
    username: str
    role: Literal["teacher", "student"]
    class_id: Id
    active: bool = True


class LoginRequest(DTO):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(DTO):
    token: str
    user: User


class TeamMember(DTO):
    user_id: Id
    position: Literal["host", "control", "service", "operations"]


class Team(DTO):
    id: Id
    class_id: Id
    name: str
    members: list[TeamMember] = Field(default_factory=list)


class ScoreWeights(DTO):
    process: float = Field(default=25, ge=0, le=100)
    business: float = Field(default=25, ge=0, le=100)
    service: float = Field(default=20, ge=0, le=100)
    compliance: float = Field(default=15, ge=0, le=100)
    review: float = Field(default=15, ge=0, le=100)

    @model_validator(mode="after")
    def validate_sum(self):
        if abs(sum(self.model_dump().values()) - 100) > 1e-6:
            raise ValueError("评分权重之和必须为 100")
        return self


class TaskWrite(DTO):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    target_audience: str = ""
    initial_budget_cents: Cents = 100000
    target_gmv_cents: Annotated[int, Field(strict=True, gt=0)] = 50000
    market_heat: float = Field(default=1, ge=0.1, le=3)
    difficulty: float = Field(default=1, ge=0.1, le=3)
    starts_at: datetime
    ends_at: datetime
    score_weights: ScoreWeights = Field(default_factory=ScoreWeights)
    team_ids: list[Id] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("时间必须包含时区")
        if self.ends_at <= self.starts_at:
            raise ValueError("截止时间必须晚于开始时间")
        return self


class Task(TaskWrite):
    id: Id
    class_id: Id
    teacher_id: Id
    status: Literal["draft", "published", "closed"]
    rules_version: str = "mvp-v1"


class Research(DTO):
    audience: str = ""
    competitor_notes: str = ""
    price_notes: str = ""
    selection_reason: str = ""


class Plan(DTO):
    theme: str = ""
    target_audience: str = ""


class ScriptSegment(DTO):
    id: str
    kind: Literal["opening", "product", "interaction", "closing"]
    product_id: Id | None = None
    text: str = ""


class Promotion(DTO):
    channel: Literal["simulated_feed"] = "simulated_feed"
    budget_cents: Cents = 0
    audience: str = ""


class Room(DTO):
    theme: str = "agriculture"
    title: str = ""
    announcement: str = ""


class Coupon(DTO):
    discount_cents: Cents = 100


class Preparation(DTO):
    research: Research = Field(default_factory=Research)
    plan: Plan = Field(default_factory=Plan)
    script: list[ScriptSegment] = Field(default_factory=list)
    promotion: Promotion = Field(default_factory=Promotion)
    room: Room = Field(default_factory=Room)
    coupon: Coupon = Field(default_factory=Coupon)


class PreparationWrite(Preparation):
    expected_version: Count


class Product(DTO):
    id: Id
    title: str
    category: str
    cost_cents: Cents
    reference_price_cents: Cents
    selling_points: str
    supplier: str
    image_or_placeholder: str = ""


class AssortmentItem(DTO):
    product_id: Id
    positioning: Literal["traffic", "profit", "image"]
    selling_points: str = ""
    sale_price_cents: Annotated[int, Field(strict=True, gt=0)]
    sort_order: Count = 0


class SessionProduct(AssortmentItem):
    id: Id
    session_id: Id
    title: str
    cost_cents: Cents
    purchased_qty: Count = 0
    stock_qty: Count = 0


class AssortmentWrite(DTO):
    items: list[AssortmentItem]


class PurchaseItem(DTO):
    session_product_id: Id
    qty: Annotated[int, Field(strict=True, gt=0)]


class PurchaseRequest(DTO):
    items: list[PurchaseItem] = Field(min_length=1)


SessionStatus = Literal["preparing", "live", "paused", "ended", "submitted", "graded"]


class TrainingSession(DTO):
    id: Id
    task_id: Id
    team_id: Id
    status: SessionStatus
    rule_snapshot: dict = Field(default_factory=dict)
    preparation_version: Count = 0
    initial_budget_cents: Cents
    started_at: datetime | None = None
    ended_at: datetime | None = None
    live_elapsed_seconds: Count = 0
    current_product_id: Id | None = None


class Metrics(DTO):
    gmv_cents: Cents = 0
    refund_cents: Cents = 0
    net_sales_cents: Cents = 0
    profit_cents: int = 0
    cash_balance_cents: int = 0
    promotion_spend_cents: Cents = 0
    order_count: Count = 0
    refunded_order_count: Count = 0
    online_count: Count = 0
    cumulative_entries: Count = 0
    product_clicks: Count = 0
    audience_question_count: Count = 0
    replied_question_count: Count = 0
    violation_count: Count = 0
    signed_order_count: Count = 0
    conversion_rate: float | None = None
    reply_rate: float | None = None


class SessionDetail(DTO):
    session: TrainingSession
    preparation: Preparation
    products: list[SessionProduct]
    metrics: Metrics
    capabilities: dict[str, bool]


class ChecklistItem(DTO):
    key: str
    passed: bool
    message: str
    target: str


class Checklist(DTO):
    items: list[ChecklistItem]
    can_start: bool


class ControlRequest(DTO):
    action: Literal["start", "pause", "resume", "end"]


class ActionRequest(DTO):
    type: Literal["select_product", "issue_coupon", "announcement", "speech", "reply", "execute_script"]
    payload: dict


class TrainingEvent(DTO):
    id: Id
    session_id: Id
    type: str
    actor_id: Id | None = None
    source: Literal["manual", "rule"]
    payload: dict
    created_at: datetime


class LiveState(DTO):
    status: SessionStatus
    current_product: SessionProduct | None = None
    metrics: Metrics
    latest_event_id: Count = 0


class Order(DTO):
    id: Id
    session_id: Id
    session_product_id: Id
    buyer_label: str
    qty: Annotated[int, Field(strict=True, gt=0)]
    unit_cost_cents: Cents
    unit_sale_cents: Cents
    discount_cents: Cents
    amount_cents: Cents
    status: Literal["pending_shipment", "shipped", "signed", "refunded"]
    created_at: datetime


class Refund(DTO):
    id: Id
    order_id: Id
    reason: str
    status: Literal["pending", "approved", "rejected"]
    handler_id: Id | None = None
    handling_note: str = ""
    amount_cents: Cents


class ReviewWrite(DTO):
    analysis: str
    improvements: str


class ScoreBreakdown(DTO):
    process: float
    business: float
    service: float
    compliance: float
    review: float
    objective_score: float
    evidence: dict = Field(default_factory=dict)


class Review(ReviewWrite):
    id: Id
    session_id: Id
    status: Literal["draft", "submitted", "graded"]
    source: Literal["rule"] = "rule"
    metrics_snapshot: Metrics | None = None
    objective_breakdown: ScoreBreakdown | None = None
    rule_snapshot: dict = Field(default_factory=dict)
    submitted_at: datetime | None = None


class GradeWrite(DTO):
    subjective_score: float = Field(ge=0, le=100)
    comment: str


class Grade(GradeWrite):
    id: Id
    session_id: Id
    teacher_id: Id
    objective_score: float
    total_score: float
    rules_version: str
    graded_at: datetime


class ReviewDetail(DTO):
    review: Review | None
    metrics: Metrics
    breakdown: ScoreBreakdown
    grade: Grade | None


class KnowledgeCard(DTO):
    title: str
    content: str


class AgentConfig(DTO):
    name: str = Field(min_length=1)
    duties: str
    boundaries: str
    instructions: str
    knowledge_cards: list[KnowledgeCard] = Field(default_factory=list)


class SessionContext(DTO):
    session_id: Id
    class_id: Id
    team_id: Id
    products: list[SessionProduct]
    recent_questions: list[TrainingEvent] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class AgentRunRequest(DTO):
    agent_id: Id | None = None
    config: AgentConfig
    question: str = Field(min_length=1)
    session_id: Id | None = None


class AgentRun(DTO):
    id: Id
    owner_id: Id
    agent_id: Id | None = None
    version_id: Id | None = None
    config_snapshot: AgentConfig
    question: str
    session_id: Id | None = None
    context_snapshot: dict = Field(default_factory=dict)
    context_sources: list[str] = Field(default_factory=list)
    output: str | None = None
    source: Literal["model", "rule"]
    model: str | None = None
    duration_ms: Count = 0
    status: Literal["running", "succeeded", "failed"]
    error: str | None = None
    created_at: datetime


CompetitionStatus = Literal["draft", "published", "finished"]


class CompetitionCreate(DTO):
    task_id: Id
    title: str = Field(min_length=1, max_length=200)


class Competition(DTO):
    id: Id
    task_id: Id
    title: str
    status: CompetitionStatus
    rule_snapshot: dict = Field(default_factory=dict)
    published_at: datetime | None = None


class LeaderboardEntry(DTO):
    team_id: Id
    team_name: str
    session_id: Id
    status: str
    metrics: Metrics
    objective_score: float | None = None
    subjective_score: float | None = None
    total_score: float | None = None


class Leaderboard(DTO):
    stage: Literal["provisional", "final"]
    rules_version: str
    score_weights: ScoreWeights
    deadline: datetime
    entries: list[LeaderboardEntry] = Field(default_factory=list)
    pending_entries: list[LeaderboardEntry] = Field(default_factory=list)


class EvidenceLink(DTO):
    kind: str
    label: str
    session_id: Id


class ComparisonTeam(DTO):
    team_id: Id
    team_name: str
    session_id: Id
    status: str
    preparation: Preparation
    products: list[SessionProduct] = Field(default_factory=list)
    metrics: Metrics
    breakdown: ScoreBreakdown | None = None
    grade: Grade | None = None
    evidence_links: list[EvidenceLink] = Field(default_factory=list)


class TaskComparison(DTO):
    task: Task
    teams: list[ComparisonTeam] = Field(default_factory=list)


class CompetitionComparison(DTO):
    competition: Competition
    teams: list[ComparisonTeam] = Field(default_factory=list)
