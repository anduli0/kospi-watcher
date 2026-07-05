/**
 * Typed client for the KOSPI-WATCHER API.
 *
 * The base URL is injected at build time from NEXT_PUBLIC_API_BASE_URL
 * (see next.config.mjs). All calls are analysis/risk only — there is no
 * order-submission endpoint in this phase.
 */

/**
 * Resolve the API base URL.
 *
 * In the browser we always call our OWN origin (relative paths). Next.js rewrites
 * proxy `/api/*` and `/health` to the API server-side (see next.config.mjs), so
 * the client bundle carries no hardcoded host — it works identically on
 * localhost, over LAN, and behind any public tunnel, with no CORS. Only
 * server-side code (SSR/build, no `window`) falls back to an absolute URL.
 */
function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    return ""; // same-origin; proxied by Next rewrites
  }
  const env = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (env && env.trim()) return env.trim().replace(/\/+$/, "");
  return "http://127.0.0.1:18080";
}

export const API_BASE_URL = resolveApiBase();

// --- Response types (mirror src/kospi_watcher/api/schemas/responses.py) ---

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  database: { connected: boolean; backend: string };
  redis: { backend: string; connected: boolean; detail: string };
  trading_mode: string;
  live_trading_enabled: boolean;
  auto_execution_enabled: boolean;
}

export interface SystemStatusResponse {
  app: string;
  version: string;
  environment: string;
  server_time_utc: string;
  server_time_kst: string;
  trading_mode: string;
  feature_flags: Record<string, boolean>;
  data_sources: { name: string; status: string }[];
  agent_count: number;
}

export interface AgentInfo {
  name: string;
  version: string;
  category: string;
  summary: string;
  enabled: boolean;
}

export interface AgentListResponse {
  count: number;
  agents: AgentInfo[];
}

export interface AgentRun {
  run_id: string;
  agent_name: string;
  agent_version: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  model_name: string;
  prompt_version: string;
  findings: AgentFinding[];
  error: string | null;
}

export interface AgentFinding {
  schema_version: string;
  agent_name: string;
  horizon: string;
  direction: string;
  impact: string;
  confidence: number;
  thesis: string;
  affected_sectors: string[];
  affected_symbols: string[];
  invalidation_conditions: string[];
  data_quality: string;
}

export interface RiskCheckResult {
  code: string;
  passed: boolean;
  detail: string;
}

export interface RiskDecision {
  decision_id: string;
  proposal_id: string;
  status: "APPROVED" | "REJECTED";
  created_at: string;
  checks: RiskCheckResult[];
  failed_checks: string[];
  reason: string;
  requires_human: boolean;
}

export interface AuditLogEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  created_at: string;
}

export interface AuditLogPage {
  count: number;
  limit: number;
  offset: number;
  items: AuditLogEntry[];
}

export interface OrderProposalInput {
  symbol: string;
  instrument_type: string;
  side: string;
  order_type: string;
  quantity: number;
  limit_price?: string | null;
  strategy_id: string;
  strategy_version?: string;
  idempotency_key: string;
}

export interface MarketQuote {
  symbol: string;
  price: string;
  currency: string;
  as_of: string;
  source: string;
  stale: boolean;
}

export type Direction = "BULLISH" | "BEARISH" | "NEUTRAL";
export type StanceLabel = "OVERWEIGHT" | "NEUTRAL" | "UNDERWEIGHT" | "AVOID";

export interface DeskView {
  desk: string;
  title: string;
  lean: Direction;
  conviction: number;
  weight: number;
  score: number;
  member_count: number;
  responded: number;
  summary: string;
  top_drivers: string[];
}

export interface InstrumentStance {
  symbol: string;
  name: string;
  kind: string;
  label: StanceLabel;
  rationale: string;
  risk_note: string | null;
}

export interface Scenario {
  name: string;
  probability: number;
  thesis: string;
  triggers: string[];
}

