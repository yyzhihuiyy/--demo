/* Generated from backend/app/shared/schemas.py. Controller-owned; do not hand edit. */

export type PlatformContracts =
  | ActionRequest
  | AgentConfig
  | AgentRun
  | AgentRunRequest
  | AssortmentItem
  | AssortmentWrite
  | Checklist
  | ChecklistItem
  | ComparisonTeam
  | Competition
  | CompetitionComparison
  | CompetitionCreate
  | ControlRequest
  | Coupon
  | EvidenceLink
  | Grade
  | GradeWrite
  | Health
  | KnowledgeCard
  | Leaderboard
  | LeaderboardEntry
  | LiveState
  | LoginRequest
  | LoginResponse
  | Metrics
  | Order
  | Plan
  | Preparation
  | PreparationWrite
  | Product
  | Promotion
  | PurchaseItem
  | PurchaseRequest
  | Refund
  | Research
  | Review2
  | ReviewDetail
  | ReviewWrite
  | Room
  | ScoreBreakdown
  | ScoreWeights
  | ScriptSegment
  | SessionContext
  | SessionDetail
  | SessionProduct
  | Task
  | TaskComparison
  | TaskWrite
  | Team
  | TeamMember
  | TrainingEvent
  | TrainingSession
  | User;
export type Type = "select_product" | "issue_coupon" | "announcement" | "speech" | "reply" | "execute_script";
export type Name = string;
export type Duties = string;
export type Boundaries = string;
export type Instructions = string;
export type Title = string;
export type Content = string;
export type KnowledgeCards = KnowledgeCard[];
export type Id = number;
export type OwnerId = number;
export type AgentId = number | null;
export type VersionId = number | null;
export type Question = string;
export type SessionId = number | null;
export type ContextSources = string[];
export type Output = string | null;
export type Source = "model" | "rule";
export type Model = string | null;
export type DurationMs = number;
export type Status = "running" | "succeeded" | "failed";
export type Error = string | null;
export type CreatedAt = string;
export type AgentId1 = number | null;
export type Question1 = string;
export type SessionId1 = number | null;
export type ProductId = number;
export type Positioning = "traffic" | "profit" | "image";
export type SellingPoints = string;
export type SalePriceCents = number;
export type SortOrder = number;
export type Items = AssortmentItem[];
export type Key = string;
export type Passed = boolean;
export type Message = string;
export type Target = string;
export type Items1 = ChecklistItem[];
export type CanStart = boolean;
export type TeamId = number;
export type TeamName = string;
export type SessionId2 = number;
export type Status1 = string;
export type Audience = string;
export type CompetitorNotes = string;
export type PriceNotes = string;
export type SelectionReason = string;
export type Theme = string;
export type TargetAudience = string;
export type Id1 = string;
export type Kind = "opening" | "product" | "interaction" | "closing";
export type ProductId1 = number | null;
export type Text = string;
export type Script = ScriptSegment[];
export type Channel = "simulated_feed";
export type BudgetCents = number;
export type Audience1 = string;
export type Theme1 = string;
export type Title1 = string;
export type Announcement = string;
export type DiscountCents = number;
export type ProductId2 = number;
export type Positioning1 = "traffic" | "profit" | "image";
export type SellingPoints1 = string;
export type SalePriceCents1 = number;
export type SortOrder1 = number;
export type Id2 = number;
export type SessionId3 = number;
export type Title2 = string;
export type CostCents = number;
export type PurchasedQty = number;
export type StockQty = number;
export type Products = SessionProduct[];
export type GmvCents = number;
export type RefundCents = number;
export type NetSalesCents = number;
export type ProfitCents = number;
export type CashBalanceCents = number;
export type PromotionSpendCents = number;
export type OrderCount = number;
export type RefundedOrderCount = number;
export type OnlineCount = number;
export type CumulativeEntries = number;
export type ProductClicks = number;
export type AudienceQuestionCount = number;
export type RepliedQuestionCount = number;
export type ViolationCount = number;
export type SignedOrderCount = number;
export type ConversionRate = number | null;
export type ReplyRate = number | null;
export type Process = number;
export type Business = number;
export type Service = number;
export type Compliance = number;
export type Review = number;
export type ObjectiveScore = number;
export type SubjectiveScore = number;
export type Comment = string;
export type Id3 = number;
export type SessionId4 = number;
export type TeacherId = number;
export type ObjectiveScore1 = number;
export type TotalScore = number;
export type RulesVersion = string;
export type GradedAt = string;
export type Kind1 = string;
export type Label = string;
export type SessionId5 = number;
export type EvidenceLinks = EvidenceLink[];
export type Id4 = number;
export type TaskId = number;
export type Title3 = string;
export type Status2 = "draft" | "published" | "finished";
export type PublishedAt = string | null;
export type Teams = ComparisonTeam[];
export type TaskId1 = number;
export type Title4 = string;
export type Action = "start" | "pause" | "resume" | "end";
export type SubjectiveScore1 = number;
export type Comment1 = string;
export type Status3 = "ok";
export type Database = "ok";
export type ContractVersion = string;
export type ModelConfigured = boolean;
export type Stage = "provisional" | "final";
export type RulesVersion1 = string;
export type Process1 = number;
export type Business1 = number;
export type Service1 = number;
export type Compliance1 = number;
export type Review1 = number;
export type Deadline = string;
export type TeamId1 = number;
export type TeamName1 = string;
export type SessionId6 = number;
export type Status4 = string;
export type ObjectiveScore2 = number | null;
export type SubjectiveScore2 = number | null;
export type TotalScore1 = number | null;
export type Entries = LeaderboardEntry[];
export type PendingEntries = LeaderboardEntry[];
export type Status5 = "preparing" | "live" | "paused" | "ended" | "submitted" | "graded";
export type LatestEventId = number;
export type Username = string;
export type Password = string;
export type Token = string;
export type Id5 = number;
export type Username1 = string;
export type Role = "teacher" | "student";
export type ClassId = number;
export type Active = boolean;
export type Id6 = number;
export type SessionId7 = number;
export type SessionProductId = number;
export type BuyerLabel = string;
export type Qty = number;
export type UnitCostCents = number;
export type UnitSaleCents = number;
export type DiscountCents1 = number;
export type AmountCents = number;
export type Status6 = "pending_shipment" | "shipped" | "signed" | "refunded";
export type CreatedAt1 = string;
export type Script1 = ScriptSegment[];
export type ExpectedVersion = number;
export type Id7 = number;
export type Title5 = string;
export type Category = string;
export type CostCents1 = number;
export type ReferencePriceCents = number;
export type SellingPoints2 = string;
export type Supplier = string;
export type ImageOrPlaceholder = string;
export type SessionProductId1 = number;
export type Qty1 = number;
/**
 * @minItems 1
 */