export interface AgentPosition {
  agent: string;
  is_lead: boolean;
  direction: Direction;
  confidence: number;
  note: string;
}

export interface DeskDeliberation {
  desk: string;
  title: string;
  consensus: Direction;
  agreement: number;
  positions: AgentPosition[];
  dissent: string[];
  lead_note: string;
}

export interface ChiefDeliberation {
  overall: Direction;
  aligned_desks: string[];
  conflicted_desks: string[];
  note: string;
}

export interface Deliberation {
  desks: DeskDeliberation[];
  chief: ChiefDeliberation;
}

export type PolicyStance = "HAWKISH" | "NEUTRAL" | "DOVISH";

export interface MonetaryPolicySignal {
  stance: PolicyStance;
  expected_hikes_2026: number; // negative = cuts
  equity_bias: Direction; // KOSPI implication (hawkish → BEARISH)
  confidence: number;
  rationale: string;
  drivers: string[];
  source: string; // "config" | "news" | "mock"
  as_of: string;
}

export interface TrendSignal {
  direction: Direction;
  strength: number; // 0..1
  price: string | null;
  sma100: string | null;
  mom60_pct: string | null;
  note: string;
  source: string; // "yahoo" | "mock" | "none"
}

export interface HorizonAccuracy {
  horizon_days: number;
  label: string;
  hit_rate: number;
  base_rate: number;
  skill: number;
  coverage: number;
  sample: number;
}

export interface BacktestReport {
  as_of: string;
  symbol: string;
  source: string;
  n_days: number;
  test_fraction: number;
  train: HorizonAccuracy[];
  test: HorizonAccuracy[];
  primary_horizon_days: number;
  primary_hit_rate: number;
  primary_base_rate: number;
  primary_skill: number;
  interpretation: string;
}

// --- Prediction tracking + auto-feedback calibration (ADR-027) ---

export interface TrackPoint {
  date: string;
  actual_cum_pct: number;
  model_cum_pct: number;
  predicted_dir: Direction;
  hit: boolean | null;
}

export interface AccuracyScore {
  samples: number;
  hit_rate: number;
  base_rate: number;
  skill: number;
  bull_samples: number;
  bear_samples: number;
  bull_hit: number | null;
  bear_hit: number | null;
  coverage: number;
  final_actual_cum_pct: number;
  final_model_cum_pct: number;
}

export interface Calibration {
  direction_bias: number;
  confidence_target: number; // realized hit rate the confidence is anchored to
  grade: string;
  basis: string;
}

export interface AccuracyTrackReport {
  as_of: string;
  symbol: string;
  source: string;
  horizon_days: number;
  window_days: number;
  points: TrackPoint[];
  score: AccuracyScore;
  calibration: Calibration;
  interpretation: string;
}

export interface MarketPrediction {
  prediction_id: string;
  as_of: string;
  subject: string;
  horizon: string;
  horizon_label: string;
  regime: string;
  direction: Direction;
  confidence: number;
  data_quality: string;
  headline: string;
  brief: string;
  desk_views: DeskView[];
  deliberation: Deliberation | null;
  monetary_policy: MonetaryPolicySignal | null;
  trend_signal: TrendSignal | null;
  calibration: Calibration | null;
  instrument_stances: InstrumentStance[];
  scenarios: Scenario[];
  news_refs: string[];
  generated_by: string;
  agent_count: number;
}

export interface NewsItem {
  id: string;
  title: string;
  url: string;
  source: string;
  topic: string;
  published_at: string;
  date_kst: string;
}

export interface NewsHeadline {
  title: string;
  source: string;
  url: string;
  published_at: string;
}

export interface NewsTheme {
  topic: string;
  count: number;
  read?: string;
  headlines: NewsHeadline[];
}

export interface NewsKeyPoint {
  tag: string;
  title: string;
  source: string;
  url: string;
}

export interface NewsBrief {
  date: string;
  item_count: number;
  is_trading_day?: boolean; // false on weekends/휴장일
  summary: string;
  market_read: string;
  key_points?: NewsKeyPoint[];
  themes: NewsTheme[];
  generated_by: string;
}

export interface MorningBriefing {
  news_added: number;
  prediction_direction: string;
  brief_items: number;
  telegram_enabled: boolean;
  telegram_report: string;
  telegram_brief: string;
  report_message: string;
  brief_message: string;
}

export interface SyncLastResult {
  direction?: string;
  confidence?: number;
  generated_by?: string;
  news_added?: number;
  brief_items?: number;
}

export interface SyncStatus {
  running: boolean;
  stage: string | null;
  stage_ko: string;
  stages: string[];
  started_at: string | null;
  finished_at: string | null;
  ok: boolean | null;
  error: string | null;
  runtime: string; // "mock" | "llm" | "claude_cli"
  model: string;
  cooldown_seconds: number;
  last_prediction_at: string | null;
  stale: boolean;
  stale_after_hours: number;
  last_result: SyncLastResult | null;
}

export interface SyncRunResult {
  started: boolean;
  reason: string;
  status: SyncStatus;
}

export interface NewsListResponse {
  count: number;
  date: string | null;
  items: NewsItem[];
}

export interface NewsDateCount {
  date: string;
  count: number;
}

export interface NewsDatesResponse {
  dates: NewsDateCount[];
}

export interface ScrapeResponse {
  fetched: number;
  added: number;
  pruned: number;
  topics: string[];
}

export interface BriefStance {
  symbol: string;
  name: string;
  kind: string;
  label: StanceLabel;
  risk_note: string | null;
}

export interface BriefResponse {
  as_of: string;
  generated_by: string;
  agent_count: number;
  direction: Direction;
  confidence: number;
  regime: string;
  headline: string;
  brief: string;
  stances: BriefStance[];
}

export interface OrgDeskInfo {
  key: string;
  title: string;
  tier: string;
  weight: number;
  lead: string;
  members: string[];
}

export interface OrgResponse {
  desks: OrgDeskInfo[];
  tiers: string[];
  agent_count: number;
}

export interface MarketQuotesResponse {
  provider: string;
  count: number;
  quotes: MarketQuote[];
}

// --- Market-flow analysis (sectors + investor flows; mirrors domain/market_analysis) ---

export interface SectorMove {
  key: string;
  name: string;
  symbol: string;
  price: string | null;
  change_pct: string; // signed percent, as string (Decimal)
  source: string; // "yahoo" | "mock"
}

export interface InvestorTrendPoint {
  date: string;
  net: string; // 억원, signed
}

export interface InvestorFlow {
  investor: "FOREIGN" | "INSTITUTION" | "INDIVIDUAL";
  label: string;
  net_today: string;
  net_5d: string;
  trend: InvestorTrendPoint[];
  source: string; // "representative" | "mock"
}

export interface MarketAnalysis {
  as_of: string;
  index_symbol: string;
  index_price: string | null;
  index_change_pct: string | null;
  sectors: SectorMove[];
  leaders: SectorMove[];
  laggards: SectorMove[];
  flows: InvestorFlow[];
  narrative: string;
  sector_source: string;
  flow_source: string;
}

// --- Per-instrument analysis (verdict + short/mid/long outlook; ADR-023) ---

export type PositionVerdict = "BUY" | "HOLD" | "SELL";

export interface HorizonProjection {
  horizon: "SHORT" | "MID" | "LONG";
  label: string;
  direction: Direction;
  expected_return_pct: string; // signed %, as string
  target_low: string | null;
  target_base: string | null;
  target_high: string | null;
  rationale: string;
}

export interface InstrumentOutlook {
  symbol: string;
  name: string;
  kind: string;
  current_price: string | null;
  price_source: string;
  verdict: PositionVerdict;
  verdict_label: string;
  stance_label: StanceLabel;
  conviction: number;
  summary: string;
  risk_note: string | null;
  projections: HorizonProjection[];
}