export type Items2 = [PurchaseItem, ...PurchaseItem[]];
export type Id8 = number;
export type OrderId = number;
export type Reason = string;
export type Status7 = "pending" | "approved" | "rejected";
export type HandlerId = number | null;
export type HandlingNote = string;
export type AmountCents1 = number;
export type Analysis = string;
export type Improvements = string;
export type Id9 = number;
export type SessionId8 = number;
export type Status8 = "draft" | "submitted" | "graded";
export type Source1 = "rule";
export type SubmittedAt = string | null;
export type Analysis1 = string;
export type Improvements1 = string;
export type SessionId9 = number;
export type ClassId1 = number;
export type TeamId2 = number;
export type Products1 = SessionProduct[];
export type Id10 = number;
export type SessionId10 = number;
export type Type1 = string;
export type ActorId = number | null;
export type Source2 = "manual" | "rule";
export type CreatedAt2 = string;
export type RecentQuestions = TrainingEvent[];
export type Sources = string[];
export type Id11 = number;
export type TaskId2 = number;
export type TeamId3 = number;
export type Status9 = "preparing" | "live" | "paused" | "ended" | "submitted" | "graded";
export type PreparationVersion = number;
export type InitialBudgetCents = number;
export type StartedAt = string | null;
export type EndedAt = string | null;
export type LiveElapsedSeconds = number;
export type CurrentProductId = number | null;
export type Products2 = SessionProduct[];
export type Title6 = string;
export type Description = string;
export type TargetAudience1 = string;
export type InitialBudgetCents1 = number;
export type TargetGmvCents = number;
export type MarketHeat = number;
export type Difficulty = number;
export type StartsAt = string;
export type EndsAt = string;
export type TeamIds = number[];
export type Id12 = number;
export type ClassId2 = number;
export type TeacherId1 = number;
export type Status10 = "draft" | "published" | "closed";
export type RulesVersion2 = string;
export type Teams1 = ComparisonTeam[];
export type Title7 = string;
export type Description1 = string;
export type TargetAudience2 = string;
export type InitialBudgetCents2 = number;
export type TargetGmvCents1 = number;
export type MarketHeat1 = number;
export type Difficulty1 = number;
export type StartsAt1 = string;
export type EndsAt1 = string;
export type TeamIds1 = number[];
export type Id13 = number;
export type ClassId3 = number;
export type Name1 = string;
export type UserId = number;
export type Position = "host" | "control" | "service" | "operations";
export type Members = TeamMember[];

export interface ActionRequest {
  type: Type;
  payload: Payload;
}
export interface Payload {
  [k: string]: unknown;
}
export interface AgentConfig {
  name: Name;
  duties: Duties;
  boundaries: Boundaries;
  instructions: Instructions;
  knowledge_cards?: KnowledgeCards;
}
export interface KnowledgeCard {
  title: Title;
  content: Content;
}
export interface AgentRun {
  id: Id;
  owner_id: OwnerId;
  agent_id?: AgentId;
  version_id?: VersionId;
  config_snapshot: AgentConfig;
  question: Question;
  session_id?: SessionId;
  context_snapshot?: ContextSnapshot;
  context_sources?: ContextSources;
  output?: Output;
  source: Source;
  model?: Model;
  duration_ms?: DurationMs;
  status: Status;
  error?: Error;
  created_at: CreatedAt;
}
export interface ContextSnapshot {
  [k: string]: unknown;
}
export interface AgentRunRequest {
  agent_id?: AgentId1;
  config: AgentConfig;
  question: Question1;
  session_id?: SessionId1;
}
export interface AssortmentItem {
  product_id: ProductId;
  positioning: Positioning;
  selling_points?: SellingPoints;
  sale_price_cents: SalePriceCents;
  sort_order?: SortOrder;
}
export interface AssortmentWrite {
  items: Items;
}
export interface Checklist {
  items: Items1;
  can_start: CanStart;
}
export interface ChecklistItem {
  key: Key;
  passed: Passed;
  message: Message;
  target: Target;
}
export interface ComparisonTeam {
  team_id: TeamId;
  team_name: TeamName;
  session_id: SessionId2;
  status: Status1;
  preparation: Preparation;
  products?: Products;
  metrics: Metrics;
  breakdown?: ScoreBreakdown | null;
  grade?: Grade | null;
  evidence_links?: EvidenceLinks;
}
export interface Preparation {
  research?: Research;
  plan?: Plan;
  script?: Script;
  promotion?: Promotion;
  room?: Room;
  coupon?: Coupon;
}
export interface Research {
  audience?: Audience;
  competitor_notes?: CompetitorNotes;
  price_notes?: PriceNotes;
  selection_reason?: SelectionReason;
}
export interface Plan {
  theme?: Theme;
  target_audience?: TargetAudience;
}
export interface ScriptSegment {
  id: Id1;
  kind: Kind;
  product_id?: ProductId1;
  text?: Text;
}
export interface Promotion {
  channel?: Channel;
  budget_cents?: BudgetCents;
  audience?: Audience1;
}
export interface Room {
  theme?: Theme1;
  title?: Title1;
  announcement?: Announcement;
}
export interface Coupon {
  discount_cents?: DiscountCents;
}
export interface SessionProduct {
  product_id: ProductId2;
  positioning: Positioning1;
  selling_points?: SellingPoints1;
  sale_price_cents: SalePriceCents1;
  sort_order?: SortOrder1;
  id: Id2;
  session_id: SessionId3;
  title: Title2;
  cost_cents: CostCents;
  purchased_qty?: PurchasedQty;
  stock_qty?: StockQty;
}
export interface Metrics {
  gmv_cents?: GmvCents;
  refund_cents?: RefundCents;
  net_sales_cents?: NetSalesCents;
  profit_cents?: ProfitCents;
  cash_balance_cents?: CashBalanceCents;
  promotion_spend_cents?: PromotionSpendCents;
  order_count?: OrderCount;
  refunded_order_count?: RefundedOrderCount;
  online_count?: OnlineCount;
  cumulative_entries?: CumulativeEntries;
  product_clicks?: ProductClicks;
  audience_question_count?: AudienceQuestionCount;
  replied_question_count?: RepliedQuestionCount;
  violation_count?: ViolationCount;
  signed_order_count?: SignedOrderCount;
  conversion_rate?: ConversionRate;
  reply_rate?: ReplyRate;
}
export interface ScoreBreakdown {
  process: Process;
  business: Business;
  service: Service;
  compliance: Compliance;
  review: Review;
  objective_score: ObjectiveScore;
  evidence?: Evidence;
}
export interface Evidence {
  [k: string]: unknown;
}
export interface Grade {
  subjective_score: SubjectiveScore;
  comment: Comment;
  id: Id3;
  session_id: SessionId4;
  teacher_id: TeacherId;
  objective_score: ObjectiveScore1;
  total_score: TotalScore;
  rules_version: RulesVersion;
  graded_at: GradedAt;
}
export interface EvidenceLink {
  kind: Kind1;
  label: Label;
  session_id: SessionId5;
}
export interface Competition {
  id: Id4;
  task_id: TaskId;
  title: Title3;
  status: Status2;
  rule_snapshot?: RuleSnapshot;
  published_at?: PublishedAt;
}
export interface RuleSnapshot {
  [k: string]: unknown;
}
export interface CompetitionComparison {
  competition: Competition;
  teams?: Teams;
}
export interface CompetitionCreate {
  task_id: TaskId1;
  title: Title4;
}
export interface ControlRequest {
  action: Action;
}
export interface GradeWrite {
  subjective_score: SubjectiveScore1;
  comment: Comment1;
}
export interface Health {
  status: Status3;
  database: Database;
  contract_version: ContractVersion;
  modules: Modules;
  model_configured: ModelConfigured;
}
export interface Modules {
  [k: string]: string;
}
export interface Leaderboard {
  stage: Stage;
  rules_version: RulesVersion1;
  score_weights: ScoreWeights;
  deadline: Deadline;
  entries?: Entries;
  pending_entries?: PendingEntries;
}
export interface ScoreWeights {
  process?: Process1;
  business?: Business1;
  service?: Service1;
  compliance?: Compliance1;
  review?: Review1;
}
export interface LeaderboardEntry {
  team_id: TeamId1;
  team_name: TeamName1;
  session_id: SessionId6;
  status: Status4;
  metrics: Metrics;
  objective_score?: ObjectiveScore2;
  subjective_score?: SubjectiveScore2;
  total_score?: TotalScore1;
}
export interface LiveState {
  status: Status5;
  current_product?: SessionProduct | null;
  metrics: Metrics;
  latest_event_id?: LatestEventId;
}
export interface LoginRequest {
  username: Username;
  password: Password;
}
export interface LoginResponse {
  token: Token;
  user: User;
}
export interface User {
  id: Id5;
  username: Username1;
  role: Role;
  class_id: ClassId;
  active?: Active;
}
export interface Order {
  id: Id6;
  session_id: SessionId7;
  session_product_id: SessionProductId;
  buyer_label: BuyerLabel;
  qty: Qty;
  unit_cost_cents: UnitCostCents;
  unit_sale_cents: UnitSaleCents;
  discount_cents: DiscountCents1;
  amount_cents: AmountCents;
  status: Status6;
  created_at: CreatedAt1;
}
export interface PreparationWrite {
  research?: Research;
  plan?: Plan;
  script?: Script1;
  promotion?: Promotion;
  room?: Room;
  coupon?: Coupon;
  expected_version: ExpectedVersion;
}
export interface Product {
  id: Id7;
  title: Title5;
  category: Category;
  cost_cents: CostCents1;
  reference_price_cents: ReferencePriceCents;
  selling_points: SellingPoints2;
  supplier: Supplier;
  image_or_placeholder?: ImageOrPlaceholder;
}
export interface PurchaseItem {
  session_product_id: SessionProductId1;
  qty: Qty1;
}
export interface PurchaseRequest {
  items: Items2;
}
export interface Refund {
  id: Id8;
  order_id: OrderId;
  reason: Reason;
  status: Status7;
  handler_id?: HandlerId;
  handling_note?: HandlingNote;
  amount_cents: AmountCents1;
}
export interface Review2 {
  analysis: Analysis;
  improvements: Improvements;
  id: Id9;
  session_id: SessionId8;
  status: Status8;
  source?: Source1;
  metrics_snapshot?: Metrics | null;
  objective_breakdown?: ScoreBreakdown | null;
  rule_snapshot?: RuleSnapshot1;
  submitted_at?: SubmittedAt;
}
export interface RuleSnapshot1 {
  [k: string]: unknown;
}
export interface ReviewDetail {
  review: Review2 | null;
  metrics: Metrics;
  breakdown: ScoreBreakdown;
  grade: Grade | null;
}
export interface ReviewWrite {
  analysis: Analysis1;
  improvements: Improvements1;
}
export interface SessionContext {
  session_id: SessionId9;
  class_id: ClassId1;
  team_id: TeamId2;
  products: Products1;
  recent_questions?: RecentQuestions;
  sources?: Sources;
}
export interface TrainingEvent {
  id: Id10;
  session_id: SessionId10;
  type: Type1;
  actor_id?: ActorId;
  source: Source2;
  payload: Payload1;
  created_at: CreatedAt2;
}
export interface Payload1 {
  [k: string]: unknown;
}
export interface SessionDetail {
  session: TrainingSession;
  preparation: Preparation;
  products: Products2;
  metrics: Metrics;
  capabilities: Capabilities;
}
export interface TrainingSession {
  id: Id11;
  task_id: TaskId2;
  team_id: TeamId3;
  status: Status9;
  rule_snapshot?: RuleSnapshot2;
  preparation_version?: PreparationVersion;
  initial_budget_cents: InitialBudgetCents;
  started_at?: StartedAt;
  ended_at?: EndedAt;
  live_elapsed_seconds?: LiveElapsedSeconds;
  current_product_id?: CurrentProductId;
}
export interface RuleSnapshot2 {
  [k: string]: unknown;
}
export interface Capabilities {
  [k: string]: boolean;
}
export interface Task {
  title: Title6;
  description?: Description;
  target_audience?: TargetAudience1;
  initial_budget_cents?: InitialBudgetCents1;
  target_gmv_cents?: TargetGmvCents;
  market_heat?: MarketHeat;
  difficulty?: Difficulty;
  starts_at: StartsAt;
  ends_at: EndsAt;
  score_weights?: ScoreWeights;
  team_ids?: TeamIds;
  id: Id12;
  class_id: ClassId2;
  teacher_id: TeacherId1;
  status: Status10;
  rules_version?: RulesVersion2;
}
export interface TaskComparison {
  task: Task;
  teams?: Teams1;
}
export interface TaskWrite {
  title: Title7;
  description?: Description1;
  target_audience?: TargetAudience2;
  initial_budget_cents?: InitialBudgetCents2;
  target_gmv_cents?: TargetGmvCents1;
  market_heat?: MarketHeat1;
  difficulty?: Difficulty1;
  starts_at: StartsAt1;
  ends_at: EndsAt1;
  score_weights?: ScoreWeights;
  team_ids?: TeamIds1;
}
export interface Team {
  id: Id13;
  class_id: ClassId3;
  name: Name1;
  members?: Members;
}
export interface TeamMember {
  user_id: UserId;
  position: Position;
}