export interface InstrumentAnalysisReport {
  as_of: string;
  subject: string;
  direction: Direction;
  confidence: number;
  regime: string;
  generated_by: string;
  house_summary: string;
  monetary_policy: MonetaryPolicySignal | null;
  trend_signal: TrendSignal | null;
  instruments: InstrumentOutlook[];
  price_source: string;
  disclaimer: string;
}

export interface FillResponse {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  price: string;
  liquidity: string;
  created_at: string;
}

export interface OrderResponse {
  id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  limit_price: string | null;
  status: string;
  broker_order_id: string | null;
  trading_mode: string;
  filled_quantity: number;
  avg_fill_price: string | null;
  created_at: string;
}

export interface OrderListResponse {
  count: number;
  orders: OrderResponse[];
}

export interface PositionResponse {
  symbol: string;
  quantity: number;
  avg_cost: string;
  realized_pnl: string;
  mark_price: string | null;
  market_value: string | null;
  unrealized_pnl: string | null;
}

export interface AccountResponse {
  account: string;
  as_of: string;
  realized_pnl: string;
  unrealized_pnl: string;
  total_pnl: string;
  gross_exposure: string;
  position_count: number;
  positions: PositionResponse[];
}

export interface SubmitOrderResponse {
  order_id: string;
  status: string;
  message: string;
  reference_price: string | null;
  decision: RiskDecision;
  fill: FillResponse | null;
  position: PositionResponse | null;
}

// --- Individual stock recommendations (ADR-026) ---

export type StockHorizonKey = "SHORT" | "MID" | "LONG";

export interface StockPick {
  rank: number;
  code: string;
  name: string;
  sector: string;
  themes: string[];
  price: string | null;
  momentum_pct: string | null;
  stretch_pct: string | null;
  overheated: boolean;
  conviction: string; // 적극매수 | 매수 | 관심
  score: number;
  drivers: string[];
  rationale: string;
  detail: string;
  news_catalyst: string | null;
}

export interface HorizonRecommendation {
  horizon: StockHorizonKey;
  label: string;
  approach: string;
  picks: StockPick[];
}

export interface StockRecommendationReport {
  as_of: string;
  house_direction: Direction;
  house_regime: string;
  monetary_stance: string;
  universe_size: number;
  price_source: string;
  horizons: HorizonRecommendation[];
  disclaimer: string;
}

// --- Fetch helper ---

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Fetch a JSON endpoint with built-in resilience.
 *
 * Network failures (the backend briefly down — e.g. the API's self-healing
 * restart, or the page opened before the API is up) are retried a few times
 * with exponential backoff before surfacing as an error. Only safe (GET)
 * requests are retried, so a POST (e.g. generating a prediction) is never
 * accidentally sent twice. HTTP error responses (4xx/5xx) are NOT retried —
 * they are deterministic and bubble up immediately (e.g. 404 = no prediction).
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const retryable = method === "GET";
  const maxAttempts = retryable ? 3 : 1;

  let lastCause: unknown;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    let resp: Response;
    try {
      resp = await fetch(`${API_BASE_URL}${path}`, {
        ...init,
        headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
        cache: "no-store",
      });
    } catch (cause) {
      lastCause = cause;
      if (attempt < maxAttempts - 1) {
        await sleep(400 * 2 ** attempt); // 400ms, 800ms
        continue;
      }
      throw new ApiError(0, `API unreachable at ${API_BASE_URL} (${String(cause)})`);
    }
    if (!resp.ok) {
      const detail = await resp.text().catch(() => resp.statusText);
      throw new ApiError(resp.status, detail || resp.statusText);
    }
    return (await resp.json()) as T;
  }
  // Unreachable (loop either returns or throws), but satisfies the type checker.
  throw new ApiError(0, `API unreachable at ${API_BASE_URL} (${String(lastCause)})`);
}

// --- Endpoints (7) ---

export const api = {
  health: () => request<HealthResponse>("/health"),
  systemStatus: () => request<SystemStatusResponse>("/api/v1/system/status"),
  listAgents: () => request<AgentListResponse>("/api/v1/agents"),
  mockRun: (agentName: string, universe: string[] = []) =>
    request<AgentRun>("/api/v1/agents/mock-run", {
      method: "POST",
      body: JSON.stringify({ agent_name: agentName, universe }),
    }),
  runAgent: (agentName: string, universe: string[] = []) =>
    request<AgentRun>("/api/v1/agents/run", {
      method: "POST",
      body: JSON.stringify({ agent_name: agentName, universe }),
    }),
  marketQuotes: (symbols?: string[]) =>
    request<MarketQuotesResponse>(
      "/api/v1/market/quotes" + (symbols?.length ? `?symbols=${symbols.join(",")}` : ""),
    ),
  marketAnalysis: () => request<MarketAnalysis>("/api/v1/market/analysis"),
  instrumentAnalysis: () =>
    request<InstrumentAnalysisReport>("/api/v1/analysis/instruments"),
  backtest: () => request<BacktestReport>("/api/v1/backtest"),
  accuracyTrack: () => request<AccuracyTrackReport>("/api/v1/accuracy/track"),
  stockRecommendations: () =>
    request<StockRecommendationReport>("/api/v1/stocks/recommendations"),
  submitOrder: (proposal: OrderProposalInput, marketOpen = true, lastPrice?: string) =>
    request<SubmitOrderResponse>("/api/v1/orders", {
      method: "POST",
      body: JSON.stringify({
        proposal,
        market_open: marketOpen,
        last_price: lastPrice ?? null,
      }),
    }),
  listOrders: (limit = 50) => request<OrderListResponse>(`/api/v1/orders?limit=${limit}`),
  positions: () => request<PositionResponse[]>("/api/v1/positions"),
  account: () => request<AccountResponse>("/api/v1/account"),
  runPrediction: (universe: string[] = []) =>
    request<MarketPrediction>("/api/v1/prediction/run", {
      method: "POST",
      body: JSON.stringify({ agent_name: "synthesis", universe }),
    }),
  latestPrediction: () => request<MarketPrediction>("/api/v1/prediction/latest"),
  brief: () => request<BriefResponse>("/api/v1/brief"),
  agentsOrg: () => request<OrgResponse>("/api/v1/agents/org"),
  news: (date?: string, limit = 60) =>
    request<NewsListResponse>(
      `/api/v1/news?limit=${limit}` + (date ? `&date=${date}` : ""),
    ),
  newsDates: () => request<NewsDatesResponse>("/api/v1/news/dates"),
  scrapeNews: () => request<ScrapeResponse>("/api/v1/news/scrape", { method: "POST" }),
  newsBrief: () => request<NewsBrief>("/api/v1/news/brief"),
  runNewsBrief: () => request<NewsBrief>("/api/v1/news/brief/run", { method: "POST" }),
  morningBriefing: () =>
    request<MorningBriefing>("/api/v1/notify/morning", { method: "POST" }),
  syncStatus: () => request<SyncStatus>("/api/v1/sync/status"),
  syncRun: () => request<SyncRunResult>("/api/v1/sync/run", { method: "POST" }),
  validateProposal: (proposal: OrderProposalInput) =>
    request<{ valid: boolean; proposal_id: string; detail: string }>(
      "/api/v1/order-proposals/validate",
      { method: "POST", body: JSON.stringify(proposal) },
    ),
  evaluateRisk: (proposal: OrderProposalInput, marketOpen: boolean, lastPrice?: string) =>
    request<RiskDecision>("/api/v1/risk/evaluate", {
      method: "POST",
      body: JSON.stringify({
        proposal,
        market_open: marketOpen,
        last_price: lastPrice ?? null,
      }),
    }),
  auditLogs: (limit = 25, offset = 0) =>
    request<AuditLogPage>(`/api/v1/audit-logs?limit=${limit}&offset=${offset}`),
};
